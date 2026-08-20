"""合并 report/ 子页面为单个完整报告 815agent_report_full.html。

从各子页面提取 <div class="wrap"> 内的正文（去掉自身 nav），
合并到带锚点导航的单文件。运行：python report/build_full.py
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PAGES = [
    ("index.html", "概览", "overview"),
    ("modules.html", "模块设计", "modules"),
    ("run.html", "如何运行", "run"),
    ("compare.html", "对比报告", "compare"),
    ("problems.html", "问题与解决", "problems"),
    ("interview.html", "工程问答", "interview"),
]

CSS = """
:root{--bg:#f6f8fa;--panel:#ffffff;--line:#d8e0e8;--fg:#1f2a37;--dim:#5a6672;--acc:#0b62a2;--ok:#1b7f4b;--warn:#b25e09;--bad:#c0392b;--codebg:#eef2f6;--codefg:#0b62a2;--prefg:#1f2a37;--thbg:#dbe5ef;--thfg:#1f2a37}
html.dark{--bg:#0f1419;--panel:#1a222b;--line:#2b3744;--fg:#d7e0e8;--dim:#8b9aab;--acc:#4fb3ff;--ok:#3fd68f;--warn:#ffb454;--bad:#ff6b6b;--codebg:#0a0e12;--codefg:#9fd3ff;--prefg:#c9d6e2;--thbg:#22303d;--thfg:#fff}
html.dark h1,html.dark h3{color:#fff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.75 "Microsoft YaHei",system-ui,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:32px 24px 64px}
h1{font-size:30px;margin:0 0 4px;color:#1a2430}h2{font-size:21px;color:var(--acc);border-left:4px solid var(--acc);padding-left:10px;margin-top:38px}
h3{font-size:16.5px;color:#1a2430;margin:22px 0 8px}
.sub{color:var(--dim);margin-bottom:24px}
#themeToggle{position:fixed;top:14px;right:16px;z-index:99;background:var(--panel);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:5px 12px;font-size:13px;cursor:pointer}
nav.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:22px 0 30px;position:sticky;top:0;background:var(--bg);padding:10px 0;z-index:9;border-bottom:1px solid var(--line)}
nav.tabs a{color:var(--fg);text-decoration:none;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 16px;font-size:14px}
nav.tabs a:hover{border-color:var(--acc);color:var(--acc)}
nav.tabs a.here{background:var(--acc);color:#fff;font-weight:700;border-color:var(--acc)}
.card,.mod{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 22px;margin:14px 0}
.mod h3{margin:0 0 8px}.mod .meta{color:var(--dim);font-size:13px;margin-bottom:8px}
table{width:100%;border-collapse:collapse;margin:14px 0;font-size:13.5px}
th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
th{background:var(--thbg);color:var(--thfg)}
td.a815{background:rgba(79,179,255,.07)}
code{background:var(--codebg);border:1px solid var(--line);border-radius:6px;padding:1px 6px;font-family:Consolas,monospace;font-size:13px;color:var(--codefg)}
pre,.flow{background:var(--codebg);border:1px solid var(--line);border-radius:8px;padding:14px;overflow-x:auto;font-family:Consolas,monospace;font-size:13px;color:var(--prefg);line-height:1.6;white-space:pre}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}.dim{color:var(--dim)}.fix{color:var(--ok)}.bug{color:var(--bad)}
.tag{display:inline-block;background:var(--thbg);border:1px solid var(--line);border-radius:20px;padding:1px 10px;font-size:12px;color:var(--acc);margin:2px 4px 2px 0}
.lv{display:inline-block;border-radius:6px;padding:0 8px;font-size:12px;font-weight:700;margin-left:8px;vertical-align:2px}
.lv0{background:rgba(90,102,114,.12);border:1px solid var(--dim);color:var(--dim)}
.lv1{background:rgba(11,98,162,.08);border:1px solid var(--acc);color:var(--acc)}
.lv2{background:rgba(27,127,75,.08);border:1px solid var(--ok);color:var(--ok)}
.lv3{background:rgba(178,94,9,.08);border:1px solid var(--warn);color:var(--warn)}
.legend{font-size:13px;color:var(--dim);margin:6px 0 18px}
.kg{background:var(--codebg);border:1px solid var(--line);border-radius:10px;padding:10px;margin:16px 0;overflow-x:auto}
.kg svg{display:block;margin:0 auto;max-width:100%;height:auto}
.kg .cap{color:var(--dim);font-size:13px;text-align:center;margin-top:6px}
.note{border-left:4px solid var(--warn);background:rgba(255,180,84,.08);padding:10px 16px;border-radius:0 8px 8px 0;margin:14px 0}
.verdict{font-size:17px;font-weight:700;padding:12px 18px;border-radius:8px;margin:12px 0}
.verdict.no{background:rgba(61,214,143,.1);border:1px solid var(--ok);color:var(--ok)}
.verdict.risk{background:rgba(255,180,84,.1);border:1px solid var(--warn);color:var(--warn)}
section{border-top:2px solid var(--line);margin-top:48px;padding-top:8px}
section:first-of-type{border-top:none;margin-top:0}
"""


def extract(fname: str) -> str:
    """提取子页面 wrap 内的正文：去 h1/.sub/nav，保留其余。"""
    html = open(os.path.join(HERE, fname), encoding="utf-8").read()
    m = re.search(r'<div class="wrap">(.*)</div>\s*</body>', html, re.S)
    body = m.group(1)
    body = re.sub(r"<h1>.*?</h1>", "", body, flags=re.S)
    body = re.sub(r'<div class="sub">.*?</div>', "", body, flags=re.S)
    body = re.sub(r'<nav class="tabs">.*?</nav>', "", body, flags=re.S)
    return body.strip()


def main():
    sections = []
    for fname, title, anchor in PAGES:
        sections.append(
            f'<section id="{anchor}"><h2 style="font-size:26px">{title}</h2>'
            + extract(fname) + "</section>")
    nav = "".join(f'<a href="#{a}">{t}</a>' for _, t, a in PAGES)
    out = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>815agent 完整报告 — 模块·设计·运行·对比·问题</title>
<style>{CSS}</style>
</head>
<body>
<button id="themeToggle" onclick="var d=document.documentElement.classList.toggle('dark');localStorage.setItem('theme815',d?'dark':'light');this.textContent=d?'🌙 深色':'☀ 亮色'">☀ 亮色</button>
<script>if(localStorage.getItem('theme815')==='dark'){{document.documentElement.classList.add('dark');document.getElementById('themeToggle').textContent='🌙 深色'}}</script>
<div class="wrap">
<h1>815agent 完整报告</h1>
<div class="sub">最小完备 Coding Agent · 模块设计 / 如何运行 / 与 kimi-code & Hermes 对比 / 污染分析与问题修复 · 2026-08-15</div>
<nav class="tabs">{nav}</nav>
{''.join(sections)}
</div></body></html>
"""
    path = os.path.join(HERE, "815agent_report_full.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"merged -> {path} ({len(out)} bytes)")


if __name__ == "__main__":
    main()
