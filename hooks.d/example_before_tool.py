"""示例进程外 hook：演示 JSON 裁决协议。

协议：stdin 收 JSON payload {"tool": ..., "args": ...}；
stdout 输出 {"decision":"block","reason":...} 即阻断该工具调用；
其他任何输出（或无输出）视为放行。
本示例阻断名为 "danger_tool" 的工具。
"""
import json
import sys

# 从 buffer 读并按 utf-8 解码，避免 Windows GBK 控制台下 sys.stdin 默认编码炸掉
payload = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))

if payload.get("tool") == "danger_tool":
    print(json.dumps({
        "decision": "block",
        "reason": "example_before_tool.py: danger_tool 被示例 hook 禁用",
    }))
