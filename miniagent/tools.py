"""实例级工具运行时 + 内置 11 工具（教程 Ch.3 最小设计）。

schema+handler 字典注册表；每个 Agent 冻结 ToolRuntime 快照；execute 做参数校验；
结果超 50K 字符全量落盘，只回 2K preview + 路径。
execute() 本身不做权限判断（权限在 loop 里经 sandbox 裁决）。
"""
from __future__ import annotations

import fnmatch
import contextvars
import os
import re
import subprocess
import time
import uuid

from . import sandbox as _sandbox_mod

REGISTRY: dict[str, dict] = {}

RESULT_LIMIT = 50_000
PREVIEW_LEN = 2_000


def tool(name: str, description: str, schema: dict, readonly: bool = False):
    """注册工具。注册必须发生在 Agent 创建前，重复名直接报错。"""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"非法工具名: {name!r}")
    if name in REGISTRY:
        raise ValueError(f"工具已注册: {name!r}")
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise ValueError(f"工具 {name!r} 的 schema 必须是 object")

    def deco(fn):
        REGISTRY[name] = {
            "name": name,
            "description": description,
            "schema": schema,
            "handler": fn,
            "readonly": readonly,
        }
        return fn
    return deco


def schemas_for_llm() -> list[dict]:
    return _default().schemas_for_llm()


# ---- Agent 实例级运行时；模块级 facade 仅保留向后兼容 ----

_active_runtime: contextvars.ContextVar["ToolRuntime | None"] = (
    contextvars.ContextVar("miniagent_tool_runtime", default=None)
)
_default_runtime: "ToolRuntime | None" = None


class ToolRuntime:
    """工具注册表快照 + 当前 Agent 的 sandbox/skills/memory 绑定。

    注册表在构造时复制，避免运行中新增工具改变既有会话的 schema；
    ContextVar 只在 handler 调用期间暴露当前实例，因此线程/子代理不会串绑。
    """

    def __init__(self, sandbox=None, skills=None, memory=None, registry=None):
        self.sandbox = sandbox
        self.skills = skills
        self.memory = memory
        source = REGISTRY if registry is None else registry
        self.registry = {name: dict(spec) for name, spec in source.items()}

    def schemas_for_llm(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["schema"],
                },
            }
            for t in self.registry.values()
        ]

    def readonly_map(self) -> dict[str, bool]:
        return {name: bool(spec["readonly"])
                for name, spec in self.registry.items()}

    def get(self, name: str) -> dict | None:
        return self.registry.get(name)

    def validate(self, name: str, args: dict) -> str | None:
        spec = self.registry.get(name)
        if spec is None:
            return f"error: 未知工具 {name!r}"
        if not isinstance(args, dict):
            return "error: arguments 必须是对象"
        schema = spec["schema"]
        for req in schema.get("required", []):
            if req not in args:
                return f"error: 缺少必填参数 {req!r}"
        props = schema.get("properties", {})
        for key, val in args.items():
            if key not in props:
                return f"error: 未声明参数 {key!r}"
            expect = (props.get(key) or {}).get("type")
            if expect == "string" and not isinstance(val, str):
                return f"error: 参数 {key!r} 应为 string"
            if expect == "integer" and (not isinstance(val, int) or isinstance(val, bool)):
                return f"error: 参数 {key!r} 应为 integer"
        return None

    def execute(self, name: str, args: dict) -> str:
        error = self.validate(name, args)
        if error:
            return error
        spec = self.registry[name]
        token = _active_runtime.set(self)
        try:
            result = spec["handler"](**args)
        except Exception as e:
            return f"error: {type(e).__name__}: {e}"
        finally:
            _active_runtime.reset(token)
        return _govern(str(result), name, self)


def _default() -> ToolRuntime:
    global _default_runtime
    if _default_runtime is None:
        _default_runtime = ToolRuntime()
    return _default_runtime


def bind(sandbox=None, skills=None, memory=None):
    """配置模块级兼容 runtime；新代码应由 Agent 持有 ToolRuntime。"""
    global _default_runtime
    current = _default()
    _default_runtime = ToolRuntime(
        sandbox=sandbox if sandbox is not None else current.sandbox,
        skills=skills if skills is not None else current.skills,
        memory=memory if memory is not None else current.memory,
    )


def _runtime() -> ToolRuntime:
    return _active_runtime.get() or _default()


def _workdir() -> str:
    runtime = _runtime()
    if runtime.sandbox is not None:
        return runtime.sandbox.workdir
    return os.path.abspath(os.environ.get("MINIAGENT_WORKDIR") or os.getcwd())


def _resolve(path: str) -> str:
    """解析路径；所有内置路径型工具都强制 workdir 围栏。"""
    runtime = _runtime()
    if runtime.sandbox is not None:
        return runtime.sandbox.guard_path(path)
    p = path if os.path.isabs(path) else os.path.join(_workdir(), path)
    return os.path.abspath(p)


def _govern(result: str, name: str, runtime: ToolRuntime | None = None) -> str:
    """结果治理：超长全量落盘，返回 preview + 路径说明。"""
    if len(result) <= RESULT_LIMIT:
        return result
    runtime = runtime or _runtime()
    workdir = (runtime.sandbox.workdir if runtime.sandbox is not None
               else _workdir())
    outdir = os.path.join(workdir, ".miniagent", "tool_results")
    os.makedirs(outdir, exist_ok=True)
    fname = (f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}_"
             f"{uuid.uuid4().hex[:12]}_{name}.txt")
    fpath = os.path.join(outdir, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(result)
    return (result[:PREVIEW_LEN]
            + f"\n\n...[输出共 {len(result)} 字符，已截断；全量已落盘: {fpath}]")


def execute(name: str, args: dict) -> str:
    """模块级兼容入口。异常不外抛。"""
    return _default().execute(name, args)


# ---------------- 内置 11 工具 ----------------

@tool("read_file", "读取文件内容（带行号）。", {
    "type": "object",
    "properties": {"path": {"type": "string", "description": "文件路径（相对 workdir 或绝对）"}},
    "required": ["path"],
}, readonly=True)
def read_file(path: str) -> str:
    p = _resolve(path)
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return "".join(f"{i+1}\t{line}" for i, line in enumerate(lines))


@tool("list_dir", "列出目录内容。", {
    "type": "object",
    "properties": {"path": {"type": "string", "description": "目录路径"}},
    "required": ["path"],
}, readonly=True)
def list_dir(path: str) -> str:
    p = _resolve(path)
    entries = sorted(os.listdir(p))
    return "\n".join(entries) if entries else "(空目录)"


@tool("grep", "用正则递归搜索文件内容（限 200 行）。", {
    "type": "object",
    "properties": {
        "pattern": {"type": "string", "description": "正则表达式"},
        "path": {"type": "string", "description": "搜索起点目录或文件"},
    },
    "required": ["pattern", "path"],
}, readonly=True)
def grep(pattern: str, path: str) -> str:
    p = _resolve(path)
    rx = re.compile(pattern)
    hits = []
    files = [p] if os.path.isfile(p) else (
        os.path.join(root, fn)
        for root, dirs, fns in os.walk(p)
        for fn in fns
        if ".git" not in root.split(os.sep)
    )
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if rx.search(line):
                        hits.append(f"{fp}:{i}: {line.rstrip()}")
                        if len(hits) >= 200:
                            return "\n".join(hits) + "\n...[已达 200 行上限]"
        except (OSError, UnicodeError):
            continue
    return "\n".join(hits) if hits else "(无匹配)"


@tool("glob", "按 fnmatch 模式递归匹配文件名（如 **/*.py）。", {
    "type": "object",
    "properties": {"pattern": {"type": "string", "description": "fnmatch 模式"}},
    "required": ["pattern"],
}, readonly=True)
def glob_tool(pattern: str) -> str:
    base = _workdir()
    matches = []
    for root, dirs, files in os.walk(base):
        if ".git" in root.split(os.sep):
            continue
        for fn in files:
            rel = os.path.relpath(os.path.join(root, fn), base)
            if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(fn, pattern):
                matches.append(rel)
    return "\n".join(sorted(matches)) if matches else "(无匹配)"


@tool("write_file", "写入文件（覆盖/新建），路径必须在 workdir 内。", {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "文件路径"},
        "content": {"type": "string", "description": "完整内容"},
    },
    "required": ["path", "content"],
})
def write_file(path: str, content: str) -> str:
    p = _resolve(path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return f"已写入 {p}（{len(content)} 字符）"


@tool("edit_file", "精确替换一次 old -> new；找不到返回错误。路径必须在 workdir 内。", {
    "type": "object",
    "properties": {
        "path": {"type": "string"},
        "old": {"type": "string", "description": "被替换的原文（须唯一）"},
        "new": {"type": "string", "description": "替换后的文本"},
    },
    "required": ["path", "old", "new"],
})
def edit_file(path: str, old: str, new: str) -> str:
    p = _resolve(path)
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    if old not in content:
        return "error: old 文本在文件中不存在"
    if content.count(old) > 1:
        return "error: old 文本出现多次，无法唯一替换"
    with open(p, "w", encoding="utf-8") as f:
        f.write(content.replace(old, new, 1))
    return f"已编辑 {p}"


@tool("bash", "执行 shell 命令（cwd=workdir，超时 120s，stdout+stderr 合并截断）。", {
    "type": "object",
    "properties": {"command": {"type": "string", "description": "shell 命令"}},
    "required": ["command"],
})
def bash(command: str) -> str:
    try:
        proc = subprocess.run(
            command, shell=True, cwd=_workdir(),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            timeout=120, env=_sandbox_mod.sanitized_env(),
        )
        out = proc.stdout or ""
        tail = f"\n[exit code: {proc.returncode}]"
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") if isinstance(e.stdout, str) else ""
        tail = "\n[error: 命令超时 120s 被杀]"
    limit = 30_000
    if len(out) > limit:
        out = out[:limit] + f"\n...[截断，原 {len(out)} 字符]"
    return out + tail


@tool("skill_view", "查看某个技能的 SKILL.md 正文全文。", {
    "type": "object",
    "properties": {"name": {"type": "string", "description": "技能名"}},
    "required": ["name"],
}, readonly=True)
def skill_view(name: str) -> str:
    skills = _runtime().skills
    if skills is None:
        return "error: skills 模块未绑定"
    return skills.view(name)


@tool("save_lesson", "把一条教训追加到 MEMORY.md（下个会话生效）。", {
    "type": "object",
    "properties": {"text": {"type": "string", "description": "教训内容（一行）"}},
    "required": ["text"],
})
def save_lesson(text: str) -> str:
    memory = _runtime().memory
    if memory is None:
        return "error: memory 模块未绑定"
    memory.save_lesson(text)
    return "教训已记录"


@tool("delegate_task", "派生一个隔离子代理执行子任务（独立上下文/预算/transcript，"
                       "只回传最终报告）。适合探索性、会污染主线上下文的子任务。", {
    "type": "object",
    "properties": {"task": {"type": "string", "description": "子任务描述"}},
    "required": ["task"],
})
def delegate_task(task: str) -> str:
    from . import subagent
    sandbox = _runtime().sandbox
    mode = sandbox.mode if sandbox is not None else None
    return subagent.run_subagent(task, _workdir(), permission_mode=mode)


@tool("memory_search", "在长期记忆 MEMORY.md 中按关键词检索条目（只读）。", {
    "type": "object",
    "properties": {"keyword": {"type": "string", "description": "检索关键词"}},
    "required": ["keyword"],
}, readonly=True)
def memory_search(keyword: str) -> str:
    memory = _runtime().memory
    if memory is None:
        return "error: memory 模块未绑定"
    return memory.search(keyword)
