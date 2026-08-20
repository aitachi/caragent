# -*- coding: utf-8 -*-
"""miniagent 完整报告构建脚本(LeetCode 合并严格版版式对齐)。

版式规格(实测自 LeetCode_Top150_高频算法题解_合并严格版_Python版.pdf,Chrome print-to-pdf):
- 章节头: MicrosoftYaHei-Bold 14px #111111, 下横线1.5px #333 + 浅灰说明条 #F4F4F4(左边3px #999)
- 题目标题/模块标题: MicrosoftYaHei-Bold 11.5px #111111
- 正文: MicrosoftYaHei 10.5px #111111 行距1.5
- pill: 灰底#E8E8E8黑字 / 黑底#333白字, 粗体9px
- 代码/图: Consolas 8.8px #111, 底#F6F6F6, 边框#BBB
- 表格: 细线#BBB, 表头灰底#F0F0F0粗体
- 复杂度/注: 9px #555 / #FAFAF0黄底注框
- 全黑白灰,无彩色渲染

构建: python build_miniagent_report.py 生成 miniagent_report_full.html
      chrome --headless --print-to-pdf 转出 docs/miniagent_report_full.pdf
"""

CSS = """
<style>
  @page { size: A4; margin: 15mm 12mm; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; color: #111111;
         font-size: 10.5px; line-height: 1.5; }
  .chapter-title { font-size: 14px; font-weight: bold; margin-top: 18px; }
  .chapter-rule { border-bottom: 1.5px solid #333333; margin: 4px 0 6px; }
  .chapter-desc { background: #F4F4F4; padding: 6px 10px; font-size: 10.5px; color: #333333;
                  border-left: 3px solid #999999; margin-bottom: 10px; }
  .sec-title { font-size: 11.5px; font-weight: bold; margin: 12px 0 4px; }
  .sub-title { font-size: 10.5px; font-weight: bold; margin: 8px 0 3px; }
  p { margin: 3px 0; }
  .pill { display: inline-block; font-size: 9px; font-weight: bold; border-radius: 2px;
          padding: 2px 8px; margin: 5px 0 3px; }
  .pill.l0 { background: #EEEEEE; color: #333333; }
  .pill.l1 { background: #DDDDDD; color: #222222; }
  .pill.l2 { background: #333333; color: #ffffff; }
  .pill.l3 { background: #111111; color: #ffffff; }
  .pill.layer { background: #E8E8E8; color: #333333; }
  pre { font-family: Consolas, "Courier New", monospace; font-size: 8.8px; line-height: 1.45;
        background: #F6F6F6; border: 1px solid #BBBBBB; border-radius: 3px;
        padding: 7px 9px; white-space: pre-wrap; word-wrap: break-word; color: #111111; }
  pre.arch { background: #FAFAFA; }
  .complexity { font-size: 9px; color: #555555; margin: 3px 0 2px; }
  .note { font-size: 9.5px; color: #444444; background: #FAFAF0; border-left: 2px solid #CCAA00;
          padding: 3px 8px; margin: 4px 0; }
  .why { font-size: 9.5px; color: #444444; background: #F6F6F6; border-left: 2px solid #888888;
         padding: 3px 8px; margin: 4px 0; }
  table { border-collapse: collapse; width: 100%; margin: 6px 0; font-size: 9.5px; }
  th { background: #F0F0F0; border: 1px solid #BBBBBB; padding: 3px 6px; text-align: left;
       font-weight: bold; }
  td { border: 1px solid #BBBBBB; padding: 3px 6px; vertical-align: top; }
  .cover { text-align: left; padding-top: 30px; }
  .cover h1 { font-size: 20px; margin-bottom: 8px; }
  .cover .intro { background: #F4F4F4; border-left: 3px solid #999; padding: 8px 12px;
                  margin: 12px 0; font-size: 10.5px; }
  .cover ol { font-size: 10.5px; padding-left: 26px; }
  .cover li { margin: 1px 0; }
  .fig { page-break-inside: avoid; margin: 8px 0; }
  .fig svg { display: block; margin: 0 auto; }
  .figcap { font-size: 9px; color: #555555; text-align: center; margin: 4px 0 8px; }
  .mod { page-break-inside: avoid; margin-bottom: 12px; }
  .m-title { font-size: 11.5px; font-weight: bold; margin: 12px 0 3px; }
  .toc2 { font-size: 9.5px; color: #444; margin: 2px 0 8px; }
</style>
"""

# ---------------- SVG 流程图工具(黑白灰) ----------------

def svg_frame(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" font-family="Microsoft YaHei, sans-serif">{body}</svg>')

def box(x, y, w, h, lines, bold=False, fill="#FFFFFF", stroke="#333333", dash=False, fs=9):
    t = ""
    n = len(lines)
    lh = fs + 3
    total = n * lh
    y0 = y + (h - total) / 2 + fs
    fw = ' font-weight="bold"' if bold else ""
    for i, ln in enumerate(lines):
        t += f'<text x="{x + w/2}" y="{y0 + i*lh}" text-anchor="middle" font-size="{fs}" fill="#111111"{fw}>{ln}</text>'
    d = ' stroke-dasharray="4,3"' if dash else ""
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.1"{d}/>' + t)

def diamond(x, y, w, h, lines, fill="#F6F6F6", fs=9):
    cx, cy = x + w/2, y + h/2
    pts = f"{cx},{y} {x+w},{cy} {cx},{y+h} {x},{cy}"
    t = ""
    lh = fs + 3
    y0 = cy - (len(lines)*lh)/2 + fs
    for i, ln in enumerate(lines):
        t += f'<text x="{cx}" y="{y0 + i*lh}" text-anchor="middle" font-size="{fs}" fill="#111111">{ln}</text>'
    return f'<polygon points="{pts}" fill="{fill}" stroke="#333333" stroke-width="1.1"/>' + t

def arrow(x1, y1, x2, y2, label="", dash=False, lx=None, ly=None, anchor="middle"):
    d = ' stroke-dasharray="4,3"' if dash else ""
    a = (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#444444" '
         f'stroke-width="1.1" marker-end="url(#ar)"{d}/>')
    if label:
        lx = lx if lx is not None else (x1 + x2) / 2
        ly = ly if ly is not None else (y1 + y2) / 2 - 3
        a += (f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" font-size="8" fill="#555555">{label}</text>')
    return a

DEFS = ('<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#444444"/></marker></defs>')

# ---------------- 每模块知识图谱矢量流程图 ----------------

def fig_loop():
    w, h = 640, 560
    b = [DEFS]
    b.append(box(200, 8, 240, 30, ["用户任务 task / --resume 重放"], fill="#F4F4F4"))
    b.append(box(130, 56, 380, 40, ["loop.run()  入口护栏", "输入 > MAX_INPUT_CHARS(20万) → 直接拒", "(零 LLM 消耗)"], bold=True, fill="#F6F6F6"))
    b.append(box(170, 112, 300, 30, ["session_start hook + user 消息 _record"]))
    # while 循环框
    b.append(f'<rect x="90" y="160" width="460" height="330" rx="5" fill="none" stroke="#777777" stroke-width="1" stroke-dasharray="6,4"/>')
    b.append(f'<text x="440" y="176" font-size="9" fill="#555555">while steps &lt; MAX_STEPS(60)</text>')
    b.append(box(150, 184, 340, 34, ["① preflight: context.maybe_compact", "估算 >85%×30万 → 头尾保留+中段摘要"]))
    b.append(box(150, 234, 340, 32, ["② _chat(): llm.chat + usage 账本", "溢出错误 → 强制压缩重试 ≤3 次"]))
    b.append(diamond(230, 284, 180, 56, ["③ 有 tool_calls?"], fill="#F0F0F0"))
    b.append(box(150, 362, 340, 40, ["④ _run_tool(逐个):", "validate → sandbox.approve → before_tool", "→ execute → after_tool"]))
    b.append(box(150, 420, 340, 26, ["⑤ result 以 tool 消息 _record(只追加)"]))
    b.append(diamond(230, 462, 180, 50, ["预算耗尽?"], fill="#F0F0F0"))
    b.append(box(560, 462, 0.1, 0.1, [""]))
    # 正常终止(右出循环)
    b.append(box(470, 528, 150, 26, ["final_text 正常收尾"]))
    b.append(box(90, 528, 170, 26, ["grace 收尾:总结进展"]))
    b.append(box(300, 528, 150, 26, ["stop hook 闩锁续跑≤1"]))
    # 边
    b.append(arrow(320, 38, 320, 58))
    b.append(arrow(320, 92, 320, 112))
    b.append(arrow(320, 142, 320, 184))
    b.append(arrow(320, 218, 320, 236))
    b.append(arrow(320, 266, 320, 284))
    b.append(arrow(410, 312, 470, 312, "否 → final_text", lx=500, ly=306))
    b.append(box(470, 300, 130, 24, ["break 出 while"], fill="#FAFAFA"))
    b.append(arrow(320, 340, 320, 366, "是"))
    b.append(arrow(320, 402, 320, 420))
    b.append(arrow(320, 444, 320, 462))
    b.append(arrow(230, 487, 90, 487, "", ly=483))
    # 回边:⑤→①
    b.append(arrow(150, 431, 110, 431, "", ly=427))
    b.append(f'<line x1="110" y1="431" x2="110" y2="201" stroke="#444444" stroke-width="1.1"/>')
    b.append(arrow(110, 201, 150, 201, "下一轮", lx=100, ly=196, anchor="end"))
    b.append(arrow(320, 512, 262, 528, "是→grace", lx=262, ly=520))
    b.append(arrow(378, 512, 375, 528, "否", lx=388, ly=522))
    b.append(arrow(535, 324, 535, 528, "", lx=543, ly=430))
    b.append(f'<line x1="450" y1="541" x2="470" y2="541" stroke="#444444" stroke-width="1.1" marker-end="url(#ar)"/>')
    return svg_frame(w, h, "".join(b))

def fig_context():
    w, h = 640, 520
    b = [DEFS]
    b.append(box(190, 8, 260, 34, ["messages 列表(上轮)", "估算 = chars/4 × drift.ratio", "(锚点校准系数,未校准=1.0)"], fill="#F4F4F4"))
    b.append(diamond(215, 58, 210, 56, ["估算 > 85%×MAX_CONTEXT?"], fill="#F0F0F0"))
    b.append(box(470, 72, 150, 28, ["原样返回(缓存安全)", "前缀不动=缓存命中"], fill="#FAFAFA"))
    b.append(box(170, 138, 300, 30, ["定界 head = messages[0](system)", "+ 首条 user"]))
    b.append(box(170, 188, 300, 36, ["tail 从尾部倒走 ≤20% 预算", "不切 tool_call/result 对", "最后 user 必在 tail"]))
    b.append(box(170, 248, 300, 30, ["middle = head 与 tail 之间", "送 LLM 单次结构化摘要"]))
    b.append(box(150, 298, 340, 34, ["摘要以 [CONTEXT COMPACTION — REFERENCE ONLY]", "免疫包裹 + 声明最新用户消息优先"]))
    b.append(box(170, 356, 300, 30, ["新 messages = head + 摘要 + tail", "写 {type:compact, messages} 快照入 transcript"]))
    b.append(diamond(215, 410, 210, 50, ["摘要调用成功?"], fill="#F0F0F0"))
    b.append(box(470, 422, 150, 26, ["fail-open:保留原会话", "不阻塞主循环"], fill="#FAFAFA"))
    b.append(box(200, 480, 240, 26, ["返回压缩后 messages(或原样)"]))
    b.append(arrow(320, 38, 320, 58))
    b.append(arrow(425, 86, 470, 86, "否", lx=440, ly=80))
    b.append(arrow(320, 114, 320, 138, "是"))
    b.append(arrow(320, 168, 320, 190))
    b.append(arrow(320, 224, 320, 248))
    b.append(arrow(320, 278, 320, 298))
    b.append(arrow(320, 332, 320, 356))
    b.append(arrow(320, 386, 320, 410))
    b.append(arrow(425, 435, 470, 435, "失败", lx=442, ly=429))
    b.append(arrow(320, 460, 320, 480))
    b.append(f'<line x1="545" y1="98" x2="545" y2="493" stroke="#444444" stroke-width="1.1" marker-end="url(#ar)"/>')
    b.append(f'<line x1="545" y1="448" x2="545" y2="493" stroke="#444444" stroke-width="1.1"/>')
    return svg_frame(w, h, "".join(b))

def fig_tools():
    w, h = 640, 500
    b = [DEFS]
    b.append(box(180, 8, 280, 30, ["REGISTRY 全局注册表(@tool 装饰器)", "Agent 创建时冻结 ToolRuntime 快照"], fill="#F4F4F4"))
    b.append(box(150, 58, 340, 30, ["绑定本 Agent 的 sandbox/skills/memory", "schemas_for_llm() → 11 工具 schema"]))
    b.append(box(180, 112, 280, 30, ["tool_calls(name + args) 到达"]))
    b.append(diamond(215, 164, 210, 52, ["注册表查名 + required/", "类型/额外参数校验"], fill="#F0F0F0"))
    b.append(box(470, 172, 150, 36, ["校验失败 →", "错误文本回填(不执行)", "模型自行换路"], fill="#FAFAFA"))
    b.append(box(150, 236, 340, 44, ["handler 执行(异常捕获,不外抛)", "read_file / list_dir / grep / glob", "write / edit / bash / skill_view", "save_lesson / delegate / memory_search"]))
    b.append(diamond(215, 306, 210, 50, ["输出 > 50K 字符?"], fill="#F0F0F0"))
    b.append(box(150, 382, 340, 34, ["全量落盘 .miniagent/tool_results/<id>", "模型只见 2K preview + 文件路径"]))
    b.append(box(470, 390, 150, 30, ["直接返回(bash 另有", "30K 截断 + 120s 超时)"], fill="#FAFAFA"))
    b.append(box(220, 442, 200, 26, ["result 消息回填主循环"]))
    b.append(arrow(320, 38, 320, 58))
    b.append(arrow(320, 88, 320, 112))
    b.append(arrow(320, 142, 320, 164))
    b.append(arrow(425, 190, 470, 190, "失败", lx=440, ly=184))
    b.append(arrow(320, 216, 320, 240, "通过"))
    b.append(arrow(320, 280, 320, 306))
    b.append(arrow(425, 331, 470, 331, "否", lx=440, ly=325))
    b.append(arrow(320, 356, 320, 382, "是"))
    b.append(arrow(320, 416, 320, 442))
    b.append(f'<line x1="545" y1="206" x2="545" y2="455" stroke="#444444" stroke-width="1.1"/>')
    b.append(arrow(545, 455, 420, 455, "", ly=451))
    b.append(f'<line x1="545" y1="420" x2="545" y2="455" stroke="#444444" stroke-width="1.1"/>')
    return svg_frame(w, h, "".join(b))

def fig_sandbox():
    w, h = 640, 470
    b = [DEFS]
    b.append(box(180, 8, 280, 30, ["tool 名 + args + 权限模式", "(ask / auto / yolo)"], fill="#F4F4F4"))
    b.append(box(150, 56, 340, 38, ["① 去混淆后 hardline 匹配:", "NFKC 全角折叠 + $IFS 折叠", "+ 引号拼接剥离"]))
    b.append(diamond(215, 112, 210, 50, ["命中 hardline?", "(rm -rf / · mkfs · dd 裸设备 ·", "fork bomb · 写 authorized_keys)"], fill="#F0F0F0"))
    b.append(box(470, 122, 150, 30, ["拒绝 — yolo 也不放行", "错误文本回填"], fill="#F6F6F6"))
    b.append(diamond(215, 182, 210, 44, ["注册表内有此工具?", "(fail-closed)"], fill="#F0F0F0"))
    b.append(diamond(215, 244, 210, 44, ["注册表标记 readonly?"], fill="#F0F0F0"))
    b.append(diamond(215, 306, 210, 50, ["模式 = yolo/auto?"], fill="#F0F0F0"))
    b.append(box(470, 306, 150, 44, ["ask 模式 → ask_fn 回调", "无回调/异常 → 默认拒绝", "(fail-closed)"], fill="#FAFAFA"))
    b.append(box(150, 382, 340, 34, ["放行 + 二道围栏:", "路径工具 realpath 必须落在 workdir 内;", "bash: 固定 cwd + sanitized_env() 剥密钥"]))
    b.append(box(200, 436, 240, 24, ["返回 (allowed, reason)"]))
    b.append(arrow(320, 38, 320, 58))
    b.append(arrow(320, 92, 320, 112))
    b.append(arrow(425, 137, 470, 137, "是", lx=440, ly=131))
    b.append(arrow(320, 162, 320, 182, "否"))
    b.append(arrow(320, 226, 320, 244, "无→拒"))
    b.append(arrow(320, 288, 320, 306, "否"))
    b.append(arrow(425, 331, 470, 331, "否(ask)", lx=448, ly=325))
    b.append(arrow(320, 356, 320, 382, "是"))
    b.append(arrow(320, 416, 320, 436))
    b.append(f'<line x1="320" y1="190" x2="320" y2="182" stroke="#444444"/>')
    return svg_frame(w, h, "".join(b))

def fig_memory():
    w, h = 640, 430
    b = [DEFS]
    b.append(box(60, 8, 200, 30, ["MEMORY.md(磁盘)", "每个 workdir 独立一份"], fill="#F4F4F4"))
    b.append(box(380, 8, 200, 30, ["Agent 创建(session 边界)", "load_snapshot()"], fill="#F4F4F4"))
    b.append(box(310, 68, 320, 30, ["逐行注入安检 _scan()", "指令覆盖/角色冒充/系统标签 → 替换占位符"]))
    b.append(box(310, 128, 320, 30, ["烘焙进 system prompt 尾部后冻结", "(前缀缓存全程命中)"]))
    b.append(box(60, 190, 200, 34, ["会话中 save_lesson(text)", "规范化为单条记录"], fill="#FAFAFA"))
    b.append(box(310, 190, 320, 30, ["追加 '- [UTC ts] text'(行级原子 provenance)"]))
    b.append(diamond(345, 246, 180, 44, ["超 8K 上限?"], fill="#F0F0F0"))
    b.append(box(540, 250, 80, 36, ["保留最近条目", "tmp+rename", "原子替换"], fill="#FAFAFA"))
    b.append(box(310, 316, 320, 30, ["下个 Agent 创建时才生效(会话边界写入)"]))
    b.append(box(60, 316, 200, 30, ["memory_search(keyword)", "只读检索 + 同样安检"], fill="#FAFAFA"))
    b.append(box(240, 380, 160, 24, ["主线循环"]))
    b.append(arrow(160, 38, 160, 190, "", ly=120))
    b.append(arrow(480, 38, 480, 68))
    b.append(arrow(480, 98, 480, 128))
    b.append(arrow(480, 158, 480, 190))
    b.append(arrow(480, 220, 480, 246))
    b.append(arrow(435, 268, 540, 268, "是", lx=485, ly=262))
    b.append(arrow(480, 290, 480, 316))
    b.append(arrow(260, 205, 310, 205))
    b.append(arrow(160, 224, 160, 316))
    b.append(arrow(480, 346, 400, 380, "system 尾部", lx=430, ly=372))
    b.append(arrow(160, 346, 240, 392, "", lx=200, ly=370))
    return svg_frame(w, h, "".join(b))

def fig_skills():
    w, h = 640, 330
    b = [DEFS]
    b.append(box(150, 8, 340, 34, ["扫描 skills/ 与 .miniagent/skills/", "每个 <name>/SKILL.md:frontmatter(name+description)"], fill="#F4F4F4"))
    b.append(box(150, 72, 340, 30, ["index_text():每个技能一行索引", "常驻 system prompt(约 100 字符/技能)"]))
    b.append(diamond(215, 132, 210, 44, ["模型调用 skill_view(name)?"], fill="#F0F0F0"))
    b.append(box(150, 208, 340, 30, ["按需返回该 SKILL.md 全文(第二层披露)", "正文不常驻,不撑爆前缀缓存"]))
    b.append(box(470, 208, 140, 30, ["未调用 → 零成本", "(索引仍提示存在)"], fill="#FAFAFA"))
    b.append(box(220, 272, 200, 24, ["正文注入 turn 内上下文"]))
    b.append(arrow(320, 42, 320, 72))
    b.append(arrow(320, 102, 320, 132))
    b.append(arrow(320, 176, 320, 208, "是", lx=330, ly=196))
    b.append(arrow(425, 154, 540, 154, "", ly=150))
    b.append(f'<line x1="540" y1="154" x2="540" y2="208" stroke="#444444" stroke-width="1.1" marker-end="url(#ar)"/>')
    b.append(arrow(320, 238, 320, 272))
    return svg_frame(w, h, "".join(b))

def fig_hooks():
    w, h = 640, 470
    b = [DEFS]
    b.append(box(150, 8, 340, 30, ["Agent 事件源(new_manager 独立实例)", "session_start / session_end / before_tool /", "after_tool / stop"], fill="#F4F4F4"))
    b.append(box(150, 78, 340, 30, ["进程内回调表 HookManager.on(event, fn)", "(clone() 出子代理副本,互不污染)"]))
    b.append(box(150, 138, 340, 34, ["进程外 hook:.miniagent/hooks.d/<event>_*.py", "子进程运行 · stdin 传 JSON · 30s 超时强杀", "崩溃只记 stderr,不影响主循环"]))
    b.append(diamond(195, 202, 120, 60, ["事件可阻断?", "(before_tool /", "stop)"], fill="#F0F0F0"))
    b.append(box(370, 210, 220, 44, ["stdout 含 {\"decision\":\"block\"} →", "block:reason", "→ 工具不执行/turn 续跑"], fill="#F6F6F6"))
    b.append(box(370, 286, 220, 30, ["stop 一次性闩锁 StopLatch:", "续跑仅 1 次,防 hook 永续 block"], fill="#FAFAFA"))
    b.append(box(150, 350, 340, 30, ["after_tool:统一收到结果(失败也通知)", "便于审计与遥测"]))
    b.append(box(220, 410, 200, 24, ["回主循环"]))
    b.append(arrow(320, 50, 320, 78))
    b.append(arrow(320, 108, 320, 138))
    b.append(arrow(320, 172, 320, 202))
    b.append(arrow(315, 232, 370, 232, "是", lx=338, ly=226))
    b.append(arrow(255, 232, 255, 350, "否→仅通知", lx=160, ly=300, anchor="start"))
    b.append(arrow(480, 254, 480, 286))
    b.append(arrow(320, 380, 320, 410))
    return svg_frame(w, h, "".join(b))

def fig_acp():
    w, h = 640, 400
    b = [DEFS]
    b.append(box(180, 8, 280, 30, ["宿主进程 stdin(每行一帧 JSON-RPC)"], fill="#F4F4F4"))
    b.append(box(150, 58, 340, 34, ["逐行解析帧", "带 id → 请求(须回复);无 id → notification(静默)"]))
    b.append(box(150, 120, 340, 40, ["method 分发:", "initialize → 能力握手", "session/new → 新建 Agent 存入 _sessions{uuid}", "session/prompt → 按 sessionId 取 Agent 跑"]))
    b.append(diamond(195, 194, 120, 56, ["未知 method?", ""], fill="#F0F0F0"))
    b.append(box(370, 200, 220, 44, ["带 id → 显式 -32601", "未知 sessionId → -32602", "(协议可观测,不静默吞错)"], fill="#F6F6F6"))
    b.append(box(150, 282, 340, 34, ["stdout 只输出协议帧(一条 print 也不混入)", "日志/调试全走 stderr"]))
    b.append(box(220, 346, 200, 24, ["宿主收到 result 帧"]))
    b.append(arrow(320, 38, 320, 58))
    b.append(arrow(320, 92, 320, 120))
    b.append(arrow(320, 160, 320, 194))
    b.append(arrow(315, 222, 370, 222, "是", lx=338, ly=216))
    b.append(arrow(255, 250, 255, 282, "否", lx=270, ly=270))
    b.append(arrow(320, 316, 320, 346))
    return svg_frame(w, h, "".join(b))

def fig_session():
    w, h = 640, 450
    b = [DEFS]
    b.append(box(150, 8, 340, 30, ["每条消息/事件一行 JSON append", "(单次 write,崩溃原子;坏行容错跳过)"], fill="#F4F4F4"))
    b.append(box(60, 78, 240, 30, ["事件类型:message", "(user/assistant/tool 消息)"], fill="#FAFAFA"))
    b.append(box(340, 78, 240, 34, ["事件类型:compact / overflow_heal", "携带替换后的完整 messages 快照"], fill="#F6F6F6"))
    b.append(box(340, 146, 240, 30, ["事件类型:usage(用量账本落盘)"], fill="#FAFAFA"))
    b.append(box(150, 208, 340, 34, ["resume = 按事件顺序重放:", "reconstruct_messages() 遇 compact 快照", "→ 直接采用快照,丢弃其前历史"]))
    b.append(box(150, 272, 340, 30, ["新会话文件名:时间戳 + 独占创建(open x 模式)", "同秒并发也不会碰撞"]))
    b.append(diamond(195, 332, 120, 50, ["mtime 超 TTL?", "(默认 30 天)"], fill="#F0F0F0"))
    b.append(box(370, 338, 220, 38, ["cleanup_old_sessions 删除", "CLI --cleanup-days 可调", "(子代理 transcript 独立文件)"], fill="#FAFAFA"))
    b.append(arrow(320, 38, 320, 78, "", ly=60))
    b.append(f'<line x1="180" y1="60" x2="460" y2="60" stroke="#444444" stroke-width="1.1"/>')
    b.append(arrow(460, 60, 460, 78))
    b.append(arrow(460, 112, 460, 146))
    b.append(f'<line x1="180" y1="108" x2="180" y2="170" stroke="#444444" stroke-width="1.1"/>')
    b.append(f'<line x1="180" y1="170" x2="320" y2="208" stroke="#444444" stroke-width="1.1" marker-end="url(#ar)"/>')
    b.append(f'<line x1="460" y1="176" x2="460" y2="190" stroke="#444444" stroke-width="1.1"/>')
    b.append(f'<line x1="460" y1="190" x2="320" y2="208" stroke="#444444" stroke-width="1.1" marker-end="url(#ar)"/>')
    b.append(arrow(320, 242, 320, 272))
    b.append(arrow(320, 302, 320, 332, "", ly=318))
    b.append(f'<line x1="315" y1="357" x2="370" y2="357" stroke="#444444" stroke-width="1.1" marker-end="url(#ar)"/>')
    return svg_frame(w, h, "".join(b))

def fig_subagent():
    w, h = 640, 420
    b = [DEFS]
    b.append(box(180, 8, 280, 30, ["主线 turn 内调用 delegate_task(task)"], fill="#F4F4F4"))
    b.append(box(130, 58, 380, 34, ["new Agent(workdir):全新实例 —", "独立 messages / 独立 ToolRuntime / 独立 HookManager"]))
    b.append(box(130, 116, 380, 30, ["独立 transcript 文件 / 独立预算 30 步 / 独立 stop 闩锁"]))
    b.append(box(130, 172, 380, 30, ["子代理跑完整 mini-loop(同 system 前缀 → 暖缓存)", "有意共享 workdir 文件与项目记忆"]))
    b.append(box(130, 228, 380, 30, ["父压缩物理上碰不到子上下文(各自 messages)", "子过程日志只进子 transcript,零主线污染"]))
    b.append(box(150, 288, 340, 30, ["最终文本 distill 截断 ≤10K 回传主线", "作为 delegate_task 的 result 消息"]))
    b.append(box(220, 346, 200, 26, ["主线继续(拿蒸馏报告干活)"]))
    b.append(arrow(320, 38, 320, 58))
    b.append(arrow(320, 92, 320, 116))
    b.append(arrow(320, 146, 320, 172))
    b.append(arrow(320, 202, 320, 228))
    b.append(arrow(320, 258, 320, 288))
    b.append(arrow(320, 318, 320, 346))
    return svg_frame(w, h, "".join(b))

def fig_llm():
    w, h = 640, 470
    b = [DEFS]
    b.append(box(180, 8, 280, 30, ["messages + tools schema", "(OpenAI 兼容 chat)"], fill="#F4F4F4"))
    b.append(box(150, 58, 340, 30, ["body: enable_thinking:false(qwen3 系必须)", "+ model / stream:false"]))
    b.append(diamond(195, 118, 120, 56, ["HTTP 成功?"], fill="#F0F0F0"))
    b.append(box(370, 118, 220, 56, ["429/5xx/超时:", "指数退避 ×2 ≤30s + 20% 抖动", "+ 尊重 Retry-After,最多 5 次", "仍失败 → raise LLMError"], fill="#F6F6F6"))
    b.append(diamond(195, 208, 120, 52, ["错误含 context/", "overflow/length?"], fill="#F0F0F0"))
    b.append(box(370, 210, 220, 48, ["溢出自愈:force=True 强制压缩", "后重试,连续 3 次放弃", "(kimi 认领 413 同构)"], fill="#F6F6F6"))
    b.append(box(150, 290, 340, 36, ["tool_calls 逐个解析 arguments JSON", "解析失败 → 空对象 + error 标记", "(回填,不炸循环)"]))
    b.append(box(150, 358, 340, 30, ["usage 累加(prompt/completion/calls)", "turn 结束落 transcript 事件"]))
    b.append(box(220, 418, 200, 24, ["返回 content + tool_calls + usage"]))
    b.append(arrow(320, 38, 320, 58))
    b.append(arrow(320, 88, 320, 118))
    b.append(arrow(315, 146, 370, 146, "否", lx=338, ly=140))
    b.append(arrow(255, 174, 255, 208, "是", lx=270, ly=196))
    b.append(arrow(315, 234, 370, 234, "是", lx=338, ly=228))
    b.append(arrow(255, 260, 255, 292, "否", lx=270, ly=280))
    b.append(arrow(320, 326, 320, 358))
    b.append(arrow(320, 388, 320, 418))
    b.append(f'<line x1="480" y1="174" x2="480" y2="208" stroke="#444444" stroke-width="1.1" stroke-dasharray="4,3" marker-end="url(#ar)"/>')
    return svg_frame(w, h, "".join(b))

def fig_cli():
    w, h = 640, 400
    b = [DEFS]
    b.append(box(200, 8, 240, 30, ["python -m miniagent 启动", "stdout/stderr reconfigure utf-8(修 GBK)"], fill="#F4F4F4"))
    b.append(box(150, 64, 340, 44, ["形态分派:", "交互 REPL(默认) · --task 一次性 · --resume 重放", "--cleanup-days 清理 · --acp 转 acp.py · --permission ask/auto/yolo"]))
    b.append(box(150, 142, 340, 34, ["交互内命令:", "/exit 退出 · /memory 查看长期记忆 · /compact 手动压缩"]))
    b.append(box(150, 202, 340, 30, ["Agent(workdir) 创建 → run(task) → 打印 final_text"]))
    b.append(box(220, 262, 200, 26, ["退出码 0(冒烟可测)"]))
    b.append(arrow(320, 38, 320, 64))
    b.append(arrow(320, 108, 320, 142))
    b.append(arrow(320, 176, 320, 202))
    b.append(arrow(320, 232, 320, 262))
    return svg_frame(w, h, "".join(b))

def fig_web():
    w, h = 640, 430
    b = [DEFS]
    b.append(box(180, 8, 280, 30, ["浏览器 GET / 查询表单页"], fill="#F4F4F4"))
    b.append(box(150, 58, 340, 34, ["POST /api/query {\"text\": ...}", "长度护栏:空/超 1MB → 400;非 JSON → 400"]))
    b.append(diamond(195, 122, 120, 52, ["并发闸可获取?", "(默认 1)"], fill="#F0F0F0"))
    b.append(box(370, 128, 220, 40, ["429:当前有任务在运行", "(闸=1 防限速雪崩)"], fill="#F6F6F6"))
    b.append(box(150, 204, 340, 38, ["后台线程:独立 workdir", "(WEB_ROOT/时间戳-uuid6)", "Agent(wd, auto).run(text);收集轨迹+usage"]))
    b.append(diamond(195, 272, 120, 52, ["TASK_TIMEOUT", "内完成?"], fill="#F0F0F0"))
    b.append(box(370, 276, 220, 40, ["504 放弃等待;闸保持占用", "直到线程真实结束(Python 线程", "不可安全强杀)"], fill="#F6F6F6"))
    b.append(box(150, 358, 340, 30, ["200 {ok, result, usage, tools, steps}", "key 只走环境变量,绝不进页面/响应"]))
    b.append(arrow(320, 38, 320, 58))
    b.append(arrow(320, 92, 320, 122))
    b.append(arrow(315, 148, 370, 148, "否", lx=338, ly=142))
    b.append(arrow(255, 174, 255, 208, "是", lx=270, ly=196))
    b.append(arrow(320, 242, 320, 272))
    b.append(arrow(315, 298, 370, 298, "否", lx=338, ly=292))
    b.append(arrow(255, 324, 255, 358, "是", lx=270, ly=346))
    return svg_frame(w, h, "".join(b))



def fig_interact():
    w, h = 660, 560
    b = [DEFS]
    # 中轴:loop Agent 实例
    b.append(box(220, 8, 220, 40, ["Agent 实例(loop.py)", "self.messages(会话状态)", "self.drift(DriftCalibrator)"], bold=True, fill="#F6F6F6"))
    # 左上:context.py
    b.append(box(30, 90, 200, 56, ["context.py", "maybe_compact(estimator=drift.estimate)", "head 保护 system(含记忆快照)", "compact/overflow 事件→快照"], fill="#FAFAFA"))
    # 右上:llm provider 真实 usage
    b.append(box(430, 90, 200, 40, ["llm.py 响应", "usage.prompt_tokens", "(真实 tokenizer 计数)"], fill="#FAFAFA"))
    # 校准回路
    b.append(f'<text x="330" y="150" font-size="8" fill="#555555">① 锚点反馈: ratio = 实测/估算(SMA)</text>')
    b.append(arrow(430, 130, 420, 100, "", ly=124))
    b.append(f'<line x1="425" y1="130" x2="425" y2="60" stroke="#444444" stroke-width="1.1" stroke-dasharray="4,3" marker-end="url(#ar)"/>')
    b.append(arrow(440, 60, 440, 48, "", ly=56))
    # loop→context
    b.append(arrow(220, 40, 130, 90, "② 每步 preflight", lx=118, ly=58))
    # context 校准后估算阈值
    b.append(f'<text x="42" y="170" font-size="8" fill="#555555">③ 校准估算 > 85%×MAX_CONTEXT 才压</text>')
    # 左下:memory.py
    b.append(box(30, 210, 200, 46, ["memory.py MEMORY.md", "Agent 创建→安检→烘焙 system 尾部", "save_lesson→provenance 追加", "memory_search 同安检"], fill="#FAFAFA"))
    b.append(arrow(130, 146, 130, 210, "", ly=180))
    b.append(f'<text x="140" y="185" font-size="8" fill="#555555">④ 快照位于 messages[0](head)→ 永不进中段</text>')
    # 多源会话:ACP/Web/subagent/resume 四入口
    b.append(f'<text x="440" y="190" font-size="9" fill="#111111" font-weight="bold">多源会话(各自独立 Agent/messages)</text>')
    b.append(box(430, 200, 100, 26, ["ACP session/new", "_sessions{uuid}"], fill="#F4F4F4"))
    b.append(box(535, 200, 100, 26, ["web /api/query", "独立 workdir"], fill="#F4F4F4"))
    b.append(box(430, 232, 100, 26, ["delegate_task", "子 Agent(38 行)"], fill="#F4F4F4"))
    b.append(box(535, 232, 100, 26, ["--resume", "重放(修协议对)"], fill="#F4F4F4"))
    b.append(f'<text x="440" y="278" font-size="8" fill="#555555">互不共享 messages;同 workdir 仅共享磁盘文件</text>')
    b.append(f'<text x="440" y="290" font-size="8" fill="#555555">与项目 MEMORY.md(追加行原子)</text>')
    # 底部:session transcript
    b.append(box(200, 320, 260, 40, ["session.py JSONL transcript", "message / compact快照 / overflow_heal / usage", "resume: 重放遇快照即切换;孤儿tool丢弃/缺result补占位"], fill="#FAFAFA"))
    b.append(arrow(280, 48, 280, 320, "", ly=200))
    b.append(f'<text x="288" y="310" font-size="8" fill="#555555">⑤ 每步落盘</text>')
    # 底部说明框
    b.append(box(30, 396, 600, 150, [
        "交互要点:",
        "① 漂移校准: chars/4 对中文低估约 2x;每次真实 usage 反馈 ratio(EMA,夹[0.25,4]);校准后估算驱动 85% 阈值",
        "   → 压缩提前到正确时点,不再依赖溢出自愈(413 往返)兜底。未校准首步退化为纯 chars/4(保守方向:低估→触发偏晚→自愈兜底)。",
        "② context×memory: 记忆快照烘焙进 messages[0](system);context 的 head=messages[:2] 恒保护它 → 压缩永不触碰记忆",
        "   与技能索引(同在 system 尾部) → 免疫包裹 + head 保护双保险,摘要劫持形态天然免疫。",
        "③ 多源隔离: 四入口各自独立 Agent/messages/drift;物理上不可能互相污染上下文。共享面仅限磁盘(workdir 文件+",
        "   MEMORY.md 行级原子追加)。resume 是唯一跨进程通路 → 协议对修复兜底崩溃截断。",
    ], fill="#F6F6F6", fs=8.5))
    return svg_frame(w, h, "".join(b))


FIGS = {
    "loop": fig_loop, "interact": fig_interact, "context": fig_context, "tools": fig_tools,
    "sandbox": fig_sandbox, "memory": fig_memory, "skills": fig_skills,
    "hooks": fig_hooks, "acp": fig_acp, "session": fig_session,
    "subagent": fig_subagent, "llm": fig_llm, "cli": fig_cli, "web": fig_web,
}

# ---------------- 内容 ----------------

def chapter(no, title, desc):
    return (f'<div class="chapter-title">{no}、{title}</div>'
            f'<div class="chapter-rule"></div>'
            f'<div class="chapter-desc">{desc}</div>')

def mtitle(text): return f'<div class="m-title">{text}</div>'
def sect(text): return f'<div class="sec-title">{text}</div>'
def sub(text): return f'<div class="sub-title">{text}</div>'
def fig(key, cap): return f'<div class="fig">{FIGS[key]()}</div><div class="figcap">{cap}</div>'
def note(text): return f'<div class="note">{text}</div>'
def why(text): return f'<div class="why"><b>为什么这样设计:</b>{text}</div>'
def lvl(n):
    m = {0: "l0", 1: "l1", 2: "l2", 3: "l3"}
    return f'<span class="pill {m[n]}">[L{n}]</span> '
def layer(l): return f'<span class="pill layer">{l}</span> '

def wf_table(rows):
    """分层工作流表: | 层 | 输入 | 输出 | 关键步骤 |"""
    h = ('<tr><th style="width:12%">层</th><th style="width:22%">输入</th>'
         '<th style="width:24%">输出</th><th style="width:42%">处理(关键步骤)</th></tr>')
    body = "".join(
        f'<tr><td><b>{r[0]}</b></td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td></tr>'
        for r in rows)
    return f'<table>{h}{body}</table>'

def build():
    P = []
    P.append(f'''<div class="cover">
<h1>miniagent 完整报告</h1>
<div class="intro">
最小完备 Coding Agent 的设计、实现与验证。对应仓库 <b>github.com/aitachi/miniagent</b>(commit 690eabf,2026-08-17)。
核心约 1,500 行(15 个 Python 文件、13 个实质模块),唯一第三方依赖 requests;Python 3.10+,Docker 可跑,默认后端 qwen3.7-max(30 万上下文)。
本报告对齐 LeetCode 合并严格版版式(黑白灰,无彩色渲染);每个模块配<b>知识图谱矢量流程图</b> + <b>分层工作流表</b> + <b>分层描述</b>;另设跨模块交互专节(token 漂移校准 · 多源会话 · context × memory)。
</div>
<div class="intro" style="border-left-color:#CC0000;">
对齐最新代码:本版含 <b>token 漂移校准(DriftCalibrator 锚点反馈)</b>与 <b>resume 协议对修复</b>;65/65 离线回归;并反映 690eabf「isolate sessions and align module contracts」 —— ToolRuntime/HookManager 实例化(会话不再串绑);compact/overflow 事件携带消息快照(resume 不再回退到压缩前);会话文件名独占创建防并发碰撞;sandbox 只读名单与注册表同源;web 并发闸超时后保持占用。
历史遗留:2026-08-16 压测发现的「跨进程 resume 丢失压缩摘要」已在本版修复。
</div>
<h1 style="font-size:14px; margin-top:20px;">目录(7 大板块 / 13 模块)</h1>
<ol>
<li>概览(设计宪法 · 三层架构 · 验证证据)</li>
<li>模块设计(13 模块:分级表 + 每模块流程图 + 分层工作流表 + 分层描述)</li>
<li>如何运行(环境变量 · 三形态 + Web · 扩展点)</li>
<li>对比报告(miniagent vs kimi-code vs dsh vs Hermes)</li>
<li>问题与解决(实测问题清单 · 已知边界)</li>
<li>工程问答(16 题,三面)</li>
<li>压力测试与问题发现(2026-08-16 实测 + 修复对照)</li>
</ol>
</div>''')

    # ============ 1 概览 ============
    P.append(chapter(1, "概览", "miniagent 是一个能自动写代码的 Agent Harness:把一个只会生成 token 的模型,变成一个能读文件、跑命令、记教训、守边界的工程实体。两条设计宪法贯穿所有模块。"))
    P.append(note("<b>宪法一 · Prompt Cache 神圣</b> —— 同一 Agent 会话内 system 前缀冻结;动态内容(记忆、steer)一律注入消息尾部;正常步骤只追加,压缩则以显式快照事件替换中段。<br><b>宪法二 · 窄腰核心</b> —— 核心 = 一个循环 + 一个消息列表 + 一个工具调用协议;沙盒/记忆/技能/Hooks/ACP/Web 全部挂在边上。"))
    P.append(sub("1.1 三层架构"))
    P.append('''<pre class="arch">表面层   cli.py(终端交互/一次性任务) · web.py(HTTP 查询表单) · acp.py(stdio JSON-RPC 宿主)
─────────────────────────────────────────────────────────────────
Harness  loop.py(窄腰核心 Agent:while ask→act→append)
          ├─ context.py   每步 preflight 压缩(85% 阈值/头尾保留/免疫包裹)
          ├─ tools.py     Agent 实例级 ToolRuntime + 11 工具 + 校验 + 50K 落盘治理
          ├─ sandbox.py   注册表同源工具集→hardline→三分级→路径工具围栏
          ├─ hooks.py     Agent 实例级 HookManager + 进程外 hook(30s 强杀)+ stop 闩锁
          ├─ memory.py    MEMORY.md 冻结快照 + provenance 追加 + 注入安检
          ├─ skills.py    SKILL.md 索引常驻一行 + 正文按需注入
          ├─ subagent.py  delegate_task 隔离派生(独立上下文/预算/transcript)
          └─ session.py   JSONL transcript + 压缩快照重放(坏行容错)
─────────────────────────────────────────────────────────────────
模型层   llm.py → qwen3.7-max(OpenAI 兼容,429/5xx 指数退避重试)</pre>''')
    P.append(sub("1.2 验证证据(全部现场实测)"))
    P.append('''<table>
<tr><th style="width:52%">验证</th><th>结果</th></tr>
<tr><td>本次离线模块回归(FakeLLM/Mock,覆盖 13 个模块 + 漂移校准 + 协议对修复)</td><td><b>65/65 OK</b></td></tr>
<tr><td>本次在线模型回归</td><td>未运行:dev-server 未配置 MINIAGENT_API_KEY,未借用其他项目密钥</td></tr>
<tr><td>现场写项目 taskcli(待办 CLI)</td><td>18 tests OK,agent 自愈空 JSON bug 并沉淀教训</td></tr>
<tr><td>Docker 内现场写项目 expense-cli</td><td>15 tests OK,干净容器复跑一致</td></tr>
<tr><td>5 个复杂压力任务(T1–T5)</td><td>39/19/54/26 tests OK,73 次工具调用 0 错误</td></tr>
<tr><td>hook 阻断适配探针</td><td>pip install 被进程外 hook 阻断→模型不重试、改标准库完成</td></tr>
<tr><td>大文件结果治理</td><td>241KB 日志→模型只见 2,130 字符 preview,全量落盘</td></tr>
<tr><td>--resume 会话恢复</td><td>重放后模型准确回忆上轮文件名与统计结果</td></tr>
<tr><td>上下文压缩实战(小窗口强制)</td><td>压缩真实触发 2 次,免疫包裹注入,任务完成</td></tr>
<tr><td>delegate_task 子代理</td><td>父子 transcript 分离;子代理 11 次探索仅回传蒸馏报告</td></tr>
<tr><td>密钥卫生</td><td>子进程环境剥离 KEY/TOKEN 类变量;工作区零密钥痕迹</td></tr>
</table>''')

    # ============ 2 模块设计 ============
    P.append(chapter(2, "模块设计", "每个模块 = 一个文件 = 教程一章的「最小设计」+ 必要的第 1~2 级演化;每份复杂性都对应一个真实痛点。分级:[L0] 骨架(能跑) · [L1] 健壮(失败路径处理) · [L2] 生产化(生产事故反推的机制) · [L3] 演化(对照 kimi/Hermes 的下一级,按需取不强上)。"))
    P.append(sub("2.1 模块分级表(13 模块)"))
    P.append('''<table>
<tr><th>#</th><th>模块</th><th>行</th><th>职责一句话</th><th>分级</th><th>防什么事故</th><th>参照物</th></tr>
<tr><td>1</td><td>loop.py</td><td>231</td><td>主循环 ask→act→append,唯一窄腰核心</td><td>[L2]</td><td>死循环烧钱、崩溃丢进度、不可回放</td><td>kimi 主循环</td></tr>
<tr><td>2</td><td>context.py</td><td>118</td><td>每步 preflight 压缩(85% 阈值)</td><td>[L2]</td><td>token 溢出即死;粗暴截断打碎缓存</td><td>kimi 阈值+头尾保留</td></tr>
<tr><td>3</td><td>tools.py</td><td>372</td><td>实例级 runtime+11 工具注册/校验/治理</td><td>[L2]</td><td>会话串绑、schema 漂移、超长结果灌窗</td><td>kimi 截断+落盘</td></tr>
<tr><td>4</td><td>sandbox.py</td><td>120</td><td>注册表同源名单+hardline+权限+路径围栏</td><td>[L3]</td><td>未知工具、危险命令、路径越界</td><td>Hermes hardline 先于 yolo</td></tr>
<tr><td>5</td><td>memory.py</td><td>103</td><td>冻结快照+追加+快照/搜索注入安检</td><td>[L2]</td><td>跨项目串记忆、毒记忆劫持新会话</td><td>kimi AppendLogStore</td></tr>
<tr><td>6</td><td>skills.py</td><td>86</td><td>索引一行常驻,正文按需取</td><td>[L1]</td><td>提示词膨胀撑爆前缀缓存</td><td>kimi 三层披露</td></tr>
<tr><td>7</td><td>hooks.py</td><td>166</td><td>实例级 5 事件+进程外 hook+闩锁</td><td>[L2]</td><td>会话串 hook、hook 崩溃、stop 死锁</td><td>kimi stopHook 闩锁</td></tr>
<tr><td>8</td><td>acp.py</td><td>104</td><td>stdio JSON-RPC 多 session 分发</td><td>[L1]</td><td>一条 print 毁掉协议流、session 串线</td><td>ACP 协议</td></tr>
<tr><td>9</td><td>session.py</td><td>93</td><td>JSONL 消息/压缩快照重放+TTL</td><td>[L2]</td><td>压缩后 resume 回退;并发文件名碰撞</td><td>kimi append-only</td></tr>
<tr><td>10</td><td>subagent.py</td><td>38</td><td>delegate_task 上下文隔离派生</td><td>[L1]</td><td>探索污染主线;父子压缩分叉</td><td>kimi 扁平子代理</td></tr>
<tr><td>11</td><td>llm.py</td><td>114</td><td>OpenAI 兼容+退避重试+溢出自愈</td><td>[L2]</td><td>429/5xx、arguments 解析失败</td><td>kimi 溢出自愈≤3</td></tr>
<tr><td>12</td><td>cli.py</td><td>106</td><td>交互/一次性/ask 三形态</td><td>[L1]</td><td>GBK 乱码、无恢复入口</td><td>—</td></tr>
<tr><td>13</td><td>web.py</td><td>171</td><td>HTTP 表面+独立 workdir+并发闸</td><td>[L1]</td><td>请求串目录、超时后并发闸失效</td><td>—</td></tr>
</table>''')

    P.append(sub("2.2 整体工作流(知识图谱)"))
    P.append(fig("loop", "图 1  loop.py 窄腰主循环:入口护栏 → preflight → chat → tool_calls 裁决链执行 → append 回环;预算耗尽 grace 收尾;stop 闩锁续跑 ≤1 次"))
    P.append(why("主线是中间纵列的一次 turn。每一步先过 context.py 的 preflight(窗口没超就原样放行,<b>前缀不动即缓存命中</b>),再把消息列表发给模型;模型要么回文本(不调工具→循环结束),要么回 tool_calls。每次工具调用依次经过注册/参数校验 → hardline/权限裁决 → before_tool hook;未知、畸形或危险调用不会进入 before_tool/handler,after_tool 仍统一收到失败结果。任何一环说「不」都把错误文本回填给模型自行换路 —— 这是 miniagent 最核心的<b>自愈语义</b>。"))
    P.append(note("<b>一个真实 turn 的走读</b>(历史压测任务,30 万窗口被真实逼近):模型先 read_file 一个 240KB 日志 → 结果治理触发,全量 255,935 字符落盘,模型只见 2,130 字符 preview + 文件路径 → 模型按 preview 判断再 grep 定位 → 若干步后 preflight 估算超 85%,中段被摘要压缩(免疫包裹注入,system 与首条 user 原样保留)→ 任务继续直到最终总结。消息与压缩后的消息快照都写入 transcript;--resume 按事件顺序恢复<b>压缩后的真实上下文</b>,而不是回到压缩前。"))

    # ---- 每模块:图 + 分层表 + 分层描述 ----
    P.append(sub("2.3 逐模块详述(每模块:知识图谱流程图 + 分层工作流表 + 分层描述)"))

    # 1 loop
    P.append(mtitle("模块 1 · loop.py 主循环(231 行) " + lvl(2) + "· 层:主管"))
    P.append(fig("interact", "图 1-1  loop.py 与 context/memory 的交互视图(与图 1 主流程图互补:图 1 看控制流,本图看数据流——估算/快照/记忆三向交互)"))
    P.append(wf_table([
        ("①入口", "user_text / --resume transcript", "拒绝文案或进入主循环", "len > MAX_INPUT_CHARS(20万) 直接拒,零 LLM 消耗;resume 则 reconstruct_messages 重建(含压缩快照)"),
        ("②会话开启", "workdir + task", "session_start 事件 + user 消息", "hooks.fire(session_start);_record(user)逐条落 transcript"),
        ("③主循环", "messages(上轮)", "assistant / tool 消息", "每步先 _compact() preflight → _chat() → 无 tool_calls 即 break;有则逐个 _run_tool → result _record → 回环"),
        ("④预算", "steps 计数", "grace 收尾文本", "steps ≥ MAX_STEPS(60) → 追加一条「请总结」的 user → 最后一次 chat,不再执行工具"),
        ("⑤终止", "final_text", "stop hook / session_end", "stop 阻断且闩锁可用 → 注入 reason 续跑(每 turn 仅一次);否则 fire(session_end) + usage 落盘"),
    ]))
    P.append("<p><b>分层描述:</b>入口层拦截恶意长文本;会话层发事件并记录首条消息;循环层承担 ask→act→append 全部语义;预算层兜底失控;终止层保证 stop hook 不会把 turn 变成永动机。四条不变量:消息列表是会话状态;终止由模型决定;工具错误作为文本回填让模型自愈;正常步骤只追加、压缩以显式快照替换中段。</p>")
    P.append(why("把「循环」本身压缩到能穷举测试的体量,所有策略(压缩/安全/记忆)都以 preflight 或事件的形式插在循环的固定点上 —— 换 provider、换存储、换表面都不需要动 loop.py,这是「窄腰」的具体含义。"))

    # 2 context
    P.append(mtitle("模块 2 · context.py 上下文压缩(118 行) " + lvl(2) + "· 层:治理"))
    P.append(fig("context", "图 2-1  context.py 知识图谱:估算 → 85% 阈值 → head/tail 定界 → 中段摘要 → 免疫包裹 → 快照替换"))
    P.append(wf_table([
        ("①估算", "messages + MAX_CONTEXT + drift.ratio", "校准后估算 tokens", "chars/4 × 漂移系数;系数由每次真实 usage.prompt_tokens 锚点反馈(EMA,夹[0.25,4]);未超 85% 原样返回 —— 前缀不动,缓存命中"),
        ("①'漂移校准", "provider usage.prompt_tokens", "drift.ratio 更新", "每次 _chat 后:ratio = 实测/估算,指数滑动平均 α=0.3,单点夹 [0.25,4];中文场景 chars/4 低估约 2x,不校准则压缩触发偏晚,靠溢出自愈兜底(413 往返)"),
        ("②定界", "超阈值 messages", "head / middle / tail 三段", "head = system(含记忆快照+技能索引)+ 首条 user;tail 从尾部倒走 ≤20% 预算,不切 tool_call/result 对,最后一条 user 必在 tail"),
        ("③摘要", "middle 文本", "单段结构化摘要", "LLM 单次摘要(摘要调用本身也产生 usage 锚点);失败 fail-open 保留原会话,不阻塞主循环"),
        ("④免疫包裹", "摘要文本", "带包裹的摘要消息", "[CONTEXT COMPACTION — REFERENCE ONLY] + 声明最新用户消息优先,防摘要旧指令被当成现行指令"),
        ("⑤替换", "head+摘要+tail", "新 messages(写回调用方)", "调用方(loop)把新列表连同 {type:compact, messages} 快照写入 transcript —— resume 恢复压缩后真实上下文"),
    ]))
    P.append("<p><b>分层描述:</b>校准层回答「估得准不准」(真实 usage 锚点持续纠偏 chars/4 的中文低估);估算层回答「要不要压」;定界层回答「保什么、压什么」—— head 恒含记忆快照与技能索引,压缩永不触碰;摘要层回答「怎么压」;包裹层防劫持;替换层保证 resume 能恢复压缩后的真实上下文。</p>")
    P.append(why("不切协议对是因为 OpenAI 协议里 tool_call 与其 result 必须成对出现,从中间切断直接 400 报错;85% 阈值留出的 15% 余量,正是给单条大工具结果(最坏 2K preview + 若干条消息)的缓冲。<b>token 漂移</b>:chars/4 对中文低估约 2x,本版加 DriftCalibrator —— 每次真实 usage 锚点反馈(EMA α=0.3,单点夹 [0.25,4]),校准系数直接驱动 85% 阈值判定与 tail 预算。这是 kimi「锚点实测+估算」双层计量的最小版:不引入阻塞式测量 job,用顺路得到的 usage 做零成本校准。"))

    # 3 tools
    P.append(mtitle("模块 3 · tools.py 工具运行时(372 行) " + lvl(2) + "· 层:执行"))
    P.append(fig("tools", "图 3-1  tools.py 知识图谱:全局注册表 → Agent 冻结 ToolRuntime → 校验 → 执行 → 结果治理(50K 落盘/2K preview)"))
    P.append(wf_table([
        ("①注册", "@tool(name, desc, schema, readonly)", "REGISTRY 条目", "注册必须在 Agent 创建前;重名/非法名/非 object schema 直接报错(fail-fast)"),
        ("②快照", "Agent.__init__", "ToolRuntime 实例", "冻结 schema/handler/readonly 快照 + 绑定本 Agent 的 sandbox/skills/memory;运行中新增工具只对之后创建的 Agent 生效"),
        ("③校验", "tool_calls(name+args)", "通过或错误文本", "required/类型/额外参数逐项校验;校验失败不执行,错误文本回填(不触发 before_tool)"),
        ("④执行", "合法调用", "result 消息", "handler 执行,异常捕获不外抛;顺序 = sandbox → before_tool → handler → after_tool"),
        ("⑤治理", "原始输出", "2K preview(+落盘路径)", "输出 >50K 字符全量落盘 .miniagent/tool_results/;bash 另有 30K 截断 + 120s 超时"),
    ]))
    P.append("<p><b>分层描述:</b>注册层维护唯一事实源;快照层把「这一会话能用哪些工具」固化,防会话间串绑与 schema 漂移;校验层挡畸形调用;执行层保证异常不炸循环;治理层保证单条输出灌不爆 30 万窗口。11 个内置工具:read_file / list_dir / grep / glob / write_file / edit_file / bash / skill_view / save_lesson / delegate_task / memory_search。</p>")
    P.append(why("结果治理的 2K preview 是「模型按需再取」协议:模型看到 preview 判断是否 grep 定位,而不是把 24 万字符直接灌进窗口 —— 实测 T5 单条 read_file 结果 25 万字符被治理在 2,130 字符。"))

    # 4 sandbox
    P.append(mtitle("模块 4 · sandbox.py 沙盒权限(120 行) " + lvl(3) + "最小版 · 层:裁决"))
    P.append(fig("sandbox", "图 4-1  sandbox.py 知识图谱:去混淆 → hardline → fail-closed → 只读/模式分级 → workdir 围栏 + 环境剥离"))
    P.append(wf_table([
        ("①去混淆", "tool 名 + args", "规范化后的匹配串", "NFKC 全角折叠 + $IFS/${IFS} 折叠 + 引号拼接剥离,再做 hardline 匹配"),
        ("②hardline", "匹配串", "拒绝或放行", "rm -rf / · mkfs · dd 裸设备 · fork bomb · 写 authorized_keys 等,<b>yolo 也不放行</b>"),
        ("③fail-closed", "工具名", "未知即拒", "注册表快照内无名 → 拒;调用方也不能用参数把写工具伪装成只读"),
        ("④分级", "readonly 标记 + 模式", "允许/询问/拒绝", "readonly 默认放行;yolo/auto 放行;ask 走回调,无回调/异常默认拒绝"),
        ("⑤围栏", "路径参数 / bash", "受控执行", "路径工具 realpath 必须落在 workdir 内(防符号链接逃逸);bash 固定 cwd + sanitized_env() 剥 KEY/TOKEN/PASSWORD/SECRET/CREDENTIAL"),
    ]))
    P.append("<p><b>分层描述:</b>去混淆层保证规则匹配的是命令的真实语义;hardline 层是不可让渡的底线;fail-closed 层保证白名单外无路可走;分级层把「用户授权」变成显式模式;围栏层是最后一道物理边界。注意边界:bash 只是规则裁决 + 固定 cwd + 环境剥离,<b>不是 OS 级文件系统隔离</b>;无人值守应套容器/E2B。</p>")
    P.append(why("「用户已授权」不能成为无恢复路径破坏的通行证 —— 用户可能被钓鱼、被注入、或只是没意识到命令后果。危险检测是工程层的不可让渡职责,所以 hardline 在裁决链第一环,先于任何授权模式。"))

    # 5 memory
    P.append(mtitle("模块 5 · memory.py 长期记忆(103 行) " + lvl(2) + "· 层:会话边界"))
    P.append(fig("memory", "图 5-1  memory.py 知识图谱:load_snapshot 安检 → 烘焙 system 尾部冻结;save_lesson provenance 追加;超限 tmp+rename;memory_search 只读检索"))
    P.append(wf_table([
        ("①快照", "MEMORY.md(每 workdir 独立)", "安检后的快照文本", "Agent 创建时读全文,逐行 _scan() 注入安检,命中 promptware 模式替换占位符"),
        ("②烘焙", "快照文本", "system prompt 尾部", "BASE_PROMPT + 快照 + skills 索引,创建后冻结 —— 前缀缓存全程命中"),
        ("③追加", "save_lesson(text)", "- [UTC ts] text 一行", "规范化为单条记录;单次 write 行级原子;相同 workdir 的会话有意共享项目记忆,不同 workdir 不共享"),
        ("④截断", "文件 >8K", "保留最近条目", "按行保留累计 ≤KEEP_CHARS 的最近条目,tmp+rename 原子替换(读取方不会看到半个文件)"),
        ("⑤检索", "memory_search(keyword)", "命中行(≤20)", "平文件关键词检索 + 同样安检;容量上限即精度:检索域永远小到关键词足够准"),
    ]))
    P.append("<p><b>分层描述:</b>快照层负责「会话开始时看到什么」;烘焙层用冻结换缓存;追加层负责「会话学到什么」(下个 Agent 才生效,天然避开 turn 内竞态);截断层防无限增长;检索层补一个只读取数。防线在写入侧与加载侧双重安检,毒条目既不进 system 也不进检索域。</p>")
    P.append(why("记忆快照若随会话内容变化,system prompt 前缀就变了,前缀缓存全部失效 —— 每轮都付全价 token。「冻结 + 尾部注入」用一点信息滞后换取整场会话的缓存命中,是缓存宪法的直接应用。"))

    # 6 skills
    P.append(mtitle("模块 6 · skills.py 技能(86 行) " + lvl(1) + "· 层:按需"))
    P.append(fig("skills", "图 6-1  skills.py 知识图谱:扫描 frontmatter → 索引一行常驻 system → skill_view 按需取正文"))
    P.append(wf_table([
        ("①扫描", "skills/ 与 .miniagent/skills/", "技能清单", "每个 <name>/SKILL.md 解析 frontmatter(name + description)"),
        ("②索引", "技能清单", "index_text() 一行/技能", "常驻 system prompt 尾部(约百字符级),提示模型「有这个技能存在」"),
        ("③取用", "skill_view(name)", "SKILL.md 全文", "正文按需注入 turn 内上下文;未调用则零成本"),
    ]))
    P.append("<p><b>分层描述:</b>扫描层发现;索引层常驻但极小;取用层延迟绑定。这是 kimi 三层披露的最小两层:索引常驻 + 正文按需,防止提示词膨胀撑爆前缀缓存。</p>")

    # 7 hooks
    P.append(mtitle("模块 7 · hooks.py 钩子(166 行) " + lvl(2) + "· 层:事件"))
    P.append(fig("hooks", "图 7-1  hooks.py 知识图谱:5 事件 → 回调表 + 进程外 hook → 30s 强杀 → 阻断语义 → stop 一次性闩锁"))
    P.append(wf_table([
        ("①事件源", "主循环固定点", "5 事件 payload", "session_start / session_end / before_tool / after_tool / stop;只有 before_tool 和 stop 可阻断"),
        ("②实例隔离", "Agent 创建", "独立 HookManager", "new_manager() 从全局配置复制;clone() 出子代理副本;on_event 不污染其他会话"),
        ("③进程外", "hooks.d/<event>_*.py", "block:reason / 通过", "子进程运行、stdin 传 JSON、30s 超时强杀、崩溃只记 stderr;stdout 打印 {\"decision\":\"block\"} 即阻断"),
        ("④闩锁", "stop 阻断", "续跑 ≤1 次", "StopLatch 一次性:防「hook 永远 block → turn 永不结束」"),
        ("⑤可见性", "任何工具调用结果", "after_tool 统一通知", "未知/畸形/权限拒绝不触发 before_tool,但 after_tool 仍收到失败结果 —— 审计不缺角"),
    ]))
    P.append("<p><b>分层描述:</b>事件层定义契约;隔离层防会话串 hook;进程外层把不可信代码推到子进程并限时;闩锁层防死锁;可见性层保证遥测完整。</p>")

    # 8 acp
    P.append(mtitle("模块 8 · acp.py ACP 宿主(104 行) " + lvl(1) + "· 层:表面"))
    P.append(fig("acp", "图 8-1  acp.py 知识图谱:stdin 逐行帧 → method 分发 → 多 session 字典 → stdout 纯协议帧/错误显式码"))
    P.append(wf_table([
        ("①解析", "stdin 每行一帧", "请求或 notification", "带 id → 请求(须回复);无 id → notification 静默"),
        ("②分发", "method 名", "Agent 调用/结果帧", "initialize 能力握手;session/new 新建 Agent 存 _sessions{uuid:hex};session/prompt 按 sessionId 取 Agent 跑"),
        ("③错误", "未知 method/sessionId", "显式错误码", "未知 method → -32601;未知 sessionId → -32602;协议可观测,不静默吞错"),
        ("④流控", "一切输出", "stdout 纯协议", "stdout 只走协议帧(一条 print 也不混入);日志/调试全走 stderr"),
    ]))
    P.append("<p><b>分层描述:</b>解析层定帧;分发层维护多 session 字典(每 session 一个独立 Agent,不串线);错误层把失败变成协议内的显式信号;流控层保证宿主能可靠解析 stdout。这是「一条 print 毁掉协议流」事故的反面设计。</p>")

    # 9 session
    P.append(mtitle("模块 9 · session.py 会话持久化(93 行) " + lvl(2) + "· 层:持久"))
    P.append(fig("session", "图 9-1  session.py 知识图谱:JSONL 追加(消息/compact 快照/usage)→ 重放遇快照即切换 → 独占创建防碰撞 → TTL 清理"))
    P.append(wf_table([
        ("①追加", "每条消息/事件", "JSONL 一行", "单次 write 崩溃原子;坏行容错跳过(resume 时)"),
        ("②快照事件", "compact / overflow_heal", "替换性事件", "携带替换后的完整 messages 快照 —— 修复了历史「跨进程 resume 丢失压缩摘要」缺陷"),
        ("③重放", "transcript 路径", "重建 messages(协议对已修复)", "reconstruct_messages() 按事件顺序:message 追加,遇 compact 快照直接采用、丢弃其前历史;末尾 _repair_tool_pairs():孤儿 tool 丢弃、缺 result 补占位(防崩溃截断 → 下一条 chat 直接 400)"),
        ("④命名", "新会话", "唯一文件名", "时间戳 + open(x) 独占创建;同秒并发 Agent 也不会拿到同一路径"),
        ("⑤清理", "mtime TTL", "删除计数", "cleanup_old_sessions(默认 30 天);CLI --cleanup-days 可调;子代理 transcript 独立文件"),
    ]))
    P.append("<p><b>分层描述:</b>追加层是「会话即账本」;快照层让压缩成果可持久;重放层让崩溃恢复回到<b>合法可发送</b>的真实上下文(协议对完整性修复是 resume 唯一跨进程通路上的最后防线);命名层防并发覆盖;清理层防无限增长。</p>")
    P.append(why("存储选型 JSONL 而非 Redis:只要恢复 → 追加日志够用,要检索才上库。压缩快照一行约放大 3K chars,换取 resume 不重付全量 prompt —— 压测中该缺陷曾致 5 用户多付约 30 次摘要调用,本版已修。"))

    # 10 subagent
    P.append(mtitle("模块 10 · subagent.py 子代理(38 行) " + lvl(1) + "· 层:派生"))
    P.append(fig("subagent", "图 10-1  subagent.py 知识图谱:delegate_task → 全新 Agent(六独立)→ 完整 mini-loop → distill ≤10K 回传,过程零主线污染"))
    P.append(wf_table([
        ("①派生", "delegate_task(task)", "全新 Agent 实例", "独立 messages / ToolRuntime / HookManager / transcript / 预算 30 步 / stop 闩锁"),
        ("②执行", "子任务描述", "完整 mini-loop", "同 system 前缀(暖缓存);有意共享 workdir 文件与项目记忆 —— 能操作同一项目,隔离的是上下文与运行时绑定"),
        ("③回传", "子代理最终文本", "distill ≤10K", "截断回传作为 result 消息;探索过程只进子 transcript,主线零污染"),
    ]))
    P.append("<p><b>分层描述:</b>派生层物理隔离上下文(父压缩碰不到子);执行层跑完整循环;回传层只给结论不给过程。对照 Hermes #38727 事故(父与 fork 共享 session 同时压缩 → 历史分叉):本设计从结构上免疫。</p>")

    # 11 llm
    P.append(mtitle("模块 11 · llm.py LLM 客户端(114 行) " + lvl(2) + "· 层:通信"))
    P.append(fig("llm", "图 11-1  llm.py 知识图谱:enable_thinking:false → 429/5xx 退避 ≤5 → 溢出强制压缩重试 ≤3 → arguments 解析降级 → usage 账本"))
    P.append(wf_table([
        ("①请求", "messages + tools schema", "HTTP 请求", "OpenAI 兼容 chat;enable_thinking:false 放 body 顶层(qwen3 系必须,否则混入思考 token)"),
        ("②重试", "429/5xx/超时", "退避后重发", "指数退避 ×2 上限 30s + 20% 抖动 + 尊重 Retry-After,最多 5 次;仍失败 raise LLMError"),
        ("③溢出自愈", "错误含 context/overflow/length", "压缩后重试", "force=True 强制压缩再试,连续 3 次放弃(kimi 认领 413 同构;loop._chat 驱动)"),
        ("④解析", "resp.content/tool_calls", "结构化结果", "arguments JSON 解析失败 → 空对象 + error 标记,作为工具错误回填,不触发 hook/handler"),
        ("⑤账本", "resp.usage", "累计计数", "prompt/completion/calls 每步累加,turn 结束落 transcript(成本可审计)"),
    ]))
    P.append("<p><b>分层描述:</b>请求层管协议兼容;重试层管瞬时故障;自愈层管窗口溢出;解析层把模型畸形输出降级为普通错误;账本层把成本变成数据。五层都不改变「失败也是一种结果」的自愈语义。</p>")

    # 12 cli
    P.append(mtitle("模块 12 · cli.py 终端表面(106 行) " + lvl(1) + "· 层:表面"))
    P.append(fig("cli", "图 12-1  cli.py 知识图谱:启动 reconfigure utf-8 → 形态分派 → 交互命令 → Agent.run → 退出码"))
    P.append(wf_table([
        ("①启动", "python -m miniagent", "utf-8 输出流", "stdout/stderr reconfigure utf-8(修复 Windows GBK 输出 emoji 崩溃)"),
        ("②分派", "argv", "运行形态", "交互 REPL(默认) · --task 一次性 · --resume 重放 · --cleanup-days 清理 · --acp 转 acp.py · --permission ask/auto/yolo"),
        ("③交互命令", "REPL 输入", "本地动作", "/exit 退出 · /memory 查看长期记忆 · /compact 手动压缩(走 Agent.compact 落快照)"),
        ("④执行", "任务文本", "final_text", "Agent(workdir).run(task) → 打印;退出码可冒烟"),
    ]))
    P.append("<p><b>分层描述:</b>启动层修编码;分派层把五种形态收敛到一个入口;命令层给交互用户三个逃生口;执行层只是 Agent 的薄壳 —— 表面层不含任何策略。</p>")

    # 13 web
    P.append(mtitle("模块 13 · web.py Web 表面(171 行) " + lvl(1) + "· 层:表面"))
    P.append(fig("web", "图 13-1  web.py 知识图谱:表单页 → POST /api/query → 并发闸(1) → 独立 workdir 后台线程 → 超时放弃等待但闸保持占用 → 200/429/504"))
    P.append(wf_table([
        ("①表单", "GET /", "HTML 表单页", "纯静态表单;key 只走环境变量,绝不进页面/响应"),
        ("②护栏", "POST /api/query", "400 或放行", "请求体长度护栏(空/超 1MB 拒;非法 JSON 拒)"),
        ("③并发闸", "信号量(默认 1)", "429 或进入", "当前有任务运行 → 429 请稍后(防 API 限速雪崩)"),
        ("④执行", "任务文本", "result/usage/tools", "后台线程:独立 workdir(WEB_ROOT/时间戳-uuid6);Agent(wd, auto).run;收集工具轨迹与用量"),
        ("⑤超时", "TASK_TIMEOUT(600s)", "504", "放弃等待;Python 线程不可安全强杀 → 闸保持占用直到任务真实结束,避免超时任务与新任务重叠"),
    ]))
    P.append("<p><b>分层描述:</b>表单层零状态;护栏层拒畸形请求;闸层控并发;执行层隔离 workdir 防请求串目录;超时层诚实处理「杀不掉的线程」—— 这是并发闸超时失效问题的正面设计。</p>")


    # ---- 交互与多源会话专节 ----
    P.append(sub("2.4 跨模块交互:token 漂移 · 多源会话 · context × memory"))
    P.append(fig("interact", "图 2-2  跨模块交互视图:校准回路(loop↔llm usage↔context 阈值)· head 保护(memory 快照永不进中段)· 四入口多源会话(各自独立 Agent/messages,共享面仅限磁盘)"))
    P.append("<p><b>token 漂移(本版新增)。</b>chars/4 对英文近似成立,对中文低估约 2x(Qwen tokenizer 中文 ≈1.5~2 字符/token)。未校准的后果链:估算低估 → 85% 阈值触发偏晚 → 溢出自愈兜底(一次 413 往返 + 全量重压)。本版在 context.py 加 <b>DriftCalibrator</b>:每次 _chat 后用真实 usage.prompt_tokens 对刚送出的 messages 做锚点校准(ratio = 实测/估算,EMA α=0.3,单点夹 [0.25,4] 防畸形),校准系数直接驱动 maybe_compact 的阈值判定与 tail 预算。单测覆盖:首锚点设值/EMA 收敛/夹逼/非法锚点忽略/校准估算。<b>为什么不用阻塞式测量</b>:kimi 的双层计量要在关键点插 token 计量 job;本设计用顺路必然返回的 usage 做零成本校准,首步未校准时退化为纯 chars/4(偏差方向:低估 → 触发偏晚 → 自愈兜底,不会误压),第二步起即有校准。</p>")
    P.append("<p><b>多源会话(四入口)。</b>ACP session/new(_sessions{uuid→Agent})、web /api/query(每请求独立 workdir→独立 Agent)、delegate_task(全新子 Agent)、--resume(重放重建)。四入口<b>各自持有独立 messages / ToolRuntime / HookManager / DriftCalibrator</b>,物理上不可能互相污染上下文;共享面仅限磁盘 —— 同 workdir 的项目文件与 MEMORY.md(行级原子追加 + tmp+rename 截断,多进程安全)。resume 是唯一跨进程上下文通路,因此其重放路径加协议对完整性修复:<b>孤儿 tool 消息丢弃、残缺 assistant(tool_calls) 补占位 result</b> —— 崩溃截断的 transcript 若原样重放,下一条 chat 直接 400 invalid tool message。单测覆盖孤儿丢弃/完整对零改动。</p>")
    P.append("<p><b>context × memory 交互。</b>记忆快照在 Agent 创建时经注入安检后烘焙进 messages[0](system)尾部并冻结;context 的 head = messages[:2] 恒含它 → <b>压缩物理上永不触碰记忆与技能索引</b>;中段摘要再裹 [REFERENCE ONLY] 免疫包裹 → 「摘要劫持」形态双保险免疫。反向交互:save_lesson 写入只发生在会话中(下个 Agent 生效),不触发任何 system 变更 → 前缀缓存全程命中。memory_search 是唯一读取侧通路,同样过 _scan 安检 —— 毒条目既不进 system 也不进检索域。</p>")

    # ============ 3 如何运行 ============
    P.append(chapter(3, "如何运行", "本机 Python / Docker / ACP 宿主 / Web 四种形态;API key 只走环境变量,绝不进代码与镜像。"))
    P.append(sub("3.1 环境变量"))
    P.append('''<table>
<tr><th style="width:30%">变量</th><th style="width:48%">说明</th><th>默认</th></tr>
<tr><td>MINIAGENT_API_KEY</td><td>LLM API key(必填,运行时注入)</td><td>—</td></tr>
<tr><td>MINIAGENT_BASE_URL</td><td>OpenAI 兼容接口</td><td>DashScope compatible-mode</td></tr>
<tr><td>MINIAGENT_MODEL</td><td>模型名</td><td>qwen3.7-max</td></tr>
<tr><td>MINIAGENT_WORKDIR</td><td>沙盒围栏根目录</td><td>当前目录</td></tr>
<tr><td>MINIAGENT_PERMISSION</td><td>ask / auto / yolo</td><td>auto</td></tr>
<tr><td>MINIAGENT_MAX_CONTEXT</td><td>上下文窗口 tokens(阈值 85%)</td><td>300000</td></tr>
<tr><td>MINIAGENT_MAX_STEPS</td><td>每 turn 步数预算</td><td>60</td></tr>
<tr><td>MINIAGENT_SUBAGENT_MAX_STEPS</td><td>子代理独立步数预算</td><td>30</td></tr>
<tr><td>MINIAGENT_MAX_INPUT_CHARS</td><td>入口最大输入字符(超限拒)</td><td>200000</td></tr>
<tr><td>MINIAGENT_WEB_PORT/_TIMEOUT/_CONCURRENCY/_ROOT</td><td>Web 表面层参数</td><td>19120 / 600 / 1 / 临时目录</td></tr>
</table>''')
    P.append(sub("3.2 四种形态"))
    P.append('''<pre># 交互模式(/exit 退出,/memory 看记忆,/compact 手动压缩)
python -m miniagent --workdir /path/to/project

# 一次性任务
python -m miniagent --workdir ./proj --permission auto --task "创建 utils.py 并写好 unittest"

# 恢复会话(重放 transcript 继续,含压缩快照)
python -m miniagent --workdir ./proj --resume .miniagent/sessions/&lt;ts&gt;.jsonl

# Docker
docker run --rm -v /tmp/ws:/workspace -e MINIAGENT_API_KEY=$KEY miniagent:latest \\
  --task "写一个记账 CLI 并跑通 unittest"

# ACP 宿主(stdout 只走协议帧,日志全在 stderr)
python -m miniagent --acp

# Web 表面层(HTTP 查询表单,并发闸+超时+每请求独立 workdir)
python -m miniagent.web

# 测试(65 个离线测试,FakeLLM/Mock 不触网)
python tests/test_all.py</pre>''')
    P.append(sub("3.3 扩展点"))
    P.append('''<table>
<tr><th style="width:14%">扩展</th><th style="width:32%">位置</th><th>说明</th></tr>
<tr><td>自定义技能</td><td>skills/&lt;name&gt;/SKILL.md</td><td>frontmatter 写 name/description,正文即操作手册</td></tr>
<tr><td>进程外 hook</td><td>.miniagent/hooks.d/&lt;event&gt;_*.py</td><td>stdin 收 JSON;stdout 打印 {"decision":"block"} 即阻断</td></tr>
<tr><td>新工具</td><td>tools.py</td><td>@tool 装饰器在 Agent 创建前注册;schema/只读属性自动进入 ToolRuntime 与 sandbox</td></tr>
</table>''')
    P.append(note("<b>工具注册示例</b>:from miniagent.tools import tool → @tool(\"add_numbers\", \"计算两个整数之和。\", {schema}, readonly=True) → 注册必须在创建 Agent 前完成;调用按「解析错误/注册表/参数校验 → sandbox → before_tool → handler → after_tool → 结果治理」执行。"))

    # ============ 4 对比 ============
    P.append(chapter(4, "对比报告:miniagent vs kimi-code vs dsh vs Hermes", "教程对照的三个工业 codebase:kimi-code v0.34、DeepSeek Harness(dsh v0.1.0-rc.5)、hermes-agent 0.18.0。四方设计理念一句话:miniagent=最小完备集; kimi-code=有人值守 CLI;dsh=everything is a plugin;Hermes=无人值守平台。"))
    P.append(sub("4.1 全模块对照表"))
    P.append('''<table>
<tr><th style="width:9%">模块</th><th style="width:23%">miniagent</th><th style="width:22%">kimi-code</th><th style="width:23%">dsh (DeepSeek)</th><th>Hermes</th></tr>
<tr><td>主循环</td><td><b>while 三行语义+预算硬墙</b></td><td>turn/step 队列+错误处理器插件链</td><td>全仓唯一具体循环(loop-agent);取消与静止是一等公民</td><td>预算驱动 while+refund 记账</td></tr>
<tr><td>上下文</td><td><b>单层估算 85%+头尾保留</b></td><td>双层计量(锚点实测+估算)+阻塞式 job</td><td>三层装配线;上下文预算守门人独立成模块</td><td>四阶段压缩+三重反抖动+压缩锁</td></tr>
<tr><td>工具</td><td><b>字典注册表+结果治理</b></td><td>三层折叠+双 policy 正交</td><td>插件即工具;268 子包按 50 功能域组装</td><td>AST 自动发现+足迹 6 级阶梯</td></tr>
<tr><td>沙盒</td><td><b>hardline+去混淆+三分级(进程内)</b></td><td>12 节静态权限链(进程内,微秒级)</td><td>进程级文件效果沙盒+E2B 远程执行世界</td><td>8 层纵深+Smart Approval+网络出口隔离</td></tr>
<tr><td>记忆</td><td><b>MEMORY.md 冻结快照+安检</b></td><td>无跨会话记忆(有意)</td><td>无 memory 模块(有意):日志即记忆</td><td>双路注入+fork 巩固+漂移检测</td></tr>
<tr><td>技能</td><td><b>frontmatter 两层披露</b></td><td>双路激活+wire 记账</td><td>三件套+Provider 契约+双层注册表</td><td>纯文档契约+紧/松双闭环 curator</td></tr>
<tr><td>子代理</td><td><b>delegate_task 单点派生</b></td><td>扁平子代理+swarm 限速</td><td>编排层独立成章:6 provider+Workflow+Ralph</td><td>fork 5 重隔离</td></tr>
<tr><td>持久化</td><td><b>JSONL 追加+快照重放</b></td><td>wire.jsonl 事件溯源</td><td>SessionEvent 日志,"logged" 不变量</td><td>SQLite 双 FTS5+软删归档</td></tr>
<tr><td><b>设计理念</b></td><td><b>最小完备,痛了再加</b></td><td>确定性优先,用户在场</td><td>归约主义:拒绝新状态容器</td><td>纵深防御,无人值守</td></tr>
</table>''')
    P.append(sub("4.2 三点结构性观察"))
    P.append("<p>① 记忆的四种答案是四方分歧最大的地方 —— miniagent 平文件快照 / kimi 干脆不要 / dsh 用「没有 memory 模块」这个否定本身作答案(日志即记忆)/ Hermes 上双路注入+巩固流水线;选哪条路线取决于「无人值守程度」与「跨会话学习收益」的权衡。② 沙盒的进程边界是第二个分水岭:miniagent/kimi 在进程内做规则裁决(快但同进程),dsh/Hermes 把执行推到进程级沙盒(慢一档但爆炸半径小一档)。③ 插件化的代价在 dsh 上可见:268 子包换来可整包替换的 loop,认知负担巨大 —— miniagent 的单包是刻意的反面选择。</p>")
    P.append(sub("4.3 行为差异与选型结论"))
    P.append('''<table>
<tr><th style="width:14%">维度</th><th>miniagent</th><th>kimi-code</th><th>Hermes</th></tr>
<tr><td>代码量</td><td><b>核心约 1,500 行(15 文件)</b></td><td>数万行(loopService 1,222 行)</td><td>更大(conversation_loop 5,294 行)</td></tr>
<tr><td>延迟</td><td><b>非流式整段返回</b></td><td>流式优先,首 token 一等指标</td><td>事件回调外发</td></tr>
<tr><td>失控兜底</td><td><b>max_steps 硬墙+stop 闩锁</b></td><td>插件链</td><td>预算硬墙+refund+退出诊断</td></tr>
<tr><td>无人值守</td><td><b>有限(bash 需外套容器)</b></td><td>低(设计前提:用户在终端前)</td><td>高(为无人值守设计)</td></tr>
<tr><td>跨会话学习</td><td><b>save_lesson+冻结快照</b></td><td>零(外包给用户)</td><td>全自动(fork+curator)</td></tr>
<tr><td>可审计</td><td><b>JSONL 全量可查</b></td><td>wire.jsonl 事件溯源</td><td>SQLite+FTS5 全文检索</td></tr>
</table>
<p><b>什么时候选谁</b>:miniagent 教学与二次开发基座,每个模块一眼看完;能力缺口(流式、swarm 调度、反抖动、MCP)是有意留白。kimi-code 型有人盯着的编程 CLI,延迟与确定性优先。Hermes 型无人值守多表面平台,安全边界与状态可恢复优先,代价是数倍代码量。</p>''')

    # ============ 5 问题与解决 ============
    P.append(chapter(5, "问题与解决", "两类:结构性问题(对照教程原型事故,证明设计免疫或已修复)+ 实测问题(时间序修复清单)。"))
    P.append(sub("5.1 问题一:多子代理上下文压缩污染 —— 不存在,且从设计上免疫"))
    P.append("<p>教程原型事故是 Hermes #38727:父 agent 与后台 fork 共享同一 session,两边同时触发压缩 → 历史分叉。miniagent 的 delegate_task 派生<b>全新 Agent 实例</b>(独立 messages / 独立 ToolRuntime / 独立 HookManager / 独立 transcript / 独立 30 步预算 / 独立 stop 闩锁),父压缩物理上碰不到子上下文;只回传 distill 报告(10K 截断);system prompt 同前缀暖缓存。现场验证 T7:父 transcript 只有 delegate_task→write_file→bash×2,子代理 11 次探索调用记录在自己独立 transcript 里,主线零污染。</p>")
    P.append(sub("5.2 问题二:多会话记忆污染 —— 一种天然免疫,两种已修复"))
    P.append("<p><b>形态 A(摘要劫持):天然免疫</b> —— 记忆快照在 messages[0](system),head 保护永不进中段;摘要带 [REFERENCE ONLY] 免疫包裹。<b>形态 B(并发写截断竞态):已修</b> —— 追加写带 UTC provenance(行级原子);截断改 tmp+rename 原子替换。<b>形态 C(毒条目带毒注入):已修</b> —— 快照加载与 memory_search 逐行注入安检,命中条目替换占位符;单测确认毒条目被过滤、正常条目不受影响。</p>")
    P.append(why("为什么不学 kimi 不要记忆:kimi 把跨会话学习整体外包 —— 零污染面但也零自学习。miniagent 保留轻量自产记忆,代价是支付 B/C 两项防御。"))
    P.append(sub("5.3 实测问题与修复清单(时间序)"))
    P.append('''<table>
<tr><th>#</th><th style="width:20%">问题</th><th style="width:24%">根因</th><th style="width:26%">修复</th><th>验证</th></tr>
<tr><td>1</td><td>一次性任务结束打印崩溃</td><td>Windows GBK,输出含 emoji</td><td>cli.py 启动 reconfigure utf-8</td><td>冒烟 exit 0</td></tr>
<tr><td>2</td><td>进程外 hook 读 payload 失败</td><td>子进程 stdin 默认 GBK</td><td>buffer+utf-8;注入 PYTHONIOENCODING</td><td>T4b 实测</td></tr>
<tr><td>3</td><td><b>单 user 会话永不压缩</b></td><td>守护把 cut 拉回 1→middle 恒空</td><td>守护仅 last_user_idx≥2 生效+回归测试</td><td>t6d 触发 2 次</td></tr>
<tr><td>4</td><td>记忆并发写竞态/带毒注入</td><td>见形态 B/C</td><td>provenance+tmp+rename+安检</td><td>TestMemory ×3</td></tr>
<tr><td>5</td><td>无子代理机制(能力缺口)</td><td>最小设计留白</td><td>delegate_task 物理隔离派生</td><td>TestSubagent+T7</td></tr>
<tr><td>6</td><td><b>跨进程 resume 丢失压缩摘要</b>(压测问题 A)</td><td>compact 事件不落摘要文本;每轮独立进程全量重灌</td><td>compact/overflow 事件携带完整 messages 快照;重放遇快照即切换</td><td>57/57 回归含快照重放用例</td></tr>
<tr><td>7</td><td>会话工具/hook 全局串绑</td><td>模块级单例注册表</td><td>ToolRuntime/HookManager 按 Agent 实例化</td><td>隔离回归测试</td></tr>
<tr><td>8</td><td>并发会话文件名同秒碰撞</td><td>时间戳命名</td><td>open(x) 独占创建原子占位</td><td>并发回归</td></tr>
<tr><td>9</td><td>web 超时后并发闸失效</td><td>超时即释放闸 → 超时任务与新任务重叠</td><td>闸保持占用到线程真实结束</td><td>web 回归</td></tr>
<tr><td>10</td><td>sandbox 只读名单与注册表漂移</td><td>两份名单各自维护</td><td>known_tools 由 ToolRuntime 生成(单一事实源)</td><td>注册回归</td></tr>
<tr><td>11</td><td><b>token 漂移:chars/4 中文低估 ~2x</b>,压缩触发偏晚靠 413 自愈兜底</td><td>估算无真实反馈</td><td>DriftCalibrator:每次真实 usage 锚点 EMA 校准,驱动 85% 阈值与 tail 预算</td><td>TestDriftCalibrator ×5 + 接线测试</td></tr>
<tr><td>12</td><td><b>resume 重放孤儿 tool 消息 → 下一条 chat 400</b></td><td>崩溃截断致协议对残缺</td><td>_repair_tool_pairs():孤儿丢弃/缺 result 补占位</td><td>TestResumeProtocolRepair ×2</td></tr>
</table>''')
    P.append(sub("5.4 已知边界(有意不修,对应演化阶梯)"))
    P.append(note("极小窗口压缩 thrash(第 6 级反抖动三件套) · LLM 非流式(第 1 级) · 无并发子代理调度 swarm(第 5 级) · 无 MCP 外部工具桥接(第 8 级) · 无 LLM 兜底裁决 Smart Approval(第 10 级) · bash 不是 OS 级沙盒(无人值守应套容器/E2B) · 同一 workdir 父/子代理有意共享项目文件与 MEMORY.md(隔离的是上下文与运行时绑定)。"))

    # ============ 6 工程问答 ============
    P.append(chapter(6, "工程问答(16 题)", "题目来自 DeepSeek Agent 岗三面连环追问。标注:〔已有机制〕现场验证过 · 〔针对性补全〕本轮新增 · 〔参照〕kimi/Hermes 对照。"))
    P.append(sub("6.1 一面 · 工程细节题"))
    P.append("<p><b>Q1 上下文用 message window 还是 token window?</b>〔已有机制〕<b>token window</b>。context.py 以估算 token 数(chars/4)对 30 万窗口设 85% 触发线;message window 无法表达「10 条消息里有一条 240KB 工具输出」的真实分布(实测单条 read_file 结果 25 万字符)。代价是估算漂移,工业解法是 kimi 双层计量;miniagent 停在单层粗估+85% 保守阈值+溢出自愈兜底。{kimi: 双层计量 · Hermes: 三套信号协调}</p>")
    P.append("<p><b>Q2 会话持久化过期策略?并发会话冲突?</b>〔针对性补全〕存储选型 <b>JSONL 而非 Redis</b>(只要恢复→追加日志够用,要检索才上库)。过期:cleanup_old_sessions(默认 30 天)按 mtime TTL。并发冲突:多会话同 workdir 写 MEMORY.md → 行级原子追加+tmp+rename;多子代理共享上下文压缩 → 物理隔离(独立 transcript);同秒新建会话 → 独占创建防碰撞。{kimi: AppendLogStore cutover · Hermes: SQLite 压缩锁 TTL 300s}</p>")
    P.append("<p><b>Q3 长期记忆用向量库吗?检索越来越不准怎么办?</b>〔针对性补全〕<b>不用向量库</b> —— 记忆是 8K 字符硬上限的平文件(容量即精度:上限强制淘汰旧条目,检索域永远小到关键词足够准)。memory_search 只读检索。防线在写入与加载双侧:provenance 溯源+注入安检,毒条目不进检索域。记忆条目破千、跨项目复用时才上向量库。{Hermes: FTS5+trigram}</p>")
    P.append("<p><b>Q4 上下文溢出兜底?</b>〔针对性补全〕三层:① 预防 —— preflight 超 85% 即压缩;② 自愈 —— provider 报 context/overflow/length 错误时 _chat() 捕获,force=True 强制压缩后重试,连续 3 次放弃(且溢出事件本身落快照);③ 兜死 —— 摘要失败 fail-open 保原会话。{kimi: 认领 413,窗口 ×0.85}</p>")
    P.append("<p><b>Q5 单用户日均 token 成本?百万级怎么控制?</b>〔针对性补全〕用量账本(prompt/completion/calls 累加,turn 结束落 transcript)。现场实测:轻任务 = 5,838 prompt + 189 completion / 4 次调用;完整项目任务约 14 次工具调用、~10 次 LLM 调用。三板斧:① 缓存宪法(前缀只追加);② 结果治理(50K 落盘只回 2K);③ 预算硬墙。{kimi: 分段缓存 · Hermes: 4 断点+冻结快照}</p>")
    P.append("<p><b>Q6 恶意刷长文本怎么限制?</b>〔针对性补全〕三层:入口 MAX_INPUT_CHARS(默认 20 万)超限直接拒,<b>零 LLM 消耗</b>;工具侧 bash 120s/30K 截断/50K 落盘;循环侧 max_steps 硬墙+stop 闩锁。Web 形态另有请求体长度护栏。</p>")
    P.append("<p><b>Q7 为什么基座不微调?拿什么数据判断?</b>〔设计决策〕行为约束都在工程层(system prompt 纪律+工具协议+权限链),不需要权重级定制。判断数据:工具调用成功率(73 次 0 协议错误)、任务完成率、失败自愈率、单任务成本(账本)。微调唯一值回票价的是把 BASE_PROMPT 烧进权重省 token —— 但损失迭代速度,不划算。</p>")
    P.append("<p><b>Q8 讲一个线上故障排查。</b>〔真实案例〕<b>单 user 会话压缩失效</b>:小窗口压测(MAX_CONTEXT=1500)下压缩恒 0。逐步重放 transcript 计算各时点估算,确认第 3 条消息起已超阈值却不触发 → 定位到「最后一条 user 必须在 tail」守护把 cut 强制拉回 1,middle 恒空。修复:守护仅 last_user_idx≥2 生效。效果:压缩触发 0→2 次;回归测试防复发。教训:守护规则必须考虑「被保护对象已在保护区」的边界。</p>")
    P.append(sub("6.2 二面 · 系统设计题"))
    P.append("<p><b>Q9 模块怎么拆分?通信?</b>〔已有机制〕13 个模块按「窄腰核心+边上插拔」拆:loop 是唯一有状态核心,三个窄接口通信 —— 工具协议(注册表快照)、事件表(hooks 5 事件)、消息列表(会话状态,正常只追加)。不走消息总线是为了缓存宪法:总线式动态注入会打碎前缀缓存。</p>")
    P.append("<p><b>Q10 简单任务 vs 多步拆解怎么判断?</b>〔已有机制〕拆解权交给模型,工程层只设边界 —— max_steps 硬墙(60)、子代理独立预算(30)、delegate_task 让模型把探索性子任务显式派生。两种工业路线(kimi 拆解权给模型 / Hermes 预算 refund)都验证了「不要在工程层替模型做拆解判断」。</p>")
    P.append("<p><b>Q11 执行一半失败:重试/回滚/重新规划?</b>〔已有机制〕分四层,触发条件显式:</p>")
    P.append('''<table>
<tr><th style="width:18%">失败类型</th><th style="width:48%">策略</th><th>触发条件</th></tr>
<tr><td>工具执行失败</td><td>错误文本回填,模型自行重试或换路(T1 实测)</td><td>任何 tool exception</td></tr>
<tr><td>429/5xx/超时</td><td>指数退避(×2 上限 30s+20% 抖动),最多 5 次</td><td>HTTP 状态码/连接异常</td></tr>
<tr><td>上下文溢出</td><td>强制压缩后重试,连续 3 次放弃(落溢出快照)</td><td>错误含 context/overflow/length</td></tr>
<tr><td>权限拒绝/hook 阻断</td><td><b>不重试不绕过</b>,原因回填换方案(T4b 实测)</td><td>sandbox/hook veto</td></tr>
</table>
<p>回滚在最小设计里刻意没有(文件操作无事务),对应 kimi 的 undo/wire Op 重放 —— 痛了再加。</p>''')
    P.append("<p><b>Q12 多工具联动?权限管控?防越权?</b>〔已有机制〕联动:纯注册表快照,顺序由模型按 schema 编排;结果治理保证单工具不灌爆窗口。权限五道防线:① hardline 硬线(yolo 也不放行);② 去混淆防绕过;③ 未知工具 fail-closed;④ 三分级+ask/auto/yolo;⑤ workdir 围栏+环境剥离。价值观:<b>危险检测先于用户授权</b>。{Hermes: hardline 先于 yolo bypass}</p>")
    P.append(sub("6.3 三面 · 认知题"))
    P.append("<p><b>Q13 Agent 长期风口还是短期热点?</b> 长期。模型每代跃迁,但三个工业 codebase 的厚度证明<b>工程表现的上下限由 Harness 决定</b> —— 同一模型接不同 Harness,安全性/成本/长任务存活率差一个数量级。</p>")
    P.append("<p><b>Q14 核心竞争力?</b> 能从「事故」反推架构:每个模块都能回答「防什么事故、对应演化阶梯第几级、kimi/Hermes 怎么解」。demo 开发者堆框架,工程师管爆炸半径、管成本、管最坏情况下限。</p>")
    P.append("<p><b>Q15 1–2 年最大瓶颈?ToB 还是 ToC?</b> 工程能力。模型已「够用」,卡脖子的是长会话成本、无人值守安全、状态可恢复。ToB 先跑通 —— 容错预算高、边界清晰、权限可预声明;ToC 越权风险面不可控。</p>")
    P.append("<p><b>Q16 从 0–1 带 Agent 业务线,第一步?</b> 先定形态再写代码:有人值守还是无人值守?这决定主循环形状、安全厚度、存储选型。招人按模块招,评审标准就是「每份复杂性答得出防什么事故」。</p>")

    # ============ 7 压测 ============
    P.append(chapter(7, "压力测试与问题发现(2026-08-16 实测 + 修复对照)", "三组实测:A 组 3 个编译类任务、B 组 5 个复杂编程任务、C 组 5 用户×20 轮并发多轮对话(强制小窗口压 context/memory 压缩)。全部现场真跑,发现 6 项问题;其中问题 A(resume 丢失压缩摘要)已在 690eabf 修复,其余按优先级保留。"))
    P.append(sub("7.1 实测任务与结果总览"))
    P.append('''<table>
<tr><th>#</th><th style="width:36%">任务</th><th style="width:10%">结果</th><th>说明</th></tr>
<tr><td>C1</td><td>C 词频统计程序(检测 gcc/tcc/cl 并编译)</td><td>降级完成</td><td>本机无 C 编译器→诚实报告,Python 等价实现验证 the=3</td></tr>
<tr><td>C2</td><td>LaTeX 中文短文 report.tex,xelatex 编译</td><td>通过</td><td>两轮编译(第二轮解决交叉引用),PDF 1 页 41KB,0 error</td></tr>
<tr><td>C3</td><td>Python 包 mylib(setup.py)+pip editable 安装+断言</td><td>通过</td><td>fib(10)==55 / is_prime(97) / sort 全过</td></tr>
<tr><td>P1</td><td>JSON 解析器(纯 Python,25 测试)</td><td>通过</td><td>独立复跑 29 tests OK(含 \\uXXXX 代理对/前导零拒绝)</td></tr>
<tr><td>P2</td><td>Markdown→HTML 渲染器(20 测试)</td><td>通过</td><td>标题/嵌套列表/围栏代码块/行内格式全覆盖</td></tr>
<tr><td>P3</td><td>线程安全 LRU+TTL 缓存装饰器(15 测试)</td><td>通过</td><td>10 线程×100 次并发读写正确</td></tr>
<tr><td>P4</td><td>表达式求值器(递归下降,18 测试)</td><td>通过</td><td>变量赋值/一元负号/比较/除零与未知变量错误</td></tr>
<tr><td>P5</td><td>优先级队列+SQLite 持久化(15 测试)</td><td>通过</td><td>崩溃恢复顺序不变;重试 3 次入死信;backoff 生效</td></tr>
<tr><td>X1</td><td>5 用户×20 轮并发,MAX_CONTEXT=12000 强制压缩</td><td><b>100/100 轮 exit 0</b></td><td>总墙钟 99s;暴露 4 项真实问题(下)</td></tr>
</table>''')
    P.append(sub("7.2 问题 A(已修复):跨进程 resume 丢失压缩摘要"))
    P.append("<p><b>现象</b>:压测 transcript 显示 u1 的 6 次 compact 事件全部集中在第 17–20 轮,且每次压缩时点估算只有 ~2,950 tokens —— 远低于 85% 阈值 10,200。<b>根因</b>:compact 事件只落 {\"type\":\"compact\",\"tokens\":...},摘要文本不落盘;压测每轮独立进程(--resume 续),每个新进程都把全量历史重新灌入活上下文 —— 前一轮压缩成果作废,要么重付全量 prompt,要么重新调一次摘要。<b>代价</b>:5 用户合计多付约 30 次多余摘要调用。<b>修复(690eabf)</b>:compact/overflow_heal 事件携带压缩后完整 messages 快照;reconstruct_messages() 遇快照直接采用、跳过其前历史。resume 回到压缩后的真实上下文。</p>")
    P.append(sub("7.3 问题 B(随 A 缓解):长会话成本爬升未压平"))
    P.append("<p>20 轮 prompt 合计 99,880 tokens(轮均 4,994,峰值 11,497 ≈ 整窗);5 用户×100 轮合计 501,841 tokens。根因同问题 A(resume 全量重放)。修 A 之后预期轮均降至 ~3K 并走平;若仍不达标,演化级是 kimi 的「锚点实测+估算」双层计量(把 20% 保守余量收窄)。</p>")
    P.append(sub("7.4 问题 C(设计权衡):压缩摘要粒度粗,早轮细节丢失"))
    P.append("<p>第 20 轮回顾题的答案只保留主题级信息,第 1–4 轮的具体返回码值(0x0011/0x0022/…)丢失。单次无结构摘要长 middle 一次压完必然有损。可选改进:摘要提示词按轮次/主题分段保留关键数值;kimi 路线是锚点+分段摘要。注意这是设计权衡而非纯缺陷 —— 记忆系统本就是为跨压缩保留关键事实而设,压测中 5 用户各 4 条 save_lesson 全部带 UTC provenance 正确落盘。</p>")
    P.append(sub("7.5 问题 D(已知边界):小窗口下 turn 内压缩抖动"))
    P.append("<p>MAX_CONTEXT=12000 时,第 5/10 轮的多步工具调用在阈值边缘反复触发:prompt 序列 6,985→3,957(压)→4,385→4,813→…→11,497→3,328(又压)—— 单 turn 内两次压缩、两次摘要调用。这是教程 Ch.2 第 6 级「反抖动三件套」(-1 哨兵/无效计数/600s 冷却)的缺席,属已知边界,本次实测量化了代价:第 10 轮多花约 8K tokens。生产窗口 30 万下抖动概率低,优先级低于问题 A。</p>")
    P.append(sub("7.6 问题 E(边界,行为正确):无 C 编译器时诚实降级"))
    P.append("<p>C1 任务本机无 gcc/tcc/cl,agent 明确声明「未执行任何编译操作」,交付可编译源码+Python 等价实现完成功能验证 —— 没有假装编译。这是反假阳价值观的正面案例,记录为部署边界:需要 C 工具链的任务请自带环境。</p>")
    P.append(sub("7.7 问题 F(口径问题):测试文件位置约定"))
    P.append("<p>P4 把测试写在 tests/ 子目录,根目录 python -m unittest discover 报 NO TESTS,需 discover -s tests 才能跑(测试本身 18/18 全过)。agent 自报口径与独立验证口径不一致。改进:BASE_PROMPT 约定测试文件写在根目录 test_*.py,或任务描述显式指明。</p>")
    P.append(sub("7.8 压测方法(可复现)"))
    P.append('''<pre># _stress/concurrency_test.py: 5 进程 = 5 用户,独立 workdir/transcript
# 每轮注入 ~2.7K 字符背景材料,MAX_CONTEXT=12000 强制压缩
# 每 5 轮一个回顾+save_lesson 任务轮;每轮 --resume 续会话
# 统计:每轮 exit/耗时/usage + compact 事件 + MEMORY.md 终态
# 结果:conc/summary.json + u*.log;墙钟 99s,100/100 exit 0</pre>''')
    P.append('<div class="complexity" style="margin-top:14px">— 报告完 — 生成:build_miniagent_report.py(XeLaTeX 版已由本 HTML+Chrome 管线取代);素材:《Agent 模块化设计教程 v2》· kimi-code v0.34 · hermes-agent 0.18.0 · miniagent commit 690eabf</div>')

    html = ("<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"UTF-8\">"
            "<title>miniagent 完整报告</title>" + CSS + "</head><body>"
            + "".join(P) + "</body></html>")
    out = __file__.rsplit("\\", 1)[0] + "\\" + "miniagent_report_full.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("written:", out, "chars:", len(html))

if __name__ == "__main__":
    build()
