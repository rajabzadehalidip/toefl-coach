"""Consolidated test suite for the TOEFL Writing Coach.

Run from the project root:
    python tests/run_tests.py
(or with the project venv: .venv/bin/python tests/run_tests.py)

Uses a throwaway SQLite DB and a mocked Turso HTTP server — no network,
no API key, safe to run anywhere.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

# Point storage at a throwaway DB BEFORE importing coach modules.
_TMP_DB = os.path.join(tempfile.mkdtemp(prefix="coach_test_"), "test.db")
os.environ["TOEFL_COACH_DB"] = _TMP_DB
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PASS = []


def ok(name, condition, detail=""):
    if not condition:
        raise AssertionError(f"FAIL: {name} {detail}")
    PASS.append(name)


# ===================================================================== sqlite
from coach import db, insights, lexstats, practice  # noqa: E402
from coach.llm import extract_json  # noqa: E402

db.init_db(); db.init_db()  # idempotent
ok("backend is sqlite", db.storage_backend() == "sqlite")

eid = db.insert_essay(
    "academic_discussion", "T", "p", "essay body", 60.0,
    {"development": 3.0, "organization": 3.5, "language": 2.5, "overall": 3.0},
    lexstats.analyze("Hello world. A second sentence here for metrics."),
    [{"word": "good", "count": 3}],
)
ok("insert_essay returns id 1", eid == 1, f"got {eid}")
ok("get_essay round-trip", db.get_essay(1)["score_overall"] == 3.0)
ok("previous_overall empty", db.previous_overall(1) is None)

db.insert_errors(eid, [
    {"category": "articles-determiners", "original": "a hour", "correction": "an hour",
     "rule": "an before vowel sounds", "severity": 2},
    {"category": "run-on-fragment", "original": "x", "correction": "y", "rule": "r", "severity": "3"},
    {"category": None, "severity": None},
])
ok("messy error rows sanitized", len(db.all_errors()) == 3)
ok("due immediately after grading", len(db.due_errors()) == 3)
ok("due sorted by severity", db.due_errors()[0]["severity"] >= db.due_errors()[-1]["severity"])

# SRS progression: 1d -> 3d -> ~interval*ease -> resolved at >=45d
r = db.update_error_srs(1, True);  ok("SRS pass 1", (r["reps"], r["interval_days"]) == (1, 1))
r = db.update_error_srs(1, True);  ok("SRS pass 2", (r["reps"], r["interval_days"]) == (2, 3))
db.update_error_srs(1, True)       # reps=3 -> interval grows by ease
r = db.update_error_srs(1, True);  ok("SRS grows by ease", r["interval_days"] > 3)
r = db.update_error_srs(1, False); ok("SRS fail resets", (r["reps"], r["interval_days"]) == (0, 1))

db.log_drill(1, True, "mcq"); db.log_drill(1, False, "fix_sentence")
ok("drill_stats", db.drill_stats() == {"attempts": 2, "passed": 1})
ok("drill_days has today", len(db.drill_days()) == 1)

db.set_meta("profile", "v1"); ok("meta set/get", db.get_meta("profile") == "v1")
db.del_meta("profile");       ok("meta deleted", db.get_meta("profile") is None)

# ================================================================= insights
# Seed 6 essays. Windows (newest-first): recent = last 3 inserted, before = the
# 3 before them. Language drops 4.0 -> 2.0 across that boundary.
seed_ids = []
for i in range(6):
    lang = 4.0 if i < 3 else 2.0
    seed_ids.append(db.insert_essay(
        "academic_discussion", f"E{i}", "p", f"essay {i}", 300.0,
        {"development": 4.0, "organization": 4.0, "language": lang, "overall": 3.5}))
before_ids, recent_ids = seed_ids[:3], seed_ids[3:]

def add_err(cat, essay_id):
    db.insert_errors(essay_id, [{"category": cat, "original": "o", "correction": "c",
                                "rule": "r", "severity": 2}])

for e in before_ids:
    add_err("articles-determiners", e); add_err("articles-determiners", e)  # before: 6
add_err("articles-determiners", recent_ids[0])                              # recent: 1
add_err("prepositions", before_ids[0])                                      # before: 1
add_err("prepositions", recent_ids[0]); add_err("prepositions", recent_ids[0])
add_err("prepositions", recent_ids[1])                                      # recent: 3
add_err("punctuation", recent_ids[0]); add_err("punctuation", recent_ids[0])
add_err("punctuation", recent_ids[1])                                       # recent: 3

m = {r["category"]: r for r in insights.category_mastery()}
a = m["articles-determiners"]
# total 8: 7 seeded + 1 from the sqlite section above (that essay predates both windows)
ok("mastery counts", (a["total"], a["active"], a["before"], a["recent"]) == (8, 8, 6, 1), str(a))
ok("trend improving", a["trend"] == "improving ⬇️", a["trend"])
p = m["prepositions"]
ok("trend worsening", p["trend"] == "worsening ⬆️", p["trend"])

# make punctuation extinct
for e in db.all_errors():
    if e["category"] == "punctuation":
        db.set_error_status(e["id"], "resolved")
extinct = insights.extinct_patterns()
ok("extinct detection", [r["category"] for r in extinct] == ["punctuation"])
weak = insights.active_weaknesses(5)
ok("active_weaknesses excludes extinct", all(r["category"] != "punctuation" for r in weak))
ok("weakness order by frequency",
   [r["category"] for r in weak][:2] == ["articles-determiners", "prepositions"],
   str([r["category"] for r in weak]))

ok("streak >= 1", insights.streak_days() >= 1)
ok("weakest dimension", insights.weakest_dimension() == "Language use", insights.weakest_dimension())
plan = insights.todays_plan()
ok("todays_plan mentions drills", "Drill" in plan and "Language use" in plan)

# ================================================================= lexstats
mt = lexstats.analyze("Technology is good. I think technology is very good because it helps students learn a lot of things quickly.")
ok("lexstats basic", mt["words"] > 15 and mt["sentences"] == 2)
ok("vague words found", "very" in mt["vague_counts"] and "i think" in mt["vague_counts"])
# 'a lot of' occurs once; plain 'a lot' must be dropped, not double counted
ok("a lot dedup exact", "a lot" not in mt["vague_counts"] and mt["vague_counts"].get("a lot of") == 1)

# ================================================================= llm utils
ok("json plain", extract_json('{"a": 1}') == {"a": 1})
ok("json fenced", extract_json('```json\n{"a": [1,2]}\n```') == {"a": [1, 2]})
ok("json chatty", extract_json('Sure!\n{"scores": {"overall": 3.5}} hope it helps') == {"scores": {"overall": 3.5}})

ok("GRADE_USER formats", "academic_discussion" in
   __import__("coach").prompts.GRADE_USER.format(
       task_type="academic_discussion", rubric="R", prompt="P", essay="E", word_count=1))
ok("CHECK_FIX_SYSTEM formats", "verdict" in
   __import__("coach").prompts.CHECK_FIX_SYSTEM.format(sentence="s", answer="a", rule="r", user="u"))
ok("format_task custom", practice.format_task({"_type": "custom", "prompt_text": "x"}) == "x")

# ================================================================= turso mock
ESSAY_COLS = ["created_at", "task_type", "prompt_title", "prompt_body", "text",
              "duration_seconds", "score_development", "score_organization",
              "score_language", "score_overall", "metrics", "overused_json"]
os.environ["TURSO_DB_URL"] = "libsql://toefl-coach-myorg.turso.io"
os.environ["TURSO_DB_TOKEN"] = "fake-token"
try:
    ok("backend switches to turso", db.storage_backend() == "turso")
    import coach.db as dbmod
    posts, TABLES = [], {"essays": []}

    class FakeResp:
        status_code = 200
        def __init__(self, body): self._body = body
        def json(self): return self._body

    def fake_post(url, json=None, headers=None, timeout=None):
        posts.append({"url": url, "headers": headers, "body": json})
        assert json["requests"][-1]["type"] == "close"
        req = json["requests"][0]
        sql = req["stmt"]["sql"]
        args = [a["value"] if isinstance(a, dict) and a.get("type") != "null" else None
                for a in (req["stmt"].get("args") or [])]
        out_rows, last_id, cols = [], None, []
        if sql.startswith("CREATE TABLE"):
            TABLES[sql.split("EXISTS")[1].split("(")[0].strip()] = []
        elif sql.startswith("INSERT INTO essays"):
            row = dict(zip(ESSAY_COLS, args))
            row["id"] = len(TABLES["essays"]) + 1
            TABLES["essays"].append(row); last_id = row["id"]
        elif sql.startswith("SELECT MAX"):
            cols, out_rows = [{"name": "id"}], [[len(TABLES["essays"]) or 1]]
        elif sql.startswith("SELECT * FROM essays"):
            cols = [{"name": "id"}, {"name": "score_overall"}]
            out_rows = [[r["id"], r["score_overall"]] for r in TABLES["essays"]]
        return FakeResp({"results": [
            {"type": "ok", "response": {"type": "execute",
             "result": {"cols": cols, "rows": out_rows, "last_insert_rowid": last_id}}},
            {"type": "ok", "response": {"type": "close"}},
        ]})

    with patch.object(dbmod.requests, "post", fake_post):
        db.init_db()
        tid = db.insert_essay("academic_discussion", "T", "p", "essay", None,
                              {"overall": 4.0, "development": 4.0, "organization": 4.0, "language": 4.0})
        ok("turso insert id", tid == 1)
        ok("turso list rows parsed", db.list_essays()[0]["score_overall"] == 4.0)
    ins = next(p for p in posts if p["body"]["requests"][0]["stmt"]["sql"].startswith("INSERT INTO essays"))
    ok("turso url conversion", ins["url"] == "https://toefl-coach-myorg.turso.io/v2/pipeline")
    ok("turso bearer auth", ins["headers"]["Authorization"] == "Bearer fake-token")
    stmt = ins["body"]["requests"][0]["stmt"]
    ok("typed args: text", stmt["args"][1] == {"type": "text", "value": "academic_discussion"})
    ok("typed args: float", stmt["args"][6] == {"type": "float", "value": 4.0})
    ok("typed args: null", {"type": "null"} in stmt["args"])
    ok("turso param helpers", db._turso_param(None) == {"type": "null"}
       and db._turso_param(True) == {"type": "integer", "value": 1}
       and db._turso_param("s") == {"type": "text", "value": "s"})
finally:
    os.environ.pop("TURSO_DB_URL", None)
    os.environ.pop("TURSO_DB_TOKEN", None)

ok("backend back to sqlite", db.storage_backend() == "sqlite")

print(f"\n✅ ALL {len(PASS)} TESTS PASSED")
for name in PASS:
    print(f"   ✓ {name}")
