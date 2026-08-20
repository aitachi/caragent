"""ACP — stdio JSON-RPC 2.0 最小适配（教程 Ch.8）。

每行一个 JSON-RPC 消息；stdout 只走协议帧，一切日志走 stderr；
未知 method 显式 -32601；notification（无 id）不回复。
入口：python -m miniagent.acp
"""
from __future__ import annotations

import json
import sys
import uuid

_sessions: dict[str, object] = {}

PROTOCOL_VERSION = 1


def _log(msg: str) -> None:
    print(f"[acp] {msg}", file=sys.stderr)


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _error(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": code, "message": message}}


def _handle(msg: dict) -> dict | None:
    req_id = msg.get("id")
    method = msg.get("method", "")
    params = msg.get("params") or {}

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "agentCapabilities": {
                "loadSession": False,
                "promptCapabilities": {"text": True},
            },
        }}

    if method == "session/new":
        from .loop import Agent
        workdir = params.get("workdir") or "."
        try:
            agent = Agent(workdir)
        except Exception as e:
            return _error(req_id, -32603, f"创建会话失败: {e}")
        session_id = uuid.uuid4().hex
        _sessions[session_id] = agent
        return {"jsonrpc": "2.0", "id": req_id,
                "result": {"sessionId": session_id}}

    if method == "session/prompt":
        agent = _sessions.get(params.get("sessionId", ""))
        if agent is None:
            return _error(req_id, -32602, "未知 sessionId")
        text = params.get("text", "")
        try:
            result = agent.run(text)
        except Exception as e:
            return _error(req_id, -32603, f"prompt 执行失败: {e}")
        return {"jsonrpc": "2.0", "id": req_id,
                "result": {"stopReason": "end_turn", "text": result}}

    if req_id is None:
        return None  # notification 不回复
    return _error(req_id, -32601, f"Method not found: {method}")


def main() -> None:
    # 一切 print/日志重定向到 stderr（启动即做）：stdout 只走协议帧
    import builtins
    _orig_print = builtins.print
    builtins.print = lambda *a, **kw: _orig_print(*a, **{**kw, "file": sys.stderr})

    _log("acp 适配器已启动（stdio JSON-RPC 2.0）")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _send(_error(None, -32700, "Parse error"))
            continue
        if not isinstance(msg, dict):
            _send(_error(None, -32600, "Invalid Request"))
            continue
        try:
            resp = _handle(msg)
        except Exception as e:
            _log(f"handler 异常: {e}")
            resp = _error(msg.get("id"), -32603, str(e))
        if resp is not None:
            _send(resp)


if __name__ == "__main__":
    main()
