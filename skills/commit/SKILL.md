---
name: commit
description: 规范 git commit 流程：先审 diff 再写规范提交信息
---

# Git Commit 规范流程

## 步骤

1. `git status` 确认改动范围，别把无关文件混进来。
2. `git diff --staged`（或先 `git add` 再看）逐条审 diff，确认没有调试代码、
   临时文件、密钥等不该提交的内容。
3. 写提交信息，格式：`<type>: <一句话摘要>`，type 取
   feat / fix / refactor / test / docs / chore 之一。
4. 摘要用祈使句、不超过 72 字符；必要时正文补充动机与影响。
5. `git commit` 后用 `git log -1 --stat` 验证提交内容符合预期。

## 红线

- 绝不提交 `.env`、密钥文件、node_modules、构建产物。
- 绝不 `git push --force` 到共享分支，除非用户明确要求。
- 用户没让 commit 时不要擅自 commit。
