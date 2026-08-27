"""Grading pipeline: rubric scoring, structured error extraction, and the
profile-consolidation step that keeps long-term memory fresh.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Dict

from . import db, prompts, rubric
from .llm import LLMError, chat, chat_json


def grade_essay(api_key: str, model: str, task_type: str,
                prompt_body: str, essay_text: str) -> Dict:
    """Grade one essay; returns the validated grader JSON."""
    messages = [
        {"role": "system", "content": prompts.GRADE_SYSTEM},
        {"role": "user", "content": prompts.GRADE_USER.format(
            task_type=task_type,
            rubric=rubric.rubric_text(task_type),
            prompt=prompt_body,
            essay=essay_text,
            word_count=len(essay_text.split()),
        )},
    ]
    result = chat_json(messages, api_key, model, temperature=0.2)
    _validate(result)
    return result


def _validate(result: Dict) -> None:
    """Defensive normalization so a sloppy model can't corrupt the UI/ledger."""
    scores = result.setdefault("scores", {})
    for key in ("development", "organization", "language", "overall"):
        try:
            scores[key] = max(0.0, min(5.0, float(scores.get(key, 0))))
        except (TypeError, ValueError):
            scores[key] = 0.0
    result.setdefault("summary", "")
    for key in ("strengths", "priority_fixes", "errors", "overused_words", "nice_phrases"):
        if not isinstance(result.get(key), list):
            result[key] = []
    if not isinstance(result["errors"], list):
        result["errors"] = []


def model_answer(api_key: str, model: str, task_type: str, prompt_body: str) -> str:
    """A 5/5-level response to the same prompt, for comparison."""
    messages = [
        {"role": "system", "content": prompts.MODEL_ANSWER_SYSTEM},
        {"role": "user", "content": f"Task type: {task_type}\n\nTASK PROMPT:\n{prompt_body}"},
    ]
    return chat(messages, api_key, model, temperature=0.6)


def update_profile(api_key: str, model: str) -> str:
    """Consolidate DB stats + old profile into a fresh profile markdown.

    This is the tutor's 'memory write': run after every graded essay.
    """
    essays = [e for e in db.list_essays(500) if e["score_overall"] is not None]

    def avg(rows, key):
        vals = [r[key] for r in rows if r[key] is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    overused = Counter()
    last_suggestions = {}
    for e in essays:
        try:
            for w in json.loads(e["overused_json"] or "[]"):
                word = (w.get("word") or "").lower()
                if word:
                    overused[word] += int(w.get("count", 1))
                    if w.get("suggestions"):
                        last_suggestions[word] = w["suggestions"]
        except (json.JSONDecodeError, TypeError):
            continue

    drill = db.drill_stats()
    stats = {
        "graded_essays": len(essays),
        "avg_overall_first_3": avg(essays[:3], "score_overall"),
        "avg_overall_last_3": avg(essays[-3:], "score_overall"),
        "top_error_categories": [
            {"category": c["category"], "count": c["n"]}
            for c in db.error_stats()[:8]
        ],
        "overused_words": [
            {"word": w, "count": n, "suggestions": last_suggestions.get(w, [])}
            for w, n in overused.most_common(8)
        ],
        "drills": drill,
    }

    previous = db.get_meta("profile", "(none yet — this is the first grading)")
    messages = [
        {"role": "system", "content": prompts.PROFILE_SYSTEM},
        {"role": "user", "content": (
            f"PREVIOUS PROFILE:\n{previous}\n\n"
            f"FRESH STATISTICS:\n{json.dumps(stats, indent=2)}\n\n"
            "Rewrite the profile now."
        )},
    ]
    profile = chat(messages, api_key, model, temperature=0.3).strip()
    if profile.startswith("```"):
        profile = profile.strip("`").lstrip("markdown").strip()
    db.set_meta("profile", profile)
    return profile
