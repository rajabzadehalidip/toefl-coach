"""Computed intelligence on top of the error ledger — no LLM calls.

These functions turn raw DB rows into the coaching signals: per-category
mastery, error trends across essays, study streaks, and today's plan.
Deterministic, cheap, and covered by tests/run_tests.py.
"""

from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional, Set

from . import db


def category_mastery(limit_essays: int = 500) -> List[Dict]:
    """Per-category error stats + a recent trend label.

    Trend compares error counts in the 3 newest essays vs the 3 before them:
    'improving ⬇️' | 'worsening ⬆️' | 'steady ➡️' | '—' (not enough data).
    """
    essays = db.list_essays(limit_essays)
    recent_ids = {e["id"] for e in essays[:3]}
    prev_ids = {e["id"] for e in essays[3:6]}

    stats: Dict[str, Dict] = {}
    for e in db.all_errors(limit=5000):
        row = stats.setdefault(e["category"], {
            "category": e["category"], "total": 0, "active": 0,
            "resolved": 0, "recent": 0, "before": 0,
        })
        row["total"] += 1
        row["resolved" if e["status"] == "resolved" else "active"] += 1
        if e["essay_id"] in recent_ids:
            row["recent"] += 1
        elif e["essay_id"] in prev_ids:
            row["before"] += 1

    for row in stats.values():
        if row["before"] == 0 and row["recent"] == 0:
            row["trend"] = "—"
        elif row["recent"] < row["before"]:
            row["trend"] = "improving ⬇️"
        elif row["recent"] > row["before"]:
            row["trend"] = "worsening ⬆️"
        else:
            row["trend"] = "steady ➡️"
    return sorted(stats.values(), key=lambda r: -r["total"])


def active_weaknesses(top: int = 5) -> List[Dict]:
    """Most frequent error categories that are NOT yet mastered (still active)."""
    return [r for r in category_mastery() if r["active"] > 0][:top]


def extinct_patterns() -> List[Dict]:
    """Categories where every logged error is resolved — worth celebrating."""
    return [r for r in category_mastery() if r["total"] > 0 and r["active"] == 0]


def activity_days() -> Set[str]:
    """Dates (ISO) with any study activity: a graded essay or a drill attempt."""
    days = {e["created_at"][:10] for e in db.list_essays(500)}
    days |= db.drill_days()
    return days


def streak_days() -> int:
    """Consecutive study days ending today (or yesterday if today is empty)."""
    days = activity_days()
    streak = 0
    d = dt.date.today()
    if d.isoformat() not in days:
        d -= dt.timedelta(days=1)  # today may simply not have started yet
    while d.isoformat() in days:
        streak += 1
        d -= dt.timedelta(days=1)
    return streak


def weakest_dimension() -> Optional[str]:
    """Lowest-scoring rubric dimension across the last 3 graded essays."""
    graded = [e for e in db.list_essays(50) if e["score_overall"] is not None][:3]
    if not graded:
        return None
    dims = {"Development": "score_development",
            "Organization": "score_organization",
            "Language use": "score_language"}
    scores = {}
    for label, key in dims.items():
        vals = [e[key] for e in graded if e[key] is not None]
        if vals:
            scores[label] = sum(vals) / len(vals)
    return min(scores, key=scores.get) if scores else None


def todays_plan() -> str:
    """A short, data-driven suggestion for today's practice."""
    n_essays = len(db.list_essays(1000))
    due = len(db.due_errors(999))
    if n_essays == 0:
        return ("1. ✍️ Write your **diagnostic** essay (Academic Discussion, timed)\n"
                "2. 🔄 Your personalized plan appears here after it's graded")
    weakest = weakest_dimension()
    if weakest:
        lines = [f"1. ✍️ One timed task — focus on **{weakest}** (your lowest dimension)"]
    else:
        lines = ["1. ✍️ One timed task"]
    if due:
        lines.append(f"2. 🎯 Drill session — {min(due, 8)} of your logged mistakes are due")
    else:
        lines.append("2. 📚 No drills due — grading a new essay creates new ones")
    streak = streak_days()
    if streak >= 2:
        lines.append(f"🔥 {streak}-day streak — keep it alive")
    return "\n".join(lines)
