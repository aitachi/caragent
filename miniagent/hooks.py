"""Hooks 最小设计（教程 Ch.7）。

回调表 + 阻断语义（只有 before_tool / stop 可阻断）；
进程外 hook 子进程 30s 超时强杀，崩溃只记 stderr；
stop 阻断一次性闩锁防 turn 永不结束。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

EVENTS = ("session_start", "session_end", "before_tool", "after_tool", "stop")
BLOCKABLE = ("before_tool", "stop")

HOOK_TIMEOUT = 30

class HookManager:
    """单个 Agent 的 hook 注册表与外部目录快照。"""

    def __init__(self, registry: dict[str, list] | None = None,
                 external_dirs: list[str] | None = None):
        source = registry or {e: [] for e in EVENTS}
        self.registry = {e: list(source.get(e, [])) for e in EVENTS}
        self.external_dirs = list(external_dirs or [])

    def clone(self) -> "HookManager":
        return HookManager(self.registry, self.external_dirs)

    def on(self, event: str, fn) -> None:
        if event not in self.registry:
            raise ValueError(f"未知事件 {event!r}，可选: {EVENTS}")
        self.registry[event].append(fn)

    def clear(self) -> None:
        for event in self.registry:
            self.registry[event] = []
        self.external_dirs = []

    def register_external_dirs(self, *dirs: str) -> None:
        for directory in dirs:
            if directory not in self.external_dirs:
                self.external_dirs.append(directory)

    def external_hooks(self, event: str) -> list[str]:
        found = []
        for directory in self.external_dirs:
            if not os.path.isdir(directory):
                continue
            for fn in sorted(os.listdir(directory)):
                stem, ext = os.path.splitext(fn)
                if ext not in (".py", ".sh"):
                    continue
                if not (stem.startswith(event + "_") or stem.endswith("_" + event)):
                    continue
                path = os.path.join(directory, fn)
                if os.path.isfile(path):
                    found.append(path)
        return found

    def fire(self, event: str, payload: dict) -> str | None:
        if event not in self.registry:
            raise ValueError(f"未知事件 {event!r}")
        blockable = event in BLOCKABLE

        for fn in list(self.registry[event]):
            try:
                result = fn(payload)
            except Exception as e:
                print(f"[hooks] 进程内 hook 异常（{event}）: {e}", file=sys.stderr)
                continue
            if blockable and isinstance(result, str) and result.startswith("block:"):
                return result

        for path in self.external_hooks(event):
            reason = _run_external(path, payload)
            if blockable and reason:
                return f"block: {reason}"
        return None


_default_manager = HookManager()


def on(event: str, fn) -> None:
    """进程内注册。"""
    _default_manager.on(event, fn)


def clear() -> None:
    _default_manager.clear()


def register_external_dirs(*dirs: str) -> None:
    """注册进程外 hook 扫描目录（<workdir>/.miniagent/hooks.d、项目 hooks.d）。"""
    _default_manager.register_external_dirs(*dirs)


def new_manager() -> HookManager:
    """复制全局配置，后续注册只影响当前 Agent。"""
    return _default_manager.clone()


def _external_hooks(event: str) -> list[str]:
    """文件名以 <event>_ 开头或以 _<event> 结尾的 .py/.sh 挂到对应事件。

    兼容两种命名：before_tool_xxx.py 与 example_before_tool.py。
    """
    return _default_manager.external_hooks(event)


def _run_external(path: str, payload: dict) -> str | None:
    """stdin 传 JSON payload；stdout 解析 {"decision":"block","reason":...}。"""
    if path.endswith(".py"):
        cmd = [sys.executable, path]
    else:
        cmd = ["bash", path]
    import os
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        proc = subprocess.run(
            cmd, input=json.dumps(payload, ensure_ascii=False),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
            timeout=HOOK_TIMEOUT, env=env,
        )
    except subprocess.TimeoutExpired:
        print(f"[hooks] 进程外 hook 超时 {HOOK_TIMEOUT}s 已强杀: {path}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[hooks] 进程外 hook 运行失败: {path}: {e}", file=sys.stderr)
        return None
    if proc.returncode != 0:
        print(f"[hooks] 进程外 hook 退出码 {proc.returncode}: {path}: "
              f"{(proc.stderr or '')[:300]}", file=sys.stderr)
        return None
    out = (proc.stdout or "").strip()
    if not out:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and data.get("decision") == "block":
        return str(data.get("reason") or "进程外 hook 阻断")
    return None


def fire(event: str, payload: dict) -> str | None:
    """触发事件。只有 before_tool / stop 的返回值被解释为阻断。"""
    return _default_manager.fire(event, payload)


class StopLatch:
    """stop 阻断闩锁：每个 turn 只允许一次 stop 阻断续跑。"""

    def __init__(self):
        self._available = True

    def use(self) -> bool:
        """可用则消费并返回 True；已消费返回 False。"""
        if self._available:
            self._available = False
            return True
        return False
