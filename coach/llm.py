"""Minimal OpenRouter (OpenAI-compatible) chat client.

One function for plain chat, one that forces valid JSON with retries —
the error ledger only stays clean if grading output is reliably parseable.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMError(RuntimeError):
    """Raised for any API or parsing failure, with a readable message."""


def chat(
    messages: List[Dict],
    api_key: str,
    model: str,
    temperature: float = 0.4,
    max_tokens: int = 4000,
    json_mode: bool = False,
    timeout: int = 180,
) -> str:
    if not api_key:
        raise LLMError("Missing OpenRouter API key — add it in the sidebar or set OPENROUTER_API_KEY.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8501",
        "X-Title": "TOEFL Writing Coach",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    resp = requests.post(API_URL, headers=headers, json=payload, timeout=timeout)

    # Some models don't support response_format — retry once without it.
    if resp.status_code == 400 and json_mode and "response_format" in resp.text:
        payload.pop("response_format", None)
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=timeout)

    if resp.status_code != 200:
        raise LLMError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:300]}")

    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Unexpected OpenRouter response: {resp.text[:300]}") from exc
    if not content:
        raise LLMError("Empty model response.")
    return content


def extract_json(text: str) -> Dict:
    """Pull the first JSON object out of a possibly fenced / chatty response."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found in response")
    return json.loads(text[start : end + 1])


def chat_json(
    messages: List[Dict],
    api_key: str,
    model: str,
    temperature: float = 0.3,
    max_tokens: int = 4000,
    retries: int = 2,
) -> Dict:
    """Chat that must return a JSON object; repairs and retries on parse failure."""
    msgs = list(messages)
    last_err: Exception = ValueError("no attempt made")
    for _ in range(retries + 1):
        raw = chat(msgs, api_key, model, temperature=temperature,
                   max_tokens=max_tokens, json_mode=True)
        try:
            return extract_json(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            last_err = exc
            msgs = msgs + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": (
                    "That was not valid JSON. Respond again with ONLY a valid JSON "
                    "object — no markdown fences, no commentary."
                )},
            ]
    raise LLMError(f"Model failed to return valid JSON after {retries + 1} attempts: {last_err}")
