# miniagent — 最小完备 Coding Agent 设计

依据《Agent 模块化设计教程》（kimi-code × Hermes 双 codebase 对照）各章"最小设计"，
实现一个**最小但模块齐全**的能自动写代码的 Agent。两条设计宪法贯穿始终：

- **宪法一：Prompt Cache 是神圣的** —— 同一 Agent 会话内 system 前缀冻结；压缩只替换中段并保留头尾。
- **宪法二：窄腰核心，一切皆可插拔** —— 核心 = 一个循环 + 一个消息列表 + 一个工具调用协议；沙盒/记忆/技能/Hooks/ACP 全是挂在边上的模块。

技术选型：Python 3.10+，仅依赖 `requests`（Docker 内零编译）。模型后端：OpenAI 兼容接口
（默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`，模型 `qwen3.7-max`，30 万上下文窗口）。

## 模块总览（每个模块 = 一个文件 = 教程一章的最小设计 + 必要的第 1~2 级演化）

| 模块 | 文件 | 教程章节 | 最小设计来源 |
|---|---|---|---|
| 主循环 | `miniagent/loop.py` | Ch.1 | 30 行 while：ask→act→append，模型不调工具即终止，工具错误回填 |
| 上下文 | `miniagent/context.py` | Ch.2 | 阈值触发 + 头尾保留 + 中段摘要，摘要免疫包裹，尾部守护 |
| 工具 | `miniagent/tools.py` | Ch.3 | Agent 实例级 ToolRuntime + 注册表快照 + 参数校验 + 结果截断落盘 |
| 沙盒权限 | `miniagent/sandbox.py` | Ch.4 | 注册表同源工具集 + hardline + 三分级 + 路径型工具 realpath 围栏 |
| 记忆 | `miniagent/memory.py` | Ch.5 | MEMORY.md：会话开始冻结快照注入，教训追加写 |
| 技能 | `miniagent/skills.py` | Ch.6 | SKILL.md frontmatter 索引常驻一行 + 正文按需注入（延迟绑定） |
| Hooks | `miniagent/hooks.py` | Ch.7 | Agent 实例级 HookManager + 进程外 hook 超时强杀 + Stop 续跑闩锁 |
| ACP | `miniagent/acp.py` | Ch.8 | stdio JSON-RPC 分发表，stdout 只走协议，日志走 stderr |
| 会话持久化 | `miniagent/session.py` | Ch.9 | JSONL 消息/压缩快照顺序重放，容错解码（坏行跳过） |
| 子代理 | `miniagent/subagent.py` | Ch.9 | 独立上下文/runtime/transcript/预算，只回传蒸馏文本 |
| LLM 客户端 | `miniagent/llm.py` | Ch.1 附属 | OpenAI 兼容 chat + 结构化重试（429/5xx/超时，指数退避+抖动） |
| CLI 表面 | `miniagent/cli.py` | Ch.8 表面层 | 交互式 / 一次性任务两种形态 |
| Web 表面 | `miniagent/web.py` | Ch.8 表面层 | 每请求独立 workdir + 并发闸 + 有界等待 |

## 分层结构

```
表面层   cli.py（终端） · web.py（HTTP） · acp.py（JSON-RPC 宿主）
─────────────────────────────────────────────
Harness  loop.py（窄腰核心：while ask→act→append）
          ├─ context.py   每步前 preflight 压缩检查
          ├─ tools.py     实例级注册表快照/校验/截断
          ├─ sandbox.py   工具执行前的裁决与路径围栏
          ├─ hooks.py     实例级 before_tool/after_tool/stop/session 事件
          ├─ memory.py    会话开始快照 + 按需关键词搜索
          ├─ skills.py    索引常驻 + 正文按需
          ├─ subagent.py  隔离上下文派生
          └─ session.py   消息/压缩快照落盘 JSONL
─────────────────────────────────────────────
模型层   llm.py → qwen3.7-max（OpenAI 兼容）
```

## 关键设计决策（对应教程事故案例）

1. **终止由模型决定，但预算硬墙兜底**（Ch.1 级 2/5）：`max_steps`（默认 60）+ 预算耗尽给一次 grace 收尾。
2. **工具错误也是结果**：异常不中断循环，作为文本回填让模型自行纠错（Ch.1 不变量）。
3. **压缩三件套**（Ch.2 级 0/4/5）：token 估算（chars/4）超 85% 触发；头（system+首轮）尾（最近 N 条）保留；
   中段 LLM 摘要以 `[CONTEXT COMPACTION — REFERENCE ONLY]` 免疫包裹 + "最新用户消息 WINS"；不切 tool_call/result 对。
4. **结果治理**（Ch.3 级 2）：工具输出超 50K 字符全量落盘，模型只见 2K preview + 路径。
5. **注册/校验先于副作用，hardline 先于授权**（Ch.4 级 3）：未知名、畸形参数和解析失败不会进入 before_tool/handler；
   已知工具/只读属性来自 ToolRuntime 同一快照；路径型内置工具 realpath 围栏在 workdir 内。bash 仅规则裁决并固定 cwd，非 OS 级隔离。
6. **记忆双路的最小版**（Ch.5 级 0/3）：MEMORY.md 会话开始烘焙进 system prompt 尾部后**冻结**（保前缀缓存）；
   会话中学到的教训追加写文件，下个会话生效。
7. **技能三层披露的最小版**（Ch.6 级 0）：索引（name+一行 description）常驻 system prompt；`skill_view` 工具按需取正文。
8. **Hooks 阻断配额**（Ch.7 级 0/2/4）：只有 `before_tool` / `stop` 可阻断；进程外 hook 30s 超时强杀；
   stop hook 阻断续跑有**一次性闩锁**，防 turn 永不结束。
9. **ACP 窄翻译层**（Ch.8 级 0/1）：stdout 只走协议帧，一切日志 stderr；未知 method 显式 `-32601`。
10. **会话即账本**（Ch.9 级 0/1）：消息和压缩后的消息快照都写 JSONL；resume 按事件重放；坏行容错跳过。
11. **实例状态隔离**：ToolRuntime 与 HookManager 属于 Agent；后创建的 ACP/Web/子代理会话不能改写已有会话绑定。
12. **共享边界写清楚**：不同 workdir 的 context/memory/files 隔离；同一 workdir 的父子代理有意共享项目文件和 MEMORY.md。

## 内置工具面（最小 coding 集合）

`read_file` `write_file` `edit_file` `bash` `grep` `glob` `list_dir` `skill_view` `save_lesson` `delegate_task` `memory_search` —— 共 11 个。
每个 Agent 冻结自己的注册表快照；schema 与 sandbox 已知工具/readonly 属性同源。所有调用先做注册与参数校验，再过 sandbox 与 before_tool hook。

## 配置（环境变量）

`MINIAGENT_API_KEY`（必填）· `MINIAGENT_BASE_URL` · `MINIAGENT_MODEL` · `MINIAGENT_WORKDIR`（沙盒围栏根）
· `MINIAGENT_MAX_CONTEXT`（默认 300000）· `MINIAGENT_MAX_STEPS` · `MINIAGENT_PERMISSION`（ask/auto/yolo）
