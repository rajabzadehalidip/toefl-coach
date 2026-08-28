# ✍️ TOEFL Writing Coach

A personal **agentic LLM writing tutor** for TOEFL iBT preparation — writing only.

Unlike one-shot AI graders, this coach **remembers you**: every graded essay feeds a
structured *error ledger*, every logged mistake comes back as **spaced-repetition drills
generated from your own sentences**, and a consolidated **learner profile** steers the
practice tasks toward your weak spots.

## What it does

| Tab | What happens |
|---|---|
| ✍️ **Practice** | Generates realistic TOEFL tasks (Academic Discussion, Integrated, or your own prompt) — *quietly engineered to exercise your known weaknesses*. Timed like the real test. |
| 📋 **Feedback** | Strict ETS-rubric scoring (0–5 on Development / Organization / Language), strengths, ranked fixes, overused-word tracking, local lexical metrics, and an optional 5/5 model response. Every error is parsed into the ledger as `category / original / correction / rule / severity`. |
| 🎯 **Drills** | Turns your due errors into fix-the-sentence and multiple-choice exercises. Pass → the interval grows (1 → 3 → 7 → 16 → … days) until the pattern is *resolved*. Fail → it comes back tomorrow. |
| 📈 **Progress** | Rubric scores over time, error-category bars, lexical profile (sentence variety, TTR, long-word ratio), first-vs-recent radar chart, drill pass rate. |
| 🧠 **Profile & Ledger** | The editable markdown "memory" of you, the full error ledger, and an overused-words aggregate. |

## The loop

```
        ┌──────────────────────────────────────────────┐
        │                                              │
        ▼                                              │
   Examiner ──▶ you write ──▶ Grader ──▶ error ledger ─┴─▶ Drills (spaced repetition)
   (weakness-                    │           │
    aware tasks)                 │           ▼
                                 └────▶ profile (consolidated after every essay)
```

**How it gets smarter over time** — the coach's intelligence is cumulative:

1. Every graded essay parses your mistakes into a structured **error ledger**
   (category, original, correction, rule, severity).
2. Your own mistakes come back as **drills on a spaced-repetition schedule** — pass
   pushes the next review further out; a pattern with all errors resolved becomes
   **extinct** 🎉 and is excluded from future practice.
3. The **examiner targets only your current weaknesses** (it knows which categories
   are improving, worsening, or extinct) and designs tasks that quietly force you to
   use the structures you keep getting wrong.
4. A **profile** is rewritten after every essay, so the tutor remembers your
   strengths, habits, and goals across sessions.
5. **Today's plan**, category **mastery & trends**, your rubric score history, and a
   study **streak** keep the feedback loop visible and motivating.

## Tests

```bash
python tests/run_tests.py   # 43 checks: DB + SRS, insights, lexstats, JSON parsing, Turso protocol (mocked)
```

## Quickstart

```bash
cd toefl-coach
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export OPENROUTER_API_KEY=sk-or-...   # from https://openrouter.ai/keys
# optional: export OPENROUTER_MODEL=anthropic/claude-sonnet-4.5

streamlit run app.py
```

Your key and essays never leave your machine (besides the API calls to OpenRouter you
make yourself). All memory lives in a single portable `coach.db` SQLite file.

## Suggested routine

1. **Diagnostic**: write your first Academic Discussion task cold — it seeds the profile.
2. **Daily**: one timed task + a drill session (~15 min of fixing *your* errors).
3. **Weekly**: check Progress; reactivate any "resolved" errors you suspect crept back.
4. Two days before the test: drill everything active one last time.

## Choosing the model

Grading nuance matters most — use a strong model (Claude Sonnet, GPT-4.1, Gemini Pro).
A cheap/fast model noticeably weakens rubric adherence and error detection.

## Roadmap ideas

- TTS for the integrated-task lecture (real-test feel: listening, no transcript)
- Weakness-targeted micro-lessons before drills
- Anki export of the error ledger
- Per-category mastery scores with FSRS scheduling
- Draft-vs-revision diff view ("rewrite essay #12 and rescore")

## Deploying to Streamlit Community Cloud

The app auto-detects its storage: **local SQLite by default**, **Turso (free hosted
SQLite) when `TURSO_DB_URL` + `TURSO_DB_TOKEN` are set** — which matters because
Community Cloud's filesystem is ephemeral and would otherwise wipe `coach.db` on every
restart. No code changes between the two.

### 1. Push to GitHub (private repo is fine)

### 2. Create a free Turso database (your coach's long-term memory)

```bash
# sign up at https://turso.com / install: https://docs.turso.tech/cli
turso auth signup
turso db create toefl-coach
turso db show toefl-coach --url          # → libsql://toefl-coach-<you>.turso.io
turso db tokens create toefl-coach       # → a long token string
```

(Or create both from the Turso dashboard — copy the database URL and a token.)

### 3. Deploy + secrets

1. [share.streamlit.io](https://share.streamlit.io) → **New app** → pick the repo,
   branch `main`, main file `app.py`.
2. App **Settings → Secrets**:
   ```toml
   OPENROUTER_API_KEY = "sk-or-v1-..."
   TURSO_DB_URL  = "libsql://toefl-coach-<you>.turso.io"
   TURSO_DB_TOKEN = "eyJ..."

   # optional
   OPENROUTER_MODEL = "anthropic/claude-sonnet-4.5"
   ```
3. **Settings → General → App visibility** → Private, so only you can open it.

The sidebar shows which storage is active (🌩 Turso = persistent). Locally, `./run.sh`
keeps using `coach.db`; set the same two env vars in `.env` if you want local runs on
Turso too.

## Project layout

```
app.py                Streamlit UI (4 tabs)
coach/
  db.py               SQLite schema + SM-2-style spaced repetition
  llm.py              OpenRouter client (JSON-mode + retries)
  rubric.py           Condensed ETS rubrics for both writing tasks
  prompts.py          System prompts: grader, examiner, drills, profile, model answer
  grading.py          Grading pipeline + profile consolidation
  practice.py         Weakness-aware task generation
  drills.py           Drill session builder + answer checking
  lexstats.py         Local lexical metrics (no LLM)
```
