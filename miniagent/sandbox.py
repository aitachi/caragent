"""沙盒权限裁决（教程 Ch.4 最小设计）。

hardline 硬线先于一切授权（即使 yolo 也不放行）；
去混淆（NFKC + $IFS 折叠 + 去引号拼接）后匹配危险模式；
路径型内置工具 realpath 围栏在 workdir 内；未知工具 fail-closed。
注意：bash 只固定 cwd、剥离敏感环境并做规则裁决，不是 OS 级沙盒。
"""
from __future__ import annotations

import os
import re
import unicodedata

PermissionMode = str  # "ask" / "auto" / "yolo"

# 危险模式（作用于去混淆后的命令文本，大小写不敏感）
_HARDLINE_PATTERNS = [
    r"\brm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)*/\s*(;|$|\||&)",        # rm -rf /
    r"\brm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)*--no-preserve-root",    # rm --no-preserve-root
    r"\brm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)+~",                     # rm -rf ~
    r"\brm\s+(-[a-zA-Z]*[rf][a-zA-Z]*\s+)+/(etc|bin|sbin|usr|boot|var|lib|proc|sys|dev)\b",
    r"\bmkfs\b",                                                  # mkfs.*
    r"\bdd\b[^|&;]*\bof=/dev/",                                   # dd of=/dev/...
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",                  # fork bomb
    r"\b(shutdown|poweroff|halt)\b",
    r"\breboot\b",
    r"\bkill\s+-1\b",                                             # kill -1
    r"\bkill\s+-9\s+-1\b",
    r"\bchmod\s+(-[a-zA-Z]*R[a-zA-Z]*\s+)+777\s+/",               # chmod -R 777 /
    r"\.ssh/authorized_keys",                                     # 写 ssh 后门
    r">\s*/dev/sd[a-z]",                                          # 覆写裸设备
]


class SandboxError(Exception):
    pass


def _deobfuscate(command: str) -> str:
    """NFKC 归一化 + $IFS 折叠 + 去除引号拼接（r''m 类）。"""
    text = unicodedata.normalize("NFKC", command)
    text = text.replace("${IFS}", " ").replace("$IFS", " ")
    text = re.sub(r"(?<=\w)['\"]{2}(?=\w)", "", text)  # r''m -> rm, r""m -> rm
    return text


def hardline_check(tool_name: str, args: dict) -> str | None:
    """命中危险模式时返回原因，否则返回 None。"""
    if tool_name != "bash":
        return None
    command = str(args.get("command", ""))
    text = _deobfuscate(command)
    for pat in _HARDLINE_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return f"hardline: 命中危险模式 {pat!r}"
    return None


class Sandbox:
    """权限裁决 + workdir 围栏。"""

    def __init__(self, workdir: str | None = None, mode: PermissionMode | None = None,
                 ask_fn=None, known_tools: dict[str, bool] | None = None):
        self.workdir = os.path.abspath(workdir or os.environ.get("MINIAGENT_WORKDIR")
                                       or os.getcwd())
        self.mode: PermissionMode = (mode or os.environ.get("MINIAGENT_PERMISSION")
                                     or "auto")
        if self.mode not in ("ask", "auto", "yolo"):
            self.mode = "auto"
        self.ask_fn = ask_fn  # ask 模式下的回调；非交互环境默认 None
        if known_tools is None:
            # 延迟导入避免 tools -> sandbox 的模块加载环；只保留一个注册事实源。
            from .tools import REGISTRY
            known_tools = {name: bool(spec["readonly"])
                           for name, spec in REGISTRY.items()}
        self.known_tools = dict(known_tools)

    def approve(self, tool_name: str, args: dict, readonly: bool) -> tuple[bool, str]:
        """返回 (allowed, reason)。hardline 检查最先，即使 yolo 也不可放行。"""
        reason = hardline_check(tool_name, args)
        if reason:
            return False, reason

        if tool_name not in self.known_tools:
            return False, f"fail-closed: 未知工具 {tool_name!r}"

        # readonly 以注册表快照为准，调用方不能用参数把写工具伪装成只读。
        if self.known_tools[tool_name]:
            return True, "readonly 默认放行"

        if self.mode in ("yolo", "auto"):
            return True, f"{self.mode} 模式放行"

        # ask 模式
        if self.ask_fn is None:
            return False, "ask 模式但无交互回调（非交互环境默认拒绝）"
        try:
            return bool(self.ask_fn(tool_name, args)), "ask 模式用户裁决"
        except Exception as e:  # fail-closed
            return False, f"ask 回调异常，默认拒绝: {e}"

    def guard_path(self, path: str) -> str:
        """解析为绝对路径，必须在 workdir 内，否则 raise SandboxError。"""
        abs_path = os.path.abspath(os.path.join(self.workdir, path))
        real_workdir = os.path.realpath(self.workdir)
        real_path = os.path.realpath(abs_path)
        try:
            inside = os.path.commonpath([real_path, real_workdir]) == real_workdir
        except ValueError:  # 不同盘符（Windows）
            inside = False
        if not inside:
            raise SandboxError(f"路径越出 workdir 围栏: {path!r}")
        return abs_path


def sanitized_env() -> dict:
    """剥除含 TOKEN/KEY/PASSWORD/SECRET/CREDENTIAL 的环境变量（含 MINIAGENT_API_KEY）。"""
    bad = ("TOKEN", "KEY", "PASSWORD", "SECRET", "CREDENTIAL")
    return {k: v for k, v in os.environ.items()
            if not any(b in k.upper() for b in bad)}
