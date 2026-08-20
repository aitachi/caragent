"""SKILL.md 技能系统最小版（教程 Ch.6）。

索引（name+一行 description）常驻 system prompt；
正文按需经 skill_view 工具注入（延迟绑定）。
frontmatter 手写简易解析，不引 pyyaml。
"""
from __future__ import annotations

import os


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析 --- 之间的 key: value；返回 (meta, body)。"""
    meta: dict[str, str] = {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return meta, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return meta, text
    for line in lines[1:end]:
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip().strip('"').strip("'")
    body = "\n".join(lines[end + 1:]).lstrip("\n")
    return meta, body


class Skills:
    def __init__(self, workdir: str, extra_dirs: list[str] | None = None):
        self.dirs: list[str] = []
        pkg_skills = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "skills")  # 包外 ../skills
        self.dirs.append(pkg_skills)
        self.dirs.append(os.path.join(workdir, ".miniagent", "skills"))
        for d in extra_dirs or []:
            self.dirs.append(d)
        self._index: dict[str, dict] = {}  # name -> {description, path, body}
        self._scan()

    def _scan(self) -> None:
        for d in self.dirs:
            if not os.path.isdir(d):
                continue
            for entry in sorted(os.listdir(d)):
                skill_md = os.path.join(d, entry, "SKILL.md")
                if not os.path.isfile(skill_md):
                    continue
                try:
                    with open(skill_md, "r", encoding="utf-8") as f:
                        text = f.read()
                except OSError:
                    continue
                meta, body = _parse_frontmatter(text)
                name = meta.get("name", entry)
                self._index[name] = {
                    "description": meta.get("description", "(无描述)"),
                    "path": skill_md,
                    "body": body,
                }

    def index_text(self) -> str:
        """每个技能一行 '- name: description'，注入 system prompt 尾部。"""
        if not self._index:
            return ""
        lines = ["", "## 可用技能（用 skill_view 工具查看正文）"]
        for name, info in self._index.items():
            lines.append(f"- {name}: {info['description']}")
        return "\n".join(lines)

    def view(self, name: str) -> str:
        """返回 SKILL.md 正文全文 + 资源文件路径提示。"""
        info = self._index.get(name)
        if info is None:
            known = ", ".join(self._index) or "(无)"
            return f"error: 未知技能 {name!r}；已知: {known}"
        skill_dir = os.path.dirname(info["path"])
        resources = [f for f in sorted(os.listdir(skill_dir)) if f != "SKILL.md"]
        hint = (f"\n\n[技能目录: {skill_dir}"
                + (f"；资源文件: {', '.join(resources)}" if resources else "")
                + "]")
        return info["body"] + hint
