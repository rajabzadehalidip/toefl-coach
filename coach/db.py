"""Storage layer: essays, the error ledger (with SM-2-style scheduling),
drill log, and a small key-value store for the learner profile.

Two interchangeable backends, picked automatically per call:
- Local SQLite file (default) — data lives in ``coach.db`` next to the project.
- Turso (free hosted SQLite) — used when TURSO_DB_URL + TURSO_DB_TOKEN env
  vars are set, e.g. on Streamlit Community Cloud whose filesystem is
  ephemeral. Same SQL, so the app works identically in both places.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

DB_PATH = Path(os.environ.get("TOEFL_COACH_DB", Path(__file__).resolve().parent.parent / "coach.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS essays(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  task_type TEXT NOT NULL,
  prompt_title TEXT,
  prompt_body TEXT,
  text TEXT NOT NULL,
  duration_seconds REAL,
  score_development REAL,
  score_organization REAL,
  score_language REAL,
  score_overall REAL,
  metrics TEXT,
  overused_json TEXT
);
CREATE TABLE IF NOT EXISTS errors(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  essay_id INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  category TEXT NOT NULL,
  original TEXT,
  correction TEXT,
  rule TEXT,
  severity INTEGER DEFAULT 2,
  reps INTEGER DEFAULT 0,
  ease REAL DEFAULT 2.5,
  interval_days REAL DEFAULT 0,
  next_review TEXT NOT NULL,
  last_review TEXT,
  status TEXT DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS drill_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  error_id INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  passed INTEGER NOT NULL,
  kind TEXT
);
CREATE TABLE IF NOT EXISTS meta(
  key TEXT PRIMARY KEY,
  value TEXT
);
"""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")


def _today() -> str:
    return dt.date.today().isoformat()


# ---------------------------------------------------------------- backend

def _turso_conf() -> Optional[Dict[str, str]]:
    url = os.environ.get("TURSO_DB_URL", "").strip()
    token = os.environ.get("TURSO_DB_TOKEN", "").strip()
    if url and token:
        if url.startswith("libsql://"):
            url = "https://" + url[len("libsql://"):]
        if not url.startswith("http"):
            url = "https://" + url
        return {"url": url.rstrip("/") + "/v2/pipeline", "token": token}
    return None


def storage_backend() -> str:
    return "turso" if _turso_conf() else "sqlite"


def storage_desc() -> str:
    if storage_backend() == "turso":
        return "Turso cloud database (persistent across restarts)"
    return f"local SQLite file ({DB_PATH.name})"


def _turso_param(v: Any) -> Any:
    """Python value -> Hrana JSON typed value."""
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": int(v)}
    if isinstance(v, int):
        return {"type": "integer", "value": v}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    return {"type": "text", "value": str(v)}


def _turso_run(sql: str, params: tuple) -> Dict:
    conf = _turso_conf()
    payload = {
        "requests": [
            {"type": "execute",
             "stmt": {"sql": sql, "args": [_turso_param(p) for p in params]}},
            {"type": "close"},
        ]
    }
    resp = requests.post(
        conf["url"], json=payload,
        headers={"Authorization": f"Bearer {conf['token']}"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Turso HTTP {resp.status_code}: {resp.text[:300]}")
    out: Dict[str, Any] = {"rows": [], "lastrowid": None}
    for res in resp.json().get("results", []):
        if res.get("type") == "error":
            raise RuntimeError(f"Turso error: {res.get('error', {}).get('message', res)}")
        if res.get("type") == "ok" and res.get("response", {}).get("type") == "execute":
            result = res["response"].get("result", {})
            cols = [c.get("name", f"col{i}") for i, c in enumerate(result.get("cols", []))]
            out["rows"] = [dict(zip(cols, row)) for row in result.get("rows", [])]
            out["lastrowid"] = result.get("last_insert_rowid")
    return out


def _sqlite_run(sql: str, params: tuple) -> Dict:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql, params)
        return {"rows": [dict(r) for r in cur.fetchall()], "lastrowid": cur.lastrowid}


def _run(sql: str, params: tuple = ()) -> Dict:
    if _turso_conf():
        return _turso_run(sql, params)
    return _sqlite_run(sql, params)


def init_db() -> None:
    for stmt in (s.strip() for s in SCHEMA.split(";")):
        if stmt:
            _run(stmt)


# ---------------------------------------------------------------- essays

def insert_essay(
    task_type: str,
    prompt_title: str,
    prompt_body: str,
    text: str,
    duration_seconds: Optional[float],
    scores: Dict[str, float],
    metrics: Optional[Dict] = None,
    overused: Optional[List] = None,
) -> int:
    res = _run(
        """INSERT INTO essays(created_at, task_type, prompt_title, prompt_body, text,
                              duration_seconds, score_development, score_organization,
                              score_language, score_overall, metrics, overused_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            _now(), task_type, prompt_title, prompt_body, text, duration_seconds,
            scores.get("development"), scores.get("organization"),
            scores.get("language"), scores.get("overall"),
            json.dumps(metrics) if metrics else None,
            json.dumps(overused) if overused else None,
        ),
    )
    if res["lastrowid"]:
        return res["lastrowid"]
    return _run("SELECT MAX(id) AS id FROM essays")["rows"][0]["id"]


def list_essays(limit: int = 200) -> List[Dict]:
    return _run("SELECT * FROM essays ORDER BY id DESC LIMIT ?", (limit,))["rows"]


def get_essay(essay_id: int) -> Optional[Dict]:
    rows = _run("SELECT * FROM essays WHERE id = ?", (essay_id,))["rows"]
    return rows[0] if rows else None


def previous_overall(essay_id: int) -> Optional[float]:
    rows = _run(
        """SELECT score_overall FROM essays
           WHERE id < ? AND score_overall IS NOT NULL
           ORDER BY id DESC LIMIT 1""",
        (essay_id,),
    )["rows"]
    return rows[0]["score_overall"] if rows else None


# ---------------------------------------------------------------- errors

def insert_errors(essay_id: int, errors: List[Dict]) -> int:
    """Store graded errors. They are immediately due for drilling."""
    inserted = 0
    for e in errors:
        try:
            severity = int(e.get("severity", 2))
        except (TypeError, ValueError):
            severity = 2
        _run(
            """INSERT INTO errors(essay_id, created_at, category, original, correction,
                                  rule, severity, next_review)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                essay_id, _now(),
                e.get("category") or "other",
                e.get("original") or "",
                e.get("correction") or "",
                e.get("rule") or "",
                max(1, min(3, severity)),
                _today(),  # due right away: drill while it's fresh
            ),
        )
        inserted += 1
    return inserted


def errors_for_essay(essay_id: int) -> List[Dict]:
    return _run("SELECT * FROM errors WHERE essay_id = ? ORDER BY id", (essay_id,))["rows"]


def all_errors(status: Optional[str] = None, limit: int = 500) -> List[Dict]:
    if status:
        return _run(
            "SELECT * FROM errors WHERE status = ? ORDER BY id DESC LIMIT ?",
            (status, limit),
        )["rows"]
    return _run("SELECT * FROM errors ORDER BY id DESC LIMIT ?", (limit,))["rows"]


def due_errors(limit: int = 30) -> List[Dict]:
    """Active errors whose next review date has arrived, worst first."""
    return _run(
        """SELECT * FROM errors
           WHERE status = 'active' AND next_review <= ?
           ORDER BY severity DESC, next_review ASC LIMIT ?""",
        (_today(), limit),
    )["rows"]


def error_stats() -> List[Dict]:
    return _run(
        """SELECT category, COUNT(*) AS n, SUM(severity) AS total_severity
           FROM errors GROUP BY category ORDER BY n DESC"""
    )["rows"]


def set_error_status(error_id: int, status: str) -> None:
    _run("UPDATE errors SET status = ? WHERE id = ?", (status, error_id))


def update_error_srs(error_id: int, passed: bool) -> Optional[Dict]:
    """SM-2-lite scheduling for one error card.

    pass  -> reps+1, ease+0.1, interval grows (1, 3, then ~interval*ease days);
             interval >= 45 days means the pattern is considered extinguished
             and the card is marked resolved.
    fail  -> reps reset, ease-0.2 (floor 1.3), interval back to 1 day.
    """
    rows = _run("SELECT * FROM errors WHERE id = ?", (error_id,))["rows"]
    if not rows:
        return None
    row = rows[0]
    if passed:
        reps = row["reps"] + 1
        ease = min(3.0, row["ease"] + 0.1)
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 3
        else:
            interval = max(1, round(row["interval_days"] * ease))
        status = "resolved" if interval >= 45 else "active"
    else:
        reps = 0
        ease = max(1.3, row["ease"] - 0.2)
        interval = 1
        status = "active"
    next_review = (dt.date.today() + dt.timedelta(days=interval)).isoformat()
    _run(
        """UPDATE errors SET reps=?, ease=?, interval_days=?, next_review=?,
                             last_review=?, status=? WHERE id=?""",
        (reps, ease, interval, next_review, _today(), status, error_id),
    )
    updated = _run("SELECT * FROM errors WHERE id = ?", (error_id,))["rows"]
    return updated[0] if updated else None


# ---------------------------------------------------------------- drills

def log_drill(error_id: int, passed: bool, kind: str) -> None:
    _run(
        "INSERT INTO drill_log(error_id, created_at, passed, kind) VALUES (?,?,?,?)",
        (error_id, _now(), int(passed), kind),
    )


def drill_stats() -> Dict[str, int]:
    rows = _run(
        "SELECT COUNT(*) AS attempts, COALESCE(SUM(passed), 0) AS passed FROM drill_log"
    )["rows"]
    return {"attempts": rows[0]["attempts"], "passed": rows[0]["passed"]} if rows else {"attempts": 0, "passed": 0}


# ---------------------------------------------------------------- meta

def get_meta(key: str, default: Optional[str] = None) -> Optional[str]:
    rows = _run("SELECT value FROM meta WHERE key = ?", (key,))["rows"]
    return rows[0]["value"] if rows else default


def set_meta(key: str, value: str) -> None:
    _run(
        "INSERT INTO meta(key, value) VALUES (?,?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
