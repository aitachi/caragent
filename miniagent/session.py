"""JSONL transcript 会话账本（教程 Ch.9）。

消息与压缩快照 append 为 JSONL；resume 按事件重放；坏行容错跳过。
"""
from __future__ import annotations

import json
import os
import time


def new_session_path(workdir: str) -> str:
    outdir = os.path.join(workdir, ".miniagent", "sessions")
    os.makedirs(outdir, exist_ok=True)
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    # 用独占创建原子占位；并发 Agent 即使同一时刻启动也不会拿到同一路径。
    n = 1
    while True:
        suffix = "" if n == 1 else f"_{n - 1}"
        path = os.path.join(outdir, f"{ts}{suffix}.jsonl")
        try:
            with open(path, "x", encoding="utf-8"):
                pass
            return path
        except FileExistsError:
            n += 1


class Transcript:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def append(self, event: dict) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def resume(self) -> list[dict]:
        """重放全部事件；坏行跳过（容错解码）。"""
        events = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            pass
        return events

    def reconstruct_messages(self) -> list[dict]:
        """按事件顺序重建消息；压缩事件替换此前消息快照。"""
        messages: list[dict] = []
        for event in self.resume():
            if (event.get("type") == "message"
                    and isinstance(event.get("message"), dict)):
                messages.append(event["message"])
            elif (event.get("type") in ("compact", "overflow_heal")
                  and isinstance(event.get("messages"), list)
                  and all(isinstance(m, dict) for m in event["messages"])):
                messages = list(event["messages"])
        return _repair_tool_pairs(messages)


def _repair_tool_pairs(messages: list[dict]) -> list[dict]:
    """修复重放产生的孤儿协议对，防下一条 chat 直接 400。

    OpenAI 协议要求 tool 消息必须紧跟在带对应 tool_call 的 assistant 之后。
    transcript 在崩溃点截断时，可能出现：assistant(tool_calls) 已落盘但部分
    tool 结果没写（或反之）。孤儿 tool 消息 → provider 400 invalid tool message。
    策略：
    - 孤儿 tool（前一条 assistant 无匹配 tool_call_id）→ 丢弃；
    - assistant(tool_calls) 缺任一 result → 补占位 tool 结果（标注 transcript 截断）。
    """
    pending: set[str] = set()
    out: list[dict] = []
    for m in messages:
        role = m.get("role")
        if role == "assistant":
            out.append(m)
            for tc in m.get("tool_calls") or []:
                tc_id = (tc.get("id") if isinstance(tc, dict) else None) or ""
                if tc_id:
                    pending.add(tc_id)
        elif role == "tool":
            tc_id = m.get("tool_call_id") or ""
            if tc_id in pending:
                pending.discard(tc_id)
                out.append(m)
            # 孤儿 tool：静默丢弃（崩溃残留）
        else:
            out.append(m)
    # 残缺 assistant：缺的 result 补占位
    if pending:
        for tc_id in sorted(pending):
            out.append({"role": "tool", "tool_call_id": tc_id,
                        "content": "[transcript truncated: 工具结果缺失，"
                                   "请根据上下文决定是否重试]"})
    return out


DEFAULT_TTL_DAYS = 30


def cleanup_old_sessions(workdir: str, ttl_days: int = DEFAULT_TTL_DAYS) -> int:
    """会话过期策略：删除 mtime 超过 ttl_days 的 transcript（默认 30 天）。

    对应"Redis 持久化会话过期策略"的文件态答案：不引入外部存储，
    以文件 mtime 为准做 TTL 清理；返回删除数量。
    """
    outdir = os.path.join(workdir, ".miniagent", "sessions")
    if not os.path.isdir(outdir):
        return 0
    cutoff = time.time() - ttl_days * 86400
    removed = 0
    for name in os.listdir(outdir):
        if not name.endswith(".jsonl"):
            continue
        path = os.path.join(outdir, name)
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed += 1
        except OSError:
            continue
    return removed
