"""子代理派生（教程 Ch.9 最小设计，对照 kimi-code 扁平子代理）。

防"多子代理上下文压缩污染"的设计答案：**不共享会话运行时状态**。
- 子代理 = 全新 Agent 实例：独立 messages、独立 transcript（自己的
  wire.jsonl 等价物）、ToolRuntime、HookManager、max_steps 预算、stop 闩锁；
- 父代理的 maybe_compact 只作用于父 messages，物理上碰不到子代理
  的上下文（反之亦然）——不存在 Hermes #38727 那种"父子共享 session
  并发压缩产生双 sibling"的前置条件；
- 只回传最终文本（distill，截断上限），探索过程不灌回主线窗口；
- 子代理 system prompt 与父一致（同前缀），缓存友好（kimi fork 暖 cache）。

为操作同一项目，父子有意共享 workdir、项目文件与该目录的 MEMORY.md；
因此这里保证的是 context/runtime 不串绑，不是文件系统写入隔离。
"""
from __future__ import annotations

import os

DISTILL_LIMIT = 10_000

# 测试可注入的 Agent 工厂（签名同 loop.Agent），默认 None = 用真 Agent
AGENT_FACTORY = None


def run_subagent(task: str, workdir: str, permission_mode: str | None = None) -> str:
    """派生一个隔离子代理执行任务，只回传最终文本（distill）。"""
    factory = AGENT_FACTORY
    if factory is None:
        from .loop import Agent  # 延迟导入，避免 tools → loop 循环依赖
        factory = Agent

    child = factory(workdir, permission_mode=permission_mode)
    # 独立预算（kimi 子代理默认 50 的最小对应物），不侵蚀父代理步数
    child.max_steps = int(os.environ.get("MINIAGENT_SUBAGENT_MAX_STEPS", "30"))
    result = child.run(task)
    if len(result) > DISTILL_LIMIT:
        result = result[:DISTILL_LIMIT] + "\n...[子代理报告已截断]"
    return result
