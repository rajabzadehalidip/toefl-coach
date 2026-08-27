"""Spaced-repetition drills generated from the learner's own error ledger."""

from __future__ import annotations

import json
from typing import Dict, List

from . import db, prompts
from .llm import chat_json


def build_session(api_key: str, model: str, size: int = 6) -> List[Dict]:
    """Turn the learner's due errors into fresh drill items."""
    due = db.due_errors(limit=max(size * 2, 12))
    if not due:
        return []

    chosen = due[:size]
    payload = [
        {
            "id": e["id"],
            "category": e["category"],
            "original": e["original"],
            "correction": e["correction"],
            "rule": e["rule"],
        }
        for e in chosen
    ]

    result = chat_json(
        [
            {"role": "system", "content": prompts.DRILL_SYSTEM},
            {"role": "user", "content": (
                f"Learner errors (JSON):\n{json.dumps(payload, indent=2)}\n\n"
                f"Generate exactly {len(payload)} items — one per error, using each error's id."
            )},
        ],
        api_key,
        model,
        temperature=0.7,
    )

    valid_ids = {p["id"] for p in payload}
    items = [
        i for i in result.get("items", [])
        if isinstance(i, dict) and i.get("error_id") in valid_ids
    ]

    # Normalize MCQs: valid options/answer index, and never leave the correct
    # answer as the first option (selectboxes pre-select index 0).
    for pos, item in enumerate(items):
        if item.get("type") == "mcq":
            options = item.get("options") or []
            if len(options) < 2:
                item["options"] = ["(malformed item)"]
                item["answer_index"] = 0
                continue
            try:
                answer_index = int(item.get("answer_index", 0))
            except (TypeError, ValueError):
                answer_index = 0
            if not 0 <= answer_index < len(options):
                answer_index = len(options) - 1
            if answer_index == 0:
                swap = (pos % (len(options) - 1)) + 1
                options[0], options[swap] = options[swap], options[0]
                answer_index = swap
            item["options"] = options[:4]
            item["answer_index"] = min(answer_index, len(item["options"]) - 1)
    return items


def check_fix(api_key: str, model: str, item: Dict, user_answer: str) -> Dict:
    """LLM-check a free-text rewrite (lenient on style, strict on the target rule)."""
    return chat_json(
        [
            {"role": "system", "content": prompts.CHECK_FIX_SYSTEM.format(
                sentence=item.get("sentence", ""),
                answer=item.get("answer", ""),
                rule=item.get("rule", ""),
                user=user_answer,
            )},
            {"role": "user", "content": "Check the rewrite."},
        ],
        api_key,
        model,
        temperature=0.1,
        max_tokens=300,
    )


def record_result(item: Dict, passed: bool, kind: str) -> None:
    """Update SRS scheduling and log the attempt."""
    db.update_error_srs(item["error_id"], passed)
    db.log_drill(item["error_id"], passed, kind)
