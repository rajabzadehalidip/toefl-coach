# Changelog

All notable changes to the TOEFL Writing Coach.

## 1.0.0 — 2026-08-28

First stable release. The complete learning loop: practice → grade → log → drill →
improve, with the coach getting sharper the more you use it.

### Added
- **Today's plan** — a data-driven daily suggestion (which rubric dimension to
  practice, how many drills are due, study streak 🔥), computed from your history.
- **Category mastery & trends** — per-error-category table with total / active /
  resolved counts and a trend (improving ⬇️ / steady ➡️ / worsening ⬆️) comparing
  your last 3 essays vs the previous 3.
- **Extinct patterns** 🎉 — categories with every error resolved are celebrated and
  excluded from future task targeting.
- **Smarter examiner** — new tasks target only your *unresolved* weaknesses and are
  told to skip patterns you've already beaten.
- **Study streak** — consecutive days with a graded essay or drill attempt.
- Consolidated test suite: `python tests/run_tests.py` (43 checks, incl. a mocked
  Turso HTTP round-trip).

### Fixed
- Countdown timer now ticks live every second (`@st.fragment`), instead of only
  updating on page interaction.
- Active task + draft **survive a page refresh** (and device switches) — persisted
  to the database, restored automatically.
- Submit button is always visible; short drafts get a helpful warning instead of a
  mysteriously disabled button.
- New **🗑 Discard task** button to abandon a practice cleanly.

## 0.1.1 — 2026-08-27
- Streamlit Community Cloud deploy support: secrets bridge (`st.secrets` → env),
  Turso HTTP backend for persistent memory on the ephemeral cloud filesystem.

## 0.1.0 — 2026-08-27
- Initial release: ETS-rubric grading via OpenRouter, structured error ledger with
  SM-2-style spaced-repetition drills, weakness-aware task generation, consolidated
  learner profile, local lexical metrics, dual storage (local SQLite / Turso).
