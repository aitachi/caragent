"""CLI 表面层（教程 Ch.8）：python -m miniagent。

交互式 / 一次性任务两种形态；ask 模式下 sandbox 的 ask_fn 用 input 问 [y/N]。
"""
from __future__ import annotations

import argparse
import os
import sys

from . import context as _context
from .loop import Agent


def _make_ask_fn():
    def ask(tool_name: str, args: dict) -> bool:
        try:
            detail = args.get("command") or args.get("path") or str(args)[:120]
            ans = input(f"[权限请求] {tool_name}: {detail}\n允许执行？[y/N] ")
        except EOFError:
            return False
        return ans.strip().lower() in ("y", "yes")
    return ask


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="miniagent",
        description="miniagent — 最小但模块齐全的 coding agent")
    p.add_argument("--workdir", default=os.getcwd(), help="工作目录（默认当前目录）")
    p.add_argument("--task", help="一次性任务模式：跑完即退出")
    p.add_argument("--permission", choices=["ask", "auto", "yolo"],
                   help="权限模式（默认 env MINIAGENT_PERMISSION 或 auto）")
    p.add_argument("--resume", help="重放指定 transcript JSONL 继续会话")
    p.add_argument("--cleanup-days", type=int, metavar="N",
                   help="清理 N 天前的旧会话 transcript 后退出")
    p.add_argument("--acp", action="store_true", help="进入 ACP stdio JSON-RPC 模式")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Windows 控制台默认 GBK，模型输出含 Unicode 符号会炸 print
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    if args.acp:
        from . import acp
        acp.main()
        return 0

    if args.cleanup_days is not None:
        from . import session as _session
        n = _session.cleanup_old_sessions(os.path.abspath(args.workdir),
                                          ttl_days=args.cleanup_days)
        print(f"已清理 {n} 个 {args.cleanup_days} 天前的会话 transcript")
        return 0

    ask_fn = _make_ask_fn() if args.permission == "ask" else None
    agent = Agent(args.workdir, permission_mode=args.permission,
                  ask_fn=ask_fn, transcript_path=args.resume)

    if args.task is not None:
        # 一次性模式
        try:
            result = agent.run(args.task)
        except Exception as e:
            print(f"任务失败: {e}", file=sys.stderr)
            return 1
        print(result)
        return 0

    # 交互模式
    print(f"miniagent | workdir={agent.workdir} | 权限={agent.sandbox.mode} "
          f"| 输入 /exit 退出, /memory 查看记忆, /compact 手动压缩")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text == "/exit":
            break
        if text == "/memory":
            print(agent.memory.load_snapshot() or "(记忆为空)")
            continue
        if text == "/compact":
            before = agent.drift.estimate(agent.messages)
            agent.compact(force=True)
            after = agent.drift.estimate(agent.messages)
            print(f"压缩完成: {before} -> {after} tokens"
                  f"（校准估算，漂移系数 x{agent.drift.ratio:.2f}）")
            continue
        try:
            print(agent.run(text))
        except Exception as e:
            print(f"error: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
