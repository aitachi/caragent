"""Web 表面层（教程 Ch.8：CLI / ACP 之外的第三种表面）。

GET  /                 查询表单页（对话 + 实时日志面板）
POST /api/query        {"text": "..."} → 在线运行 agent，返回结果/工具轨迹/用量账本
POST /api/run          {"text": "..."} → 启动带日志任务，返回 {"run_id"}
GET  /api/stream/<id>  SSE 实时事件流（llm/tool/usage/耗时）
GET  /api/run/<id>     任务最终状态 JSON

安全边界：并发闸（默认 1，防 API 限速雪崩）+ 输入长度护栏（loop 层已有 20 万字符）
+ 每次请求独立 workdir + 后台 key 只走环境变量（绝不进页面/响应）。
"""
from __future__ import annotations

import json
import os
import queue
import re
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .loop import Agent

MAX_CONCURRENT = int(os.environ.get("MINIAGENT_WEB_CONCURRENCY", "1"))
TASK_TIMEOUT = int(os.environ.get("MINIAGENT_WEB_TIMEOUT", "600"))
WEB_ROOT = os.environ.get("MINIAGENT_WEB_ROOT",
                          os.path.join(tempfile.gettempdir(), "miniagent_web"))

_sem = threading.Semaphore(MAX_CONCURRENT)

# ---- 带日志任务注册表：run_id -> RunState ----
# run 结果与事件日志全部落在内存 + 独立 workdir 的 transcript；页面刷新后可回捞。
_RUNS: dict[str, "RunState"] = {}
_RUNS_LOCK = threading.Lock()
_RUNS_MAX = 50  # 防内存无界：最多保留最近 50 个已完成任务

# ---- 多轮会话注册表：session_id -> {"agent": Agent, "workdir": str} ----
# 同一 session_id 的后续轮次复用同一 Agent 实例：消息列表连续（模型记得
# 上文）、workdir 连续（上一轮创建的文件这一轮还在）。
_SESSIONS: dict[str, dict] = {}
_SESSIONS_LOCK = threading.Lock()
_SESSIONS_MAX = 20


def _trim_sessions() -> None:
    """会话 LRU：超上限删最老会话（其 Agent 随之可被 GC，transcript 留在磁盘）。"""
    with _SESSIONS_LOCK:
        for sid in list(_SESSIONS)[:max(0, len(_SESSIONS) - _SESSIONS_MAX)]:
            del _SESSIONS[sid]


class RunState:
    """一次后台任务的全部状态：事件队列(多消费者) + 终态。"""

    def __init__(self, run_id: str, workdir: str, text: str,
                 session_id: str | None = None, turn: int = 1):
        self.run_id = run_id
        self.workdir = workdir
        self.text = text
        self.session_id = session_id or ""   # 非空=多轮复用会话
        self.turn = turn                     # 会话内第几轮
        self.events: list[dict] = []          # 全量事件（回放用）
        self.subscribers: list[queue.Queue] = []  # SSE 订阅者
        self.status = "pending"               # pending/running/done/error
        self.result: str = ""
        self.error: str = ""
        self.usage: dict = {}
        self.started = time.time()
        self.finished: float | None = None
        self._lock = threading.Lock()

    def publish(self, event: dict) -> None:
        """事件落档并广播给所有 SSE 订阅者。"""
        with self._lock:
            self.events.append(event)
            for q in self.subscribers:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    pass

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=1000)
        with self._lock:
            # 新订阅者先拿历史，再接增量
            for ev in self.events:
                q.put_nowait(ev)
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def finish(self, status: str, result: str = "", error: str = "",
               usage: dict | None = None) -> None:
        self.status = status
        self.result = result
        self.error = error
        self.usage = usage or {}
        self.finished = time.time()
        end = {"type": "end", "status": status, "run_id": self.run_id,
               "usage": self.usage, "elapsed": round(self.finished - self.started, 2)}
        if error:
            end["error"] = error
        if result:
            end["result"] = result
        self.publish(end)

    def summary(self) -> dict:
        return {"run_id": self.run_id, "status": self.status,
                "text": self.text, "workdir": self.workdir,
                "session_id": self.session_id, "turn": self.turn,
                "usage": self.usage, "result": self.result, "error": self.error,
                "elapsed": (round((self.finished or time.time()) - self.started, 2))}


def _trim_runs() -> None:
    """保留最近 _RUNS_MAX 个任务，防止注册表无界增长。"""
    with _RUNS_LOCK:
        if len(_RUNS) <= _RUNS_MAX:
            return
        done_ids = [rid for rid, r in _RUNS.items()
                    if r.status in ("done", "error")]
        for rid in done_ids[:len(_RUNS) - _RUNS_MAX]:
            del _RUNS[rid]


def _fmt_args(args: dict) -> str:
    """工具参数 → 单行展示文本（长值截断）。"""
    parts = []
    for k, v in args.items():
        s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
        if len(s) > 160:
            s = s[:160] + "…"
        parts.append(f"{k}={s}")
    return " ".join(parts)


def run_task_logged(run: RunState, session_id: str | None = None) -> None:
    """跑一轮 agent；通过 hooks 收集 LLM/工具/耗时事件。

    多轮：session_id 已存在 → 复用同一 Agent（消息列表与 workdir 连续）；
    新会话 → 建新 Agent。埋点全部走 Agent 自带的 on_event 机制（进程内
    回调），不侵入 loop 窄腰核心 —— 符合"表面层只挂边上"的设计宪法。
    """
    run.status = "running"
    step_counter = [0]   # 闭包可变：本轮工具调用序号（before/after 配对）

    def ev_session_start(payload):
        run.publish({"type": "session_start", "ts": time.time(),
                     "workdir": payload.get("workdir", ""),
                     "task": payload.get("task", "")[:500],
                     "session_id": session_id or "",
                     "turn": run.turn})

    def ev_before_tool(payload):
        step_counter[0] += 1
        run.publish({"type": "tool_start", "ts": time.time(),
                     "step": step_counter[0],
                     "tool": payload.get("tool", "?"),
                     "args": payload.get("args", {}),
                     "preview": _fmt_args(payload.get("args", {}))})

    def ev_after_tool(payload):
        result = str(payload.get("result", ""))
        run.publish({"type": "tool_end", "ts": time.time(),
                     "step": step_counter[0],
                     "tool": payload.get("tool", "?"),
                     "ok": not (result.startswith("error:")
                                or result.startswith("permission denied:")
                                or result.startswith("blocked by hook:")),
                     "result_preview": (result[:1500] + "…") if len(result) > 1500 else result,
                     "result_len": len(result)})

    def ev_session_end(payload):
        run.publish({"type": "session_end", "ts": time.time(),
                     "steps": payload.get("steps", 0),
                     "text_preview": str(payload.get("text", ""))[:1500],
                     "turn": run.turn})

    # LLM 调用与用量没有专门 hook → 用轻量子类包一层 chat 计时
    from .llm import LLM

    class LoggedLLM(LLM):
        def chat(self, messages, tools=None):
            t = time.time()
            req_tokens_est = sum(len(str(m.get("content", ""))) for m in messages) // 4
            try:
                resp = super().chat(messages, tools)
            except Exception as e:
                run.publish({"type": "llm_error", "ts": time.time(),
                             "model": self.model,
                             "elapsed": round(time.time() - t, 2),
                             "error": f"{type(e).__name__}: {e}"})
                raise
            u = resp.get("usage") or {}
            run.publish({"type": "llm", "ts": time.time(),
                         "model": self.model,
                         "msg_count": len(messages),
                         "prompt_tokens": u.get("prompt_tokens", 0),
                         "completion_tokens": u.get("completion_tokens", 0),
                         "est_ctx_tokens": req_tokens_est,
                         "tool_calls": [tc.get("name", "?")
                                        for tc in resp.get("tool_calls", [])],
                         "content_preview": (resp.get("content") or "")[:800],
                         "elapsed": round(time.time() - t, 2)})
            return resp

    try:
        # 多轮：同 session_id 复用 Agent 实例（消息列表连续 → 模型记得上文）
        agent = None
        if session_id:
            with _SESSIONS_LOCK:
                entry = _SESSIONS.get(session_id)
                agent = entry["agent"] if entry else None
        if agent is not None:
            # 复用：换绑本轮 hook 与 LoggedLLM（事件发到本轮 run 的流），
            # 消息列表与 workdir 连续。注意必须换 llm —— 上一轮的 LoggedLLM
            # 闭包捕获的是上一轮的 run，不换会把本轮 llm 事件发错流。
            agent.hooks.clear()
            for ev, fn in (("session_start", ev_session_start),
                           ("before_tool", ev_before_tool),
                           ("after_tool", ev_after_tool),
                           ("session_end", ev_session_end)):
                agent.hooks.on(ev, fn)
            agent.llm = LoggedLLM()
        else:
            agent = Agent(run.workdir, permission_mode="auto", llm=LoggedLLM(),
                          on_event={"session_start": ev_session_start,
                                    "before_tool": ev_before_tool,
                                    "after_tool": ev_after_tool,
                                    "session_end": ev_session_end})

        result = agent.run(run.text)
        run.finish("done", result=result, usage=dict(agent.usage))

        # 会话登记（首轮分配 sid；复用时刷新 LRU 位）
        sid = session_id or uuid.uuid4().hex[:12]
        with _SESSIONS_LOCK:
            _SESSIONS.pop(sid, None)
            _SESSIONS[sid] = {"agent": agent, "workdir": run.workdir}
        run.session_id = sid
        run.publish({"type": "session_bound", "ts": time.time(),
                     "session_id": sid})
        _trim_sessions()
    except Exception as e:
        run.finish("error", error=f"{type(e).__name__}: {e}")
    finally:
        _trim_runs()


FORM = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>miniagent · 控制台</title>
<style>
/* 主题变量：暗色默认，亮色参考 caragent surface 分层 */
:root, html[data-theme="dark"]{
  --bg:#0f1419;--panel:#141b22;--panel2:#1a222b;--line:#2b3744;--ink:#d7e0e8;--dim:#8b9aab;
  --blue:#4fb3ff;--green:#3fd68f;--amber:#e5c07b;--red:#ff6b6b;--purple:#b280ff;
  --code-bg:#0a0e12;--user-bg:#1d2b3a;--user-line:#2a4a6b;--bot-bg:#17251c;--bot-line:#2b4a36;
  --err-bg:#2b1a1a;--err-line:#5a2b2b;--out-bg:#0d1410;--accent-soft:rgba(79,179,255,.14);
  --btn-ink:#06121c;--shadow:none}
html[data-theme="light"]{
  --bg:#f3f6fa;--panel:#ffffff;--panel2:#eef2f7;--line:#d7dfe9;--ink:#1a2430;--dim:#5b6b7d;
  --blue:#2f6fd6;--green:#1e9e6a;--amber:#b07d1e;--red:#d0483d;--purple:#7a4fb3;
  --code-bg:#f6f8fb;--user-bg:#d8e6fb;--user-line:#b7cdf0;--bot-bg:#e9f7ef;--bot-line:#bfe5cf;
  --err-bg:#fbe3e1;--err-line:#efb6b0;--out-bg:#eef7f1;--accent-soft:rgba(47,111,214,.12);
  --btn-ink:#ffffff;--shadow:0 2px 10px rgba(20,40,70,.08)}
*{scrollbar-width:thin;scrollbar-color:var(--line) transparent}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.65 "Microsoft YaHei",system-ui,sans-serif;transition:background .2s,color .2s}
.wrap{max-width:1500px;margin:0 auto;padding:16px 18px 50px}
/* ---- 顶栏 ---- */
header{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:8px 14px;background:var(--panel);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow)}
header h1{color:var(--ink);font-size:17px;margin:0;letter-spacing:.3px}
header .sub{color:var(--dim);font-size:11.5px}
header .spacer{flex:1}
.hstat{display:flex;gap:14px;font-size:11.5px;color:var(--dim)}
.hstat b{color:var(--ink);font-weight:600}
.icon-btn{background:transparent;border:1px solid var(--line);color:var(--ink);border-radius:8px;width:32px;height:32px;font-size:15px;line-height:1;cursor:pointer;padding:0;transition:border-color .15s}
.icon-btn:hover{border-color:var(--blue)}
/* ---- 布局 ---- */
.layout{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1.45fr) 240px;gap:14px;margin-top:14px;align-items:start}
@media(max-width:1200px){.layout{grid-template-columns:minmax(0,1fr) minmax(0,1.3fr)}.rcol{grid-column:1/-1;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}
@media(max-width:860px){.layout{grid-template-columns:1fr}.rcol{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:13px 15px;box-shadow:var(--shadow)}
.panel h3{color:var(--ink);font-size:12.5px;margin:0 0 9px;letter-spacing:.6px;display:flex;justify-content:space-between;align-items:center;gap:6px;flex-wrap:wrap}
.panel h3 .pill{font-size:10.5px;color:var(--dim);font-weight:400}
textarea{width:100%;min-height:76px;background:var(--code-bg);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:10px 11px;font:13.5px/1.55 Consolas,monospace;box-sizing:border-box;resize:vertical;outline:none;transition:border-color .15s}
textarea:focus{border-color:var(--blue)}
button{background:var(--blue);color:var(--btn-ink);border:none;border-radius:8px;padding:7px 20px;font-size:13px;font-weight:700;cursor:pointer;transition:filter .15s}
button:hover:not(:disabled):not(.icon-btn):not(.ghost){filter:brightness(1.12)}
button:disabled{background:var(--line);color:var(--dim);cursor:not-allowed}
button.ghost{background:transparent;border:1px solid var(--line);color:var(--dim);padding:3px 10px;font-size:11px;font-weight:400;border-radius:6px}
button.ghost:hover:not(:disabled){border-color:var(--blue);color:var(--blue);filter:none}
button.ghost.on{border-color:var(--green);color:var(--green)}
.row{display:flex;gap:7px;margin-top:9px;align-items:center;flex-wrap:wrap}
/* ---- 对话 ---- */
.chat{overflow-y:auto;padding:2px;min-height:230px;max-height:52vh}
.msg{border-radius:10px;padding:9px 12px;margin:7px 0;white-space:pre-wrap;word-break:break-word;line-height:1.6;font-size:13.5px}
.msg.user{background:var(--user-bg);border:1px solid var(--user-line)}
.msg.assistant{background:var(--bot-bg);border:1px solid var(--bot-line)}
.msg.assistant.done{border-color:var(--green)}
.msg.err{background:var(--err-bg);border:1px solid var(--err-line);color:var(--red)}
.usage{color:var(--green);font-size:11px;margin-top:4px}
.turn-sep{display:flex;align-items:center;gap:10px;color:var(--dim);font-size:10.5px;margin:11px 0 3px}
.turn-sep::before,.turn-sep::after{content:"";flex:1;height:1px;background:var(--line)}
/* ---- 流程步进条（caragent wf-flow 同款思路）---- */
#flow{display:flex;align-items:stretch;overflow-x:auto;padding:1px 0 5px;gap:0}
.wf-node{position:relative;min-width:86px;flex:1;padding:5px 8px 5px 20px;font-size:10.5px;color:var(--dim);border:1px solid transparent;border-radius:7px;white-space:nowrap}
.wf-node small{display:block;font-size:9.5px;opacity:.8;margin-top:1px}
.wf-node::before{content:"";position:absolute;left:7px;top:9px;width:7px;height:7px;border-radius:50%;background:var(--line)}
.wf-node:not(:last-child)::after{content:"";position:absolute;top:12px;left:calc(100% - 5px);width:10px;height:1px;background:var(--line);z-index:1}
.wf-node.active{color:var(--blue);background:var(--accent-soft);border-color:var(--blue);font-weight:600}
.wf-node.active::before{background:var(--blue);box-shadow:0 0 0 4px var(--accent-soft);animation:wfp 1.2s infinite}
.wf-node.done{color:var(--ink)}
.wf-node.done::before{background:var(--green)}
@keyframes wfp{50%{opacity:.4}}
/* ---- 日志系统：tabs + 工具栏 + 视图 ---- */
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin-bottom:8px;flex-wrap:wrap}
.tab{background:transparent;border:none;border-radius:7px 7px 0 0;padding:5px 13px;font-size:12px;font-weight:600;color:var(--dim);cursor:pointer;box-shadow:none!important;filter:none!important}
.tab:hover{color:var(--blue)}
.tab.on{color:var(--blue);border-bottom:2px solid var(--blue);background:var(--accent-soft)}
.tab .cnt{font-size:10px;color:var(--dim);margin-left:4px;font-weight:400}
.logbar{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:7px}
.logbar input{background:var(--code-bg);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:4px 9px;font-size:11.5px;outline:none;width:150px;transition:border-color .15s}
.logbar input:focus{border-color:var(--blue)}
#logbox{display:flex;flex-direction:column;flex:none;min-height:190px;height:380px;border:1px solid var(--line);border-radius:8px;background:var(--code-bg);overflow:hidden;transition:border-color .15s;position:relative}
#logbox.resizing{border-color:var(--blue);user-select:none}
.view{flex:1;overflow-y:auto;display:none;padding:8px 10px;font:12px/1.6 Consolas,"Courier New",monospace;white-space:pre-wrap;word-break:break-word}
.view.on{display:block}
.grip{height:7px;margin:5px -5px 0;border-radius:4px;cursor:ns-resize;position:relative;flex:none}
.grip::after{content:"";position:absolute;left:50%;top:2px;transform:translateX(-50%);width:44px;height:3px;border-radius:2px;background:var(--line);transition:background .15s}
.grip:hover::after{background:var(--blue)}
/* 事件条目（可点击展开原始 JSON）*/
.ev{margin:3px 0;padding-left:9px;border-left:2px solid var(--line);color:var(--dim);cursor:pointer;border-radius:0 5px 5px 0}
.ev:hover{background:var(--accent-soft)}
.ev .t{opacity:.7}
.ev b{color:var(--ink);font-weight:600}
.ev .ms{color:var(--amber);font-size:10.5px}
.ev .st{opacity:.75;font-size:10px}
.ev .detail{color:var(--dim);font-size:11px;margin:2px 0 0 0;white-space:pre-wrap}
.ev .out{color:var(--green);background:var(--out-bg);border-radius:5px;padding:4px 7px;margin-top:3px;font-size:11px;max-height:150px;overflow-y:auto;white-space:pre-wrap}
.ev .raw{display:none;margin-top:4px;background:var(--panel2);border:1px solid var(--line);border-radius:5px;padding:6px;font-size:10.5px;color:var(--dim);max-height:220px;overflow:auto;white-space:pre}
.ev.open .raw{display:block}
.ev.llm{border-left-color:var(--blue)}.ev.llm b{color:var(--blue)}
.ev.tool_start{border-left-color:var(--amber)}.ev.tool_start b{color:var(--amber)}
.ev.tool_end{border-left-color:var(--green)}.ev.tool_end b{color:var(--green)}
.ev.tool_end.fail{border-left-color:var(--red)}.ev.tool_end.fail b{color:var(--red)}
.ev.error,.ev.llm_error{border-left-color:var(--red);color:var(--red)}
.ev.session_start,.ev.session_end{border-left-color:var(--purple)}.ev.session_start b,.ev.session_end b{color:var(--purple)}
.ev.session_bound{border-left-color:var(--blue);opacity:.85}
/* 时间线视图 */
.tl-row{display:flex;gap:8px;align-items:baseline;margin:2px 0;font-size:11.5px}
.tl-bar{height:12px;border-radius:3px;background:var(--blue);opacity:.75;min-width:2px;display:inline-block;vertical-align:middle}
.tl-row.g .tl-bar{background:var(--green)}.tl-row.a .tl-bar{background:var(--amber)}
.tl-lab{color:var(--dim);width:210px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:none}
.tl-ms{color:var(--ink);width:52px;text-align:right;flex:none;font-size:11px}
/* 统计视图 */
.stt{display:grid;grid-template-columns:repeat(auto-fill,minmax(128px,1fr));gap:8px;padding:4px}
.stt .kpi{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:8px 10px}
.stt .kpi .v{font-size:17px;font-weight:700;color:var(--ink)}
.stt .kpi .l{font-size:10.5px;color:var(--dim)}
.stt .bar{height:5px;border-radius:3px;background:var(--line);margin-top:6px;overflow:hidden}
.stt .bar i{display:block;height:100%;background:var(--blue)}
.tchips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.tchip{background:var(--panel2);border:1px solid var(--line);border-radius:14px;padding:2px 10px;font-size:11px;color:var(--dim)}
.tchip b{color:var(--amber);font-weight:600}
/* 右栏状态卡 */
.kv{display:flex;justify-content:space-between;gap:8px;font-size:11.5px;padding:3px 0;border-bottom:1px dashed var(--line)}
.kv:last-child{border-bottom:none}
.kv .k{color:var(--dim)}
.kv .v{color:var(--ink);text-align:right;max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.kv .v.ok{color:var(--green)}.kv .v.err{color:var(--red)}
.rcol .panel{margin-bottom:0}
#lasterr .txt{font-size:11px;color:var(--red);white-space:pre-wrap;word-break:break-word}
/* 状态点 */
.status{font-size:11.5px;color:var(--dim)}
.status .dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--dim);margin-right:5px;vertical-align:middle}
.status.running .dot{background:var(--amber);animation:pulse 1s infinite}
.status.done .dot{background:var(--green)}
.status.error .dot{background:var(--red)}
@keyframes pulse{50%{opacity:.3}}
.empty{color:var(--dim);font-size:11.5px;padding:6px 2px;opacity:.8}
#newmsg{position:absolute;right:14px;bottom:10px;background:var(--blue);color:var(--btn-ink);border:none;border-radius:14px;padding:3px 13px;font-size:11px;font-weight:700;cursor:pointer;display:none;box-shadow:0 2px 10px rgba(0,0,0,.35)}
.kbd{background:var(--code-bg);border:1px solid var(--line);border-radius:4px;padding:0 5px;font-size:10px;color:var(--dim)}
</style></head><body><div class="wrap">
<header>
  <h1>miniagent 控制台</h1>
  <span class="sub">qwen3.7-max · 多轮连续 · 全过程可观测</span>
  <span class="spacer"></span>
  <span class="hstat" id="hstat">
    <span>会话 <b id="h-sess">—</b></span>
    <span>轮次 <b id="h-turn">0</b></span>
    <span>tokens <b id="h-tok">0</b></span>
    <span>LLM <b id="h-calls">0</b></span>
    <span>工具 <b id="h-tools">0</b></span>
  </span>
  <button id="theme-toggle" class="icon-btn" title="切换亮/暗主题">🌙</button>
</header>
<div class="layout">
  <!-- 左:对话 -->
  <div class="panel lcol">
    <h3>对话 <span class="pill" id="sessinfo">新会话</span><span class="pill"><span class="kbd">Ctrl</span>+<span class="kbd">Enter</span></span></h3>
    <textarea id="t" placeholder="例如:创建 fib.py 实现斐波那契并写 unittest 跑通&#10;完成后继续追问:改成返回前 n 项列表（同会话记得上文与文件）"></textarea>
    <div class="row">
      <button id="go" onclick="run()">发送</button>
      <button class="ghost" onclick="newSession()">⊕ 新会话</button>
      <button class="ghost" onclick="clearChat()">清空显示</button>
      <span class="status" id="status"><span class="dot"></span>空闲</span>
    </div>
    <div class="chat" id="chat" style="margin-top:8px"><div class="empty">尚无对话。左下状态卡实时更新;右侧日志系统全程观测。</div></div>
  </div>
  <!-- 中:日志系统 -->
  <div class="panel mcol">
    <h3>执行日志 <span class="pill" id="runinfo">—</span></h3>
    <div id="flow"></div>
    <div class="tabs">
      <button class="tab on" data-v="stream" onclick="switchTab('stream')">执行流<span class="cnt" id="c-stream">0</span></button>
      <button class="tab" data-v="timeline" onclick="switchTab('timeline')">时间线<span class="cnt" id="c-timeline">0</span></button>
      <button class="tab" data-v="stats" onclick="switchTab('stats')">统计<span class="cnt" id="c-stats">0</span></button>
      <button class="tab" data-v="raw" onclick="switchTab('raw')">原始事件<span class="cnt" id="c-raw">0</span></button>
    </div>
    <div class="logbar">
      <input id="q" placeholder="🔍 过滤日志…" oninput="applyFilter()">
      <button class="ghost on" id="f-tool" onclick="toggleFilter('tool')">工具</button>
      <button class="ghost on" id="f-llm" onclick="toggleFilter('llm')">LLM</button>
      <button class="ghost on" id="f-other" onclick="toggleFilter('other')">其他</button>
      <span style="flex:1"></span>
      <button class="ghost on" id="f-scroll" onclick="toggleScroll()">⇩ 跟随</button>
      <button class="ghost" onclick="downloadLog()">⬇ 导出</button>
      <button class="ghost" onclick="clearLog()">清空</button>
    </div>
    <div id="logbox">
      <div class="view on" id="v-stream"><div class="empty">等待任务启动…</div></div>
      <div class="view" id="v-timeline"><div class="empty">时间线在任务运行后生成,展示每个环节耗时占比</div></div>
      <div class="view" id="v-stats"><div class="empty">统计汇总</div></div>
      <div class="view" id="v-raw"><div class="empty">原始 JSONL 事件流(与服务端 transcript 同构)</div></div>
      <button id="newmsg" onclick="resumeScroll()">↓ 新日志</button>
    </div>
    <div class="grip" id="grip" title="拖动调节高度"></div>
  </div>
  <!-- 右:状态卡 -->
  <div class="rcol">
    <div class="panel">
      <h3>会话状态</h3>
      <div class="kv"><span class="k">会话 ID</span><span class="v" id="s-sid">—</span></div>
      <div class="kv"><span class="k">轮次</span><span class="v" id="s-turn">—</span></div>
      <div class="kv"><span class="k">当前步骤</span><span class="v" id="s-step">—</span></div>
      <div class="kv"><span class="k">最后工具</span><span class="v" id="s-tool">—</span></div>
      <div class="kv"><span class="k">本轮耗时</span><span class="v" id="s-elapsed">—</span></div>
      <div class="kv"><span class="k">prompt tok</span><span class="v" id="s-pt">0</span></div>
      <div class="kv"><span class="k">completion tok</span><span class="v" id="s-ct">0</span></div>
      <div class="kv"><span class="k">LLM 调用</span><span class="v" id="s-calls">0</span></div>
      <div class="kv"><span class="k">工具调用</span><span class="v" id="s-tools">0</span></div>
      <div class="kv"><span class="k">workdir</span><span class="v" id="s-wd" title="">—</span></div>
      <div class="kv"><span class="k">状态</span><span class="v" id="s-status">空闲</span></div>
    </div>
    <div class="panel" style="margin-top:14px" id="toolpanel">
      <h3>工具分布</h3>
      <div class="empty" id="toolchips">尚无调用</div>
    </div>
    <div class="panel" style="margin-top:14px" id="lasterr">
      <h3>最近错误</h3>
      <div class="empty" id="errtxt">—</div>
    </div>
  </div>
</div>
<script>
/* ---- 主题（caragent 同款） ---- */
function applyTheme(t){document.documentElement.dataset.theme=t;
  document.getElementById('theme-toggle').textContent=t==='dark'?'🌙':'☀️';
  try{localStorage.setItem('miniagent-theme',t)}catch(_){}}
applyTheme(function(){try{return localStorage.getItem('miniagent-theme')}catch(_){return null}}()
  ||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'));
document.getElementById('theme-toggle').addEventListener('click',function(){
  applyTheme(document.documentElement.dataset.theme==='dark'?'light':'dark')});

const chat=document.getElementById('chat'),status=document.getElementById('status');
const views={stream:document.getElementById('v-stream'),timeline:document.getElementById('v-timeline'),
  stats:document.getElementById('v-stats'),raw:document.getElementById('v-raw')};
const filters={tool:true,llm:true,other:true};
let autoScroll=true,running=false,sessionId='',turn=0,timer=null,t0=null;
let events=[],llmCount=0,toolCount=0,toolUse={},promptTok=0,compTok=0;

function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;')}
function ts(t){const d=new Date((t||Date.now()/1000)*1000);return d.toTimeString().slice(0,8)}
function ms(sec){return sec>=1?sec.toFixed(1)+'s':Math.round(sec*1000)+'ms'}
function base(w){return String(w||'').split(/[\\\\/]/).pop()}
function $(id){return document.getElementById(id)}
function setStatus(cls,txt){status.className='status '+cls;status.innerHTML='<span class="dot"></span>'+txt}
function addChat(role,html,extra){const d=document.createElement('div');d.className='msg '+role;
  d.innerHTML=html+(extra?`<div class="usage">${extra}</div>`:'');chat.appendChild(d);chat.scrollTop=chat.scrollHeight}
function addTurnSep(n){const s=document.createElement('div');s.className='turn-sep';s.textContent='第 '+n+' 轮';chat.appendChild(s)}
function newSession(){if(running)return;sessionId='';turn=0;events=[];llmCount=0;toolCount=0;toolUse={};promptTok=0;compTok=0;
  chat.innerHTML='<div class="empty">已开新会话。</div>';clearLog();updHdr();updStats();
  $('sessinfo').textContent='新会话';$('runinfo').textContent='—';$('s-sid').textContent='—';setStatus('','空闲')}
function clearChat(){chat.innerHTML='<div class="empty">已清空显示(日志与状态保留)</div>'}

/* ---- tabs / 过滤 / 跟随 / 导出 ---- */
let curTab='stream';
function switchTab(v){curTab=v;document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('on',b.dataset.v===v));
  Object.entries(views).forEach(([k,el])=>el.classList.toggle('on',k===v));renderView()}
function toggleFilter(k){filters[k]=!filters[k];const b=$('f-'+k);b.classList.toggle('on',filters[k]);renderStream()}
function pass(kind){if(kind==='tool_start'||kind==='tool_end'||kind==='error')return filters.tool;
  if(kind==='llm'||kind==='llm_error')return filters.llm;return filters.other}
function applyFilter(){renderStream();renderTimeline();renderRaw()}
function matchQ(el){const q=$('q').value.trim().toLowerCase();
  return !q||el.textContent.toLowerCase().includes(q)}
function toggleScroll(){autoScroll=!autoScroll;const b=$('f-scroll');
  b.textContent=autoScroll?'⇩ 跟随':'❚❚ 暂停';b.classList.toggle('on',autoScroll);$('newmsg').style.display='none'}
function resumeScroll(){autoScroll=true;const b=$('f-scroll');b.textContent='⇩ 跟随';b.classList.add('on');
  $('newmsg').style.display='none';const v=views[curTab];if(v)v.scrollTop=v.scrollHeight}
function scrollCur(){const v=views[curTab];if(!v)return;
  if(autoScroll){v.scrollTop=v.scrollHeight;$('newmsg').style.display='none'}else $('newmsg').style.display='block'}
views.stream.addEventListener('scroll',()=>{if(views.stream.scrollHeight-views.stream.scrollTop-views.stream.clientHeight<24&&!autoScroll)resumeScroll()});
function clearLog(){Object.values(views).forEach(v=>v.innerHTML='<div class="empty">已清空(新事件继续追加)</div>');
  events=[];renderView()}
function downloadLog(){const blob=new Blob([events.map(e=>JSON.stringify(e)).join('\\n')],{type:'application/x-ndjson'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download='miniagent_events_'+new Date().toISOString().replace(/[:.]/g,'-')+'.jsonl';a.click()}

/* ---- 拖拽调高 ---- */
(function(){const grip=$('grip'),box=$('logbox');let sy=0,sh=0,on=false;
  grip.addEventListener('pointerdown',e=>{on=true;sy=e.clientY;sh=box.offsetHeight;
    box.classList.add('resizing');grip.setPointerCapture(e.pointerId);e.preventDefault()});
  grip.addEventListener('pointermove',e=>{if(!on)return;
    box.style.height=Math.min(Math.max(sh+(sy-e.clientY),150),window.innerHeight*0.8)+'px'});
  function fin(e){if(!on)return;on=false;box.classList.remove('resizing');
    try{localStorage.setItem('miniagent.logH',box.offsetHeight)}catch(_){}}
  grip.addEventListener('pointerup',fin);grip.addEventListener('pointercancel',fin);
  try{const h=localStorage.getItem('miniagent.logH');if(h)box.style.height=Math.min(+h,window.innerHeight*0.8)+'px'}catch(_){}})();

/* ---- 流程步进条 ---- */
const FLOW=['接收任务','LLM 推理','工具执行','循环…','完成'];
function renderFlow(cur){const f=$('flow');f.innerHTML='';
  FLOW.forEach((n,i)=>{const d=document.createElement('div');
    d.className='wf-node'+(i<cur?' done':i===cur?' active':'');
    d.innerHTML=esc(n)+'<small>'+(i<cur?'✓':i===cur?'…':'')+'</small>';f.appendChild(d)})}

/* ---- 事件渲染 ---- */
function evNode(ev){
  const d=document.createElement('div');d.className='ev '+ev.type;d.dataset.kind=ev.type;
  const T=`<span class="t">${ts(ev.ts)}</span> `,S=ev.step?`<span class="st">#${ev.step}</span> `:'';
  let body='';
  if(ev.type==='session_start'){const tag=ev.turn>1?`继续 · 第 ${ev.turn} 轮`:'任务启动';
    body=`<b>▶ ${tag}</b> workdir=${esc(base(ev.workdir))}\\n<div class="detail">任务: ${esc(ev.task)}</div>`}
  else if(ev.type==='llm'){body=`<b>LLM 推理</b> <span class="ms">${ms(ev.elapsed)}</span> · ${ev.msg_count} msgs · ctx≈${ev.est_ctx_tokens}tok\\n<div class="detail">↑${ev.prompt_tokens} · ↓${ev.completion_tokens} tok${ev.tool_calls.length?'\\n→ 调用: '+ev.tool_calls.join(', '):'\\n→ 最终回答'}${ev.content_preview?'\\n💭 '+esc(ev.content_preview):''}</div>`}
  else if(ev.type==='llm_error'){body=`<b>LLM 失败</b> <span class="ms">${ms(ev.elapsed)}</span>\\n<div class="detail">${esc(ev.error)}</div>`}
  else if(ev.type==='tool_start'){body=`<b>⚙ ${esc(ev.tool)}</b>\\n<div class="detail">${esc(ev.preview)}</div>`}
  else if(ev.type==='tool_end'){d.className='ev tool_end'+(ev.ok?'':' fail');
    body=`<b>⚙ ${esc(ev.tool)} ${ev.ok?'✓':'✗'}</b> ${ev.result_len} 字符\\n${ev.result_preview?`<div class="out">${esc(ev.result_preview)}</div>`:''}`}
  else if(ev.type==='session_end'){body=`<b>■ 本轮完成</b> ${ev.steps} 步`}
  else if(ev.type==='session_bound'){body=`<b>⇄ 会话 ${ev.session_id} 已建立</b>（后续轮次复用）`}
  else if(ev.type==='end'){const u=ev.usage||{};
    body=`<b>■■ [${ev.status}] 结束</b> 本轮 ${ms(ev.elapsed)}\\n<div class="detail">累计 ↑${u.prompt_tokens||0} + ↓${u.completion_tokens||0} tok · LLM ${u.calls||0} 次</div>`}
  else{body=`<b>${esc(ev.type)}</b>`}
  d.innerHTML=T+S+body+`<div class="raw">${esc(JSON.stringify(ev,null,1))}</div>`;
  d.addEventListener('click',()=>d.classList.toggle('open'));
  return d;
}
function renderStream(){const v=views.stream;v.innerHTML='';
  const q=$('q').value.trim().toLowerCase();
  let shown=0;
  for(const ev of events){if(!pass(ev.type))continue;
    const n=evNode(ev);if(q&&!n.textContent.toLowerCase().includes(q)){continue}
    v.appendChild(n);shown++}
  if(!shown)v.innerHTML='<div class="empty">无匹配事件</div>';scrollCur()}
function renderTimeline(){const v=views.timeline;const q=$('q').value.trim().toLowerCase();
  const items=events.filter(e=>['llm','tool_end','end'].includes(e.type)
    &&(!q||JSON.stringify(e).toLowerCase().includes(q)));
  if(!items.length){v.innerHTML='<div class="empty">时间线在任务运行后生成</div>';return}
  const max=Math.max(...items.map(e=>e.type==='end'?e.elapsed:e.elapsed||0),0.001);
  v.innerHTML=items.map(e=>{
    const dur=e.type==='end'?e.elapsed:(e.elapsed||0);
    const lab=e.type==='llm'?`LLM #${items.filter(x=>x.type==='llm'&&x.ts<=e.ts).length} 推理`
      :e.type==='end'?'■ 本轮总计':`⚙ ${(e.tool||'?')}${e.step?' #'+e.step:''}`;
    const cls=e.type==='llm'?'':e.type==='end'?'g':'a';
    return `<div class="tl-row ${cls}"><span class="tl-lab">${esc(lab)}</span><span class="tl-bar" style="width:${Math.max(2,dur/max*280)}px"></span><span class="tl-ms">${ms(dur)}</span></div>`}).join('');}
function renderStats(){
  const tot={};for(const e of events){tot[e.type]=(tot[e.type]||0)+1}
  $('c-stream').textContent=events.length;$('c-timeline').textContent=events.filter(e=>['llm','tool_end','end'].includes(e.type)).length;
  $('c-stats').textContent=Object.keys(toolUse).length||0;$('c-raw').textContent=events.length;
  const v=views.stats;const maxT=Math.max(...Object.values(toolUse),1);
  const chips=Object.entries(toolUse).sort((a,b)=>b[1]-a[1]).map(([k,n])=>
    `<span class="tchip">${esc(k)} <b>${n}</b></span>`).join('');
  v.innerHTML=`<div class="stt">
    <div class="kpi"><div class="v">${turn}</div><div class="l">对话轮次</div></div>
    <div class="kpi"><div class="v">${llmCount}</div><div class="l">LLM 调用</div></div>
    <div class="kpi"><div class="v">${toolCount}</div><div class="l">工具调用</div></div>
    <div class="kpi"><div class="v">${(promptTok/1000).toFixed(1)}k</div><div class="l">prompt tok</div></div>
    <div class="kpi"><div class="v">${(compTok/1000).toFixed(1)}k</div><div class="l">completion tok</div></div>
    <div class="kpi"><div class="v">${events.length}</div><div class="l">事件总数</div></div>
  </div>
  <div style="padding:8px 4px;font-size:11.5px;color:var(--dim)">按事件类型: ${Object.entries(tot).map(([k,n])=>k+' '+n).join(' · ')}</div>
  <div style="padding:0 4px 8px"><div style="font-size:11.5px;color:var(--dim);margin-bottom:4px">工具分布:</div>
  ${Object.entries(toolUse).sort((a,b)=>b[1]-a[1]).map(([k,n])=>
    `<div class="tl-row a" style="margin:2px 0"><span class="tl-lab">${esc(k)}</span><span class="tl-bar" style="width:${n/maxT*200}px"></span><span class="tl-ms">${n}</span></div>`).join('')||'<div class="empty">尚无工具调用</div>'}</div>`;
  $('toolchips').innerHTML=chips||'尚无调用';
}
function renderRaw(){const v=views.raw;const q=$('q').value.trim().toLowerCase();
  const lines=events.filter(e=>!q||JSON.stringify(e).toLowerCase().includes(q))
    .map(e=>esc(JSON.stringify(e)));
  v.innerHTML=lines.length?lines.join('\\n'):'<div class="empty">无匹配</div>'}
function renderView(){renderStream();renderTimeline();renderStats();renderRaw()}

/* ---- 状态卡/顶栏 ---- */
function updHdr(){$('h-turn').textContent=turn;$('h-tok').textContent=(promptTok+compTok).toLocaleString();
  $('h-calls').textContent=llmCount;$('h-tools').textContent=toolCount;
  $('h-sess').textContent=sessionId?sessionId.slice(0,8):'—'}
function updStats(){updHdr();
  $('s-turn').textContent=turn||'—';$('s-pt').textContent=promptTok.toLocaleString();
  $('s-ct').textContent=compTok.toLocaleString();$('s-calls').textContent=llmCount;
  $('s-tools').textContent=toolCount}
function startTimer(){t0=Date.now();clearInterval(timer);
  timer=setInterval(()=>{if(running)$('s-elapsed').textContent=ms((Date.now()-t0)/1000)},200)}
function stopTimer(){clearInterval(timer)}

/* ---- 事件入口 ---- */
function appendEv(ev){
  events.push(ev);
  const v=views.stream;const first=v.querySelector('.empty');if(first)first.remove();
  const n=evNode(ev);if(!pass(ev.type))n.style.display='none';else if($('q').value.trim()&&!matchQ(n))n.style.display='none';
  v.appendChild(n);scrollCur();
  if(ev.type==='llm'){llmCount++;promptTok+=ev.prompt_tokens||0;compTok+=ev.completion_tokens||0;
    $('s-step').textContent='LLM 推理';renderFlow(1)}
  if(ev.type==='llm_error'){$('errtxt').textContent=ts(ev.ts)+' '+ev.error}
  if(ev.type==='tool_start'){renderFlow(2);$('s-step').textContent='⚙ '+ev.tool;$('s-tool').textContent=ev.tool;
    if(ev.tool){toolUse[ev.tool]=(toolUse[ev.tool]||0)+1}}
  if(ev.type==='tool_end'){toolCount++;renderFlow(1)}
  if(ev.type==='session_start'){turn=ev.turn||1;$('runinfo').textContent=base(ev.workdir);
    $('s-wd').textContent=base(ev.workdir);$('s-wd').title=ev.workdir;
    setStatus('running','第 '+turn+' 轮运行中…');renderFlow(0);startTimer();
    if(turn>1)addTurnSep(turn);addChat('user',esc(ev.task))}
  if(ev.type==='session_bound'){sessionId=ev.session_id;
    $('sessinfo').textContent='会话 '+sessionId.slice(0,8);$('s-sid').textContent=sessionId.slice(0,10)+'…';updHdr()}
  if(ev.type==='end'){
    stopTimer();
    if(ev.status==='done'){setStatus('done','完成 · '+ms(ev.elapsed));
      addChat('assistant done',esc(ev.result||''),
        `↑${ev.usage.prompt_tokens||0}+↓${ev.usage.completion_tokens||0} tok · LLM ${ev.usage.calls||0} · 本轮 ${ms(ev.elapsed)}`)}
    else{setStatus('error','失败');addChat('err',esc(ev.error||'运行失败'));$('errtxt').textContent=ev.error||''}
    running=false;const go=$('go');go.disabled=false;go.textContent='发送';
    promptTok=ev.usage?.prompt_tokens??promptTok;compTok=ev.usage?.completion_tokens??compTok;
    llmCount=ev.usage?.calls??llmCount;renderFlow(4)}
  renderStats();
}
renderFlow(-1);

async function run(){
  if(running)return;
  const t=$('t').value.trim();if(!t)return;
  const btn=$('go');btn.disabled=true;btn.textContent='运行中…';running=true;
  setStatus('running','启动中…');renderFlow(0);
  try{
    const body={text:t};if(sessionId)body.session_id=sessionId;
    const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const d=await r.json();
    if(!d.ok){addChat('err',esc(d.error||'启动失败'));setStatus('error','启动失败');running=false;btn.disabled=false;btn.textContent='发送';return}
    const es=new EventSource('/api/stream/'+d.run_id);
    es.onmessage=e=>{const ev=JSON.parse(e.data);appendEv(ev);if(ev.type==='end')es.close()};
    es.onerror=()=>{es.close()};
  }catch(e){addChat('err','网络错误: '+esc(e));setStatus('error','网络错误');running=false;btn.disabled=false;btn.textContent='发送'}
  $('t').value='';
}
$('t').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey))run()});
</script>
</div></body></html>"""


def run_task(text: str) -> dict:
    """在独立 workdir 里跑一次 agent，收集结果/工具轨迹/用量。"""
    wd = os.path.join(WEB_ROOT, time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
                      + "-" + uuid.uuid4().hex[:6])
    os.makedirs(wd, exist_ok=True)
    agent = Agent(wd, permission_mode="auto")
    result = agent.run(text)
    tools: list[str] = []
    for e in agent.transcript.resume():
        if e.get("type") != "message":
            continue
        m = e["message"]
        if m.get("role") == "assistant":
            for tc in m.get("tool_calls") or []:
                tools.append((tc.get("function") or {}).get("name", "?"))
    return {"result": result, "usage": agent.usage,
            "tools": tools, "steps": len(tools)}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code: int, body: str,
              ctype: str = "text/html; charset=utf-8") -> None:
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code: int, obj: dict) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False),
                   "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send(200, FORM)
            return
        if self.path.startswith("/api/stream/"):
            self._handle_stream(self.path[len("/api/stream/"):])
            return
        if self.path.startswith("/api/run/"):
            with _RUNS_LOCK:
                run = _RUNS.get(self.path[len("/api/run/"):])
            self._json(200, {"ok": bool(run), **(run.summary() if run else
                                                  {"error": "run_id 不存在"})})
            return
        self._send(404, "not found", "text/plain; charset=utf-8")

    def _handle_stream(self, run_id: str) -> None:
        """SSE：先回放历史事件，再实时推增量，直到 end 事件或客户端断开。"""
        with _RUNS_LOCK:
            run = _RUNS.get(run_id)
        if run is None:
            self._json(404, {"ok": False, "error": "run_id 不存在"})
            return
        q = run.subscribe()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            import selectors
            sel = selectors.DefaultSelector()
            sel.register(self.connection, selectors.EVENT_READ)
            while True:
                try:
                    ev = q.get(timeout=5)
                except queue.Empty:
                    # 心跳保活 + 探测客户端断开
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    if sel.select(0):
                        break
                    continue
                data = json.dumps(ev, ensure_ascii=False)
                self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                self.wfile.flush()
                if ev.get("type") == "end":
                    break
                if sel.select(0):
                    break  # 客户端已断开
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            run.unsubscribe(q)

    def do_POST(self) -> None:
        if self.path == "/api/run":
            return self._handle_run()
        if self.path == "/api/new_session":
            return self._json(200, {"ok": True,
                                    "session_id": uuid.uuid4().hex[:12]})
        if self.path == "/api/query":
            return self._handle_query()
        self._send(404, "not found", "text/plain; charset=utf-8")

    def _read_text_payload(self) -> dict | None:
        """解析 {"text": ..., "session_id": ...} 请求体；非法返回 None（响应已发）。"""
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > 1_000_000:
            self._json(400, {"ok": False, "error": "请求体长度非法"})
            return None
        try:
            payload = json.loads(self.rfile.read(n).decode("utf-8"))
            payload.setdefault("text", "")
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(400, {"ok": False, "error": "请求体不是合法 JSON"})
            return None
        if not str(payload["text"]).strip():
            self._json(400, {"ok": False, "error": "任务为空"})
            return None
        return payload

    def _handle_run(self) -> None:
        """启动带日志的后台任务，立即返回 run_id；日志走 /api/stream/<id> SSE。

        请求体 {"text": ..., "session_id": ...}：带 session_id 且会话存在 →
        多轮续聊（复用 Agent，消息与 workdir 连续）；否则开新会话。
        """
        payload = self._read_text_payload()
        if payload is None:
            return
        text = str(payload["text"])
        # session_id 只接受十六进制串，防注入
        session_id = payload.get("session_id") or None
        if session_id and not re.fullmatch(r"[0-9a-f]{6,32}", str(session_id)):
            session_id = None
        turn = 1
        wd = None
        if session_id:
            with _SESSIONS_LOCK:
                entry = _SESSIONS.get(session_id)
            if entry:
                wd = entry["workdir"]  # 多轮沿用同一 workdir
        if not _sem.acquire(blocking=False):
            return self._json(429, {"ok": False,
                                    "error": "当前有任务在运行，请稍后重试（并发闸=1）"})
        try:
            if wd is None:
                wd = os.path.join(WEB_ROOT, time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
                                  + "-" + uuid.uuid4().hex[:6])
                os.makedirs(wd, exist_ok=True)
            run_id = uuid.uuid4().hex[:12]
            with _RUNS_LOCK:
                turn = (sum(1 for r in _RUNS.values()
                            if session_id and r.session_id == session_id) + 1
                        if session_id else 1)
                run = RunState(run_id, wd, text, session_id=session_id, turn=turn)
                _RUNS[run_id] = run

            def work() -> None:
                try:
                    run_task_logged(run, session_id=session_id)
                finally:
                    _sem.release()

            threading.Thread(target=work, daemon=True).start()
            self._json(200, {"ok": True, "run_id": run_id, "workdir": wd,
                             "session_id": session_id or ""})
        except Exception as e:
            _sem.release()
            self._json(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})

    def _handle_query(self) -> None:
        """旧接口：同步阻塞跑完返回（保留兼容）。"""
        payload = self._read_text_payload()
        if payload is None:
            return
        text = str(payload["text"])
        if not _sem.acquire(blocking=False):
            return self._json(429, {"ok": False,
                                    "error": "当前有任务在运行，请稍后重试（并发闸=1）"})
        box: dict = {}

        def work() -> None:
            try:
                box["r"] = run_task(text)
            except Exception as e:  # agent 内部异常不拖死服务
                box["e"] = f"{type(e).__name__}: {e}"
            finally:
                # Python 线程无法安全强杀；超时响应后仍保持占位，直到后台任务实际结束。
                _sem.release()

        t = threading.Thread(target=work, daemon=True)
        t.start()
        t.join(TASK_TIMEOUT)
        if t.is_alive():
            return self._json(504, {"ok": False,
                                    "error": f"任务超时（{TASK_TIMEOUT}s），已放弃等待"})
        if "e" in box:
            return self._json(500, {"ok": False, "error": box["e"][:500]})
        self._json(200, {"ok": True, **box["r"]})

    def log_message(self, fmt: str, *args) -> None:
        print(f"[web] {fmt % args}", file=sys.stderr)


def main() -> None:
    port = int(os.environ.get("MINIAGENT_WEB_PORT", "19120"))
    os.makedirs(WEB_ROOT, exist_ok=True)
    print(f"[web] miniagent web listening on :{port}, workroot={WEB_ROOT}",
          file=sys.stderr)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
