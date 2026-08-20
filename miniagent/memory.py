"""MEMORY.md 双路最小版（教程 Ch.5）。

会话开始读全文烘焙进 system prompt 尾部后冻结（保前缀缓存）；
会话中教训追加写文件，下个会话生效；上限管理按行截断旧条目。

多会话防污染加固（对照 kimi-code "会话即记忆 + 用户主权" 与
Hermes "注入安检 + 外部漂移防御" 的最小化实现）：
1. 追加写带 provenance（UTC 时间戳），每条 lesson 规范为单行；
2. 超限截断走 tmp+rename 原子替换，读取方不会看到半文件；
3. 快照加载时做注入安检，命中 promptware 模式的条目以占位符替换——
   被污染的条目不随快照带毒注入（Hermes #11475 系事故的最小对策）。
"""
from __future__ import annotations

import os
import re
import time

MAX_CHARS = 8000
KEEP_CHARS = 6000

# 注入安检：命中即替换为占位符（最小覆盖：指令覆盖/角色冒充/围栏回显）
_THREAT_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above)\s+instructions?",
    r"忽略(以上|之前|先前|所有).{0,6}(指令|指示|命令)",
    r"you\s+are\s+(now\s+)?a\b",
    r"你(现在)?是(一个|一名)",
    r"<\s*/?\s*system\s*>",
    r"\[CONTEXT COMPACTION",
]
_PLACEHOLDER = "- [已过滤：疑似注入内容的记忆条目]"


def _scan(text: str) -> str:
    """逐行注入安检：命中威胁模式的行替换为占位符。"""
    out = []
    for line in text.splitlines(keepends=True):
        if any(re.search(p, line, re.IGNORECASE) for p in _THREAT_PATTERNS):
            out.append(_PLACEHOLDER + "\n")
        else:
            out.append(line)
    return "".join(out)


class Memory:
    def __init__(self, workdir: str):
        self.path = os.path.join(workdir, ".miniagent", "MEMORY.md")

    def load_snapshot(self) -> str:
        """会话开始读全文（无则空串），注入安检后返回冻结文本。"""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return _scan(f.read())
        except FileNotFoundError:
            return ""

    def save_lesson(self, text: str) -> None:
        """追加带 provenance 的 '- [ts] {text}'；文件超限时按行保留最近部分。

        追加用单次 write；截断重写走 tmp+rename 原子替换。
        """
        text = " ".join(str(text).splitlines()).strip()
        if not text:
            raise ValueError("记忆条目不能为空")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(f"- [{ts}] {text}\n")
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            return
        if len(content) <= MAX_CHARS:
            return
        # 按行从旧到新，保留累计不超过 KEEP_CHARS 的最近条目
        lines = content.splitlines(keepends=True)
        kept: list[str] = []
        acc = 0
        for line in reversed(lines):
            if acc + len(line) > KEEP_CHARS:
                break
            kept.insert(0, line)
            acc += len(line)
        # tmp+rename 原子替换：读取方不会看到截断到一半的文件
        tmp = self.path + f".tmp.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("".join(kept))
        os.replace(tmp, self.path)

    def search(self, keyword: str, limit: int = 20) -> str:
        """关键词检索记忆条目（容量有上限的平文件，关键词检索精度足够；
        对照 Hermes session_search 的最小版，不引入向量库依赖）。"""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = _scan(f.read()).splitlines()
        except FileNotFoundError:
            return "(记忆为空)"
        kw = keyword.lower()
        hits = [l for l in lines if kw in l.lower()]
        if not hits:
            return f"(无匹配 {keyword!r} 的记忆条目)"
        return "\n".join(hits[:limit])
