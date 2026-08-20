---
name: py-test
description: 写 pytest 测试的流程与常见坑
---

# pytest 测试编写流程

## 流程

1. 先读被测代码的公开接口，确定要覆盖的行为（正常路径 + 边界 + 错误路径）。
2. 测试文件命名 `test_<模块>.py`，放在 `tests/` 目录。
3. 每个测试只断言一件事；用 `tmp_path` fixture 隔离文件系统副作用。
4. 跑 `python -m pytest tests/ -x -q` 验证；红了先读 traceback 再改。
5. 外部依赖（网络、时钟、随机数）一律 mock 或注入，测试必须离线可重复。

## 常见坑

- 别在测试里 `time.sleep` 等异步结果，用轮询+超时或直接注入同步实现。
- 浮点数比较用 `pytest.approx`，不要 `==`。
- 修改全局状态（环境变量、单例）的测试要用 `monkeypatch` 自动还原。
- 断言异常用 `pytest.raises`，并匹配 message 避免误捕。
