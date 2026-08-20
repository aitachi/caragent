"""OpenAI 兼容 LLM 客户端（教程 Ch.1 附属：结构化重试）。

环境变量：
  MINIAGENT_API_KEY   必填
  MINIAGENT_BASE_URL  默认 https://dashscope.aliyuncs.com/compatible-mode/v1
  MINIAGENT_MODEL     默认 qwen3.7-max
"""
from __future__ import annotations

import json
import os
import random
import time

import requests

DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.7-max"
TIMEOUT = 300
MAX_RETRIES = 5


class LLMError(Exception):
    pass


class LLM:
    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None):
        self.api_key = api_key or os.environ.get("MINIAGENT_API_KEY")
        self.base_url = (base_url or os.environ.get("MINIAGENT_BASE_URL")
                         or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.environ.get("MINIAGENT_MODEL") or DEFAULT_MODEL
        self._session = requests.Session()

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """返回规范化 dict：{content, tool_calls[{id,name,arguments}], finish_reason, usage}。"""
        if not self.api_key:
            raise LLMError("MINIAGENT_API_KEY 未设置")
        body: dict = {
            "model": self.model,
            "messages": messages,
            "enable_thinking": False,
        }
        if tools:
            body["tools"] = tools
        url = self.base_url + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        delay = 1.0
        last_err: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = self._session.post(url, json=body, headers=headers,
                                          timeout=TIMEOUT)
            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError) as e:
                last_err = e
                time.sleep(delay + random.uniform(0, delay * 0.2))
                delay = min(delay * 2, 30)
                continue

            if resp.status_code == 429 or resp.status_code >= 500:
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait = float(retry_after)
                    except ValueError:
                        wait = delay
                else:
                    wait = delay
                time.sleep(wait + random.uniform(0, wait * 0.2))
                delay = min(delay * 2, 30)
                last_err = LLMError(f"HTTP {resp.status_code}: {resp.text[:500]}")
                continue

            if resp.status_code >= 400:
                raise LLMError(f"HTTP {resp.status_code}: {resp.text[:1000]}")

            try:
                data = resp.json()
            except ValueError as e:
                raise LLMError(f"响应不是合法 JSON: {e}") from e
            return self._normalize(data)

        raise LLMError(f"重试 {MAX_RETRIES} 次仍失败: {last_err}")

    @staticmethod
    def _normalize(data: dict) -> dict:
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        tool_calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            entry = {
                "id": tc.get("id", ""),
                "name": fn.get("name", ""),
            }
            raw_args = fn.get("arguments", "")
            try:
                entry["arguments"] = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except (json.JSONDecodeError, TypeError):
                entry["arguments"] = {}
                entry["error"] = f"arguments JSON 解析失败: {str(raw_args)[:200]}"
            tool_calls.append(entry)
        return {
            "content": msg.get("content") or "",
            "tool_calls": tool_calls,
            "finish_reason": choice.get("finish_reason", ""),
            "usage": data.get("usage") or {},
        }
