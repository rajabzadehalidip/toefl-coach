"""TOEFL Writing Coach — Streamlit app.

Run with:  streamlit run app.py
"""

import json
import os
import time
from collections import Counter

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from coach import db, drills, grading, lexstats, practice
from coach.llm import LLMError

st.set_page_config(page_title="TOEFL Writing Coach", page_icon="✍️", layout="wide")
db.init_db()

def _get_secret_or_env(name: str, default: str = "") -> str:
    """Read a config value from st.secrets (Streamlit Cloud) or the
    environment (local / .env). Never crashes when secrets don't exist."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


DEFAULT_MODEL = _get_secret_or_env("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")

# Materialize Streamlit Cloud secrets into env vars so coach.db (which reads
# only the environment, not streamlit) picks them up on every call.
for _name in ("TURSO_DB_URL", "TURSO_DB_TOKEN"):
    _val = _get_secret_or_env(_name)
    if _val:
        os.environ.setdefault(_name, _val)

st.title("✍️ TOEFL Writing Coach")
st.caption(
    "Your personal agentic writing tutor: grades against the ETS rubric, keeps an error "
    "ledger, drills your own mistakes back at you on a spaced-repetition schedule, and "
    "remembers your strengths and weaknesses across sessions."
)

# ------------------------------------------------------------------ sidebar

with st.sidebar:
    api_key = st.text_input(
        "OpenRouter API key", type="password",
        value=_get_secret_or_env("OPENROUTER_API_KEY"),
    )
    model = st.text_input("Model (OpenRouter slug)", value=DEFAULT_MODEL)
    st.caption(
        "Get a key at [openrouter.ai/keys](https://openrouter.ai/keys) — any model works, "
        "e.g. `anthropic/claude-sonnet-4.5`, `openai/gpt-4.1`, `google/gemini-2.5-pro`."
    )
    st.divider()
    n_essays = len(db.list_essays(1000))
    n_due = len(db.due_errors(limit=999))
    c1, c2 = st.columns(2)
    c1.metric("Essays", n_essays)
    c2.metric("Drills due", n_due)
    if db.storage_backend() == "turso":
        st.caption("🌩 Storage: Turso cloud DB — memory survives restarts")
    else:
        st.caption("💾 Storage: local `coach.db` — all data stays on this machine")


def weakness_summary() -> str:
    """Context the examiner uses to design tasks that target your weak spots."""
    parts = []
    cats = db.error_stats()
    if cats:
        parts.append(
            "Most frequent error categories: "
            + ", ".join(f"{c['category']} ({c['n']}×)" for c in cats[:5])
        )
    profile = db.get_meta("profile")
    if profile:
        parts.append("Learner profile:\n" + profile)
    return "\n\n".join(parts)


# ------------------------------------------------------------------ practice

def _render_feedback(lr: dict, api_key: str, model: str) -> None:
    r, scores, metrics = lr["result"], lr["result"]["scores"], lr["metrics"]
    st.divider()
    st.subheader(f"📋 Feedback — essay #{lr['essay_id']}")

    prev = db.previous_overall(lr["essay_id"])
    cols = st.columns(4)
    for col, (label, key) in zip(
        cols,
        [("Overall", "overall"), ("Development", "development"),
         ("Organization", "organization"), ("Language use", "language")],
    ):
        delta = round(scores[key] - prev, 1) if prev is not None else None
        col.metric(label, f"{scores[key]:.1f} / 5", delta=delta)

    st.markdown(r.get("summary", ""))

    if r.get("strengths"):
        st.success("**Strengths**\n\n" + "\n".join(f"- {s}" for s in r["strengths"]))
    if r.get("priority_fixes"):
        st.warning("**Priority fixes**\n\n" + "\n".join(
            f"{i}. {f}" for i, f in enumerate(r["priority_fixes"], 1)))

    errs = r.get("errors") or []
    if errs:
        st.markdown(f"**📒 Error ledger — {len(errs)} entries added** (they come back as drills 🔁)")
        st.dataframe(
            pd.DataFrame([{
                "category": e.get("category"),
                "original": e.get("original"),
                "correction": e.get("correction"),
                "rule": e.get("rule"),
                "severity": e.get("severity"),
            } for e in errs]),
            width="stretch", hide_index=True,
        )

    if r.get("overused_words"):
        badges = " · ".join(
            f"`{w.get('word')}`×{w.get('count', '?')} → {', '.join(w.get('suggestions', [])[:2])}"
            for w in r["overused_words"]
        )
        st.info(f"**Overused words** (tracked across essays): {badges}")

    if r.get("nice_phrases"):
        st.caption("🌟 Nice phrases: " + " · ".join(f"“{p}”" for p in r["nice_phrases"][:5]))

    st.caption("📊 " + lexstats.format_metrics(metrics))

    ma_key = f"model_answer_{lr['essay_id']}"
    if st.button("💡 Show a 5/5 model response"):
        try:
            with st.spinner("Writing a model response..."):
                answer = st.session_state.get(ma_key) or grading.model_answer(
                    api_key, model, lr["task_type"], lr["prompt_body"])
                st.session_state[ma_key] = answer
            st.markdown(answer)
        except LLMError as e:
            st.error(f"Model answer failed: {e}")


tab_practice, tab_drills, tab_progress, tab_ledger = st.tabs(
    ["✍️ Practice", "🎯 Drills", "📈 Progress", "🧠 Profile & Ledger"])

with tab_practice:
    if n_essays == 0:
        st.info("🏁 Your first essay doubles as the **diagnostic** — it builds your "
                "weakness map and error ledger, so make it a real effort.")

    left, right = st.columns([2, 3])
    reuse = "— write a new one —"
    with left:
        task_type = st.selectbox(
            "Task type",
            list(practice.TASK_DURATIONS.keys()),
            format_func=practice.TASK_LABELS.get,
        )
    with right:
        if task_type == "custom":
            custom_prompt = st.text_area(
                "Paste your prompt (any writing task you want graded)", height=90)
        else:
            past = db.list_essays(30)
            if past:
                reuse = st.selectbox(
                    "Re-use a previous prompt",
                    ["— write a new one —"] + [
                        f"#{e['id']} · {e['prompt_title'] or e['task_type']} · {e['created_at'][:10]}"
                        for e in past
                    ],
                )

    def _start_task(task: dict) -> None:
        st.session_state.task = task
        st.session_state.task_started = time.time()
        st.session_state.pop("last_result", None)
        st.session_state.pop("draft", None)
        for k in [k for k in st.session_state if k.startswith("model_answer_")]:
            st.session_state.pop(k)

    if task_type != "custom":
        if st.button("🎲 Generate task", type="primary"):
            try:
                with st.spinner("Designing a task targeted at your weaknesses..."):
                    task = practice.generate_task(api_key, model, task_type, weakness_summary())
                _start_task(task)
            except LLMError as e:
                st.error(e)
    elif st.button("Start custom task", type="primary"):
        _start_task({
            "_type": "custom",
            "title": "Custom practice",
            "prompt_text": custom_prompt.strip() or "Free writing: pick any topic.",
        })

    task = st.session_state.get("task")
    if task:
        body = practice.format_task(task)
        kind = task.get("_type", "custom")
        limit = practice.TASK_DURATIONS.get(kind, 25) * 60
        elapsed = time.time() - st.session_state.get("task_started", time.time())
        remaining = max(0, int(limit - elapsed))
        st.caption(
            f"⏱ **{remaining // 60}:{remaining % 60:02d} remaining** of {limit // 60} min "
            "· the clock refreshes whenever the page updates"
        )
        with st.container(border=True):
            st.markdown(body)

        draft = st.text_area("✏️ Your response", height=320, key="draft")
        st.caption(f"{len((draft or '').split())} words · TOEFL discussion answers are usually 100+")

        if st.button("Submit for grading", type="primary",
                     disabled=not draft or len(draft.split()) < 20):
            duration = time.time() - st.session_state.get("task_started", time.time())
            try:
                with st.spinner("Grading against the ETS rubric + extracting errors (≈30–60 s)..."):
                    result = grading.grade_essay(api_key, model, kind, body, draft)
                    metrics = lexstats.analyze(draft)
                    essay_id = db.insert_essay(
                        kind, task.get("title", "Practice"), body, draft, duration,
                        result["scores"], metrics, result.get("overused_words"),
                    )
                    db.insert_errors(essay_id, result.get("errors", []))
                try:
                    grading.update_profile(api_key, model)
                except LLMError:
                    st.caption("(Profile auto-update failed — the graded essay was still saved.)")
                st.session_state.last_result = {
                    "result": result, "metrics": metrics, "essay_id": essay_id,
                    "prompt_body": body, "task_type": kind,
                }
                st.session_state.pop("task", None)
                st.session_state.pop("task_started", None)
                st.session_state.pop("draft", None)
                st.rerun()
            except LLMError as e:
                st.error(f"Grading failed: {e}")
    elif reuse != "— write a new one —":
        essay_id = int(reuse.split(" · ")[0].lstrip("#"))
        essay = db.get_essay(essay_id)
        if essay and st.button(f"↩️ Practice #{essay_id} again"):
            _start_task({
                "_type": essay["task_type"],
                "title": essay["prompt_title"] or "Re-practice",
                "prompt_text": essay["prompt_body"] or "",
            })
            st.rerun()

    lr = st.session_state.get("last_result")
    if lr:
        _render_feedback(lr, api_key, model)

# ------------------------------------------------------------------ drills

with tab_drills:
    due = db.due_errors(limit=999)
    st.caption(f"🔁 {len(due)} logged error(s) due for review — each pass pushes the "
               "next review further out until the mistake is extinct.")
    if not due:
        st.info("Nothing due right now. Errors become due immediately after grading — "
                "submit an essay in **Practice**, then come back here.")

    if st.button("🎯 Start drill session", type="primary",
                 disabled=not due or not api_key):
        try:
            with st.spinner("Building drills from your own mistakes..."):
                items = drills.build_session(api_key, model, size=6)
            st.session_state.drill_items = items
            st.session_state.pop("drill_results", None)
        except LLMError as e:
            st.error(e)

    items = st.session_state.get("drill_items") or []
    if items and "drill_results" not in st.session_state:
        with st.form("drill_form"):
            for i, item in enumerate(items):
                st.markdown(f"**{i + 1} · `{item.get('category', '?')}`** — {item.get('rule', '')}")
                if item.get("type") == "mcq":
                    st.selectbox("Pick the best option:", item.get("options", []),
                                 key=f"drill_{i}", index=None, placeholder="Choose…")
                else:
                    st.caption(f"✏️ {item.get('sentence', '')}")
                    st.text_area("Rewrite the sentence correctly:", key=f"drill_{i}")
                st.divider()
            submitted = st.form_submit_button("Check my answers", type="primary")

        if submitted:
            results = []
            progress = st.progress(0.0, text="Checking answers...")
            for i, item in enumerate(items):
                answer = st.session_state.get(f"drill_{i}")
                if item.get("type") == "mcq":
                    options = item.get("options", [])
                    passed = bool(answer) and answer == options[item.get("answer_index", 0)]
                    results.append({
                        "item": item, "passed": passed, "user": answer or "—",
                        "feedback": item.get("explanation", ""),
                        "correct": options[item.get("answer_index", 0)] if options else "",
                    })
                    drills.record_result(item, passed, "mcq")
                else:
                    user_text = (answer or "").strip()
                    if not user_text:
                        passed, feedback = False, "No answer given."
                    else:
                        try:
                            verdict = drills.check_fix(api_key, model, item, user_text)
                            passed = verdict.get("verdict") == "pass"
                            feedback = verdict.get("feedback", "")
                        except LLMError as e:
                            passed, feedback = None, f"(auto-check unavailable: {e})"
                    results.append({
                        "item": item, "passed": passed, "user": user_text or "—",
                        "feedback": feedback, "correct": item.get("answer", ""),
                    })
                    if passed is not None:
                        drills.record_result(item, passed, "fix_sentence")
                progress.progress((i + 1) / len(items), text=f"Checked {i + 1}/{len(items)}")
            st.session_state.drill_results = results
            st.session_state.pop("drill_items", None)
            st.rerun()

    results = st.session_state.get("drill_results")
    if results:
        n_pass = sum(1 for r in results if r["passed"])
        st.metric("Session score", f"{n_pass} / {len(results)}")
        for i, r in enumerate(results):
            icon = "✅" if r["passed"] else ("⚠️" if r["passed"] is None else "❌")
            with st.container(border=True):
                st.markdown(f"{icon} **{i + 1} · `{r['item'].get('category', '?')}`**")
                st.caption(f"Rule: {r['item'].get('rule', '')}")
                st.markdown(f"**Your answer:** {r['user']}")
                if not r["passed"] and r["correct"]:
                    st.markdown(f"**Corrected:** {r['correct']}")
                if r["feedback"]:
                    st.caption(r["feedback"])
        if st.button("Clear session"):
            st.session_state.pop("drill_results", None)
            st.rerun()

# ------------------------------------------------------------------ progress

with tab_progress:
    graded = [e for e in db.list_essays(500) if e["score_overall"] is not None]
    if not graded:
        st.info("Submit your first graded essay to unlock progress tracking.")
    else:
        chronologic = list(reversed(graded))  # oldest first

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Rubric scores over time")
            score_df = pd.DataFrame([{
                "date": f"{e['created_at'][:10]} #{e['id']}",
                "Overall": e["score_overall"],
                "Development": e["score_development"],
                "Organization": e["score_organization"],
                "Language": e["score_language"],
            } for e in chronologic]).set_index("date")
            st.line_chart(score_df)

        stats = db.error_stats()
        with c2:
            st.subheader("Errors by category (all time)")
            if stats:
                st.bar_chart(
                    pd.DataFrame([{"category": s["category"], "count": s["n"]}
                                  for s in stats]).set_index("category"))
            else:
                st.caption("No logged errors yet 🎉")

        st.subheader("Lexical profile (computed locally, no LLM)")
        lex_rows = []
        for e in chronologic:
            m = json.loads(e["metrics"]) if e["metrics"] else {}
            lex_rows.append({
                "date": f"{e['created_at'][:10]} #{e['id']}",
                "avg sentence len": m.get("avg_sentence_len"),
                "sentence variety (σ)": m.get("sentence_len_std"),
                "vocab range (TTR)": m.get("type_token_ratio"),
                "long-word ratio": m.get("long_word_ratio"),
            })
        st.line_chart(pd.DataFrame(lex_rows).set_index("date"))

        dims = ["score_development", "score_organization", "score_language", "score_overall"]
        labels = ["Development", "Organization", "Language", "Overall"]
        first = chronologic[0]
        recent = chronologic[-3:]

        def _avg(rows, key):
            vals = [r[key] for r in rows if r[key] is not None]
            return sum(vals) / len(vals) if vals else 0.0

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=[first[d] or 0 for d in dims], theta=labels, fill="toself",
            name=f"First essay (#{first['id']})",
        ))
        fig.add_trace(go.Scatterpolar(
            r=[_avg(recent, d) for d in dims], theta=labels, fill="toself",
            name="Recent average (last 3)",
        ))
        fig.update_layout(
            polar={"radialaxis": {"range": [0, 5]}},
            title="First essay vs recent average",
            height=420,
        )
        c3, c4 = st.columns([3, 2])
        c3.plotly_chart(fig, width="stretch")
        drill = db.drill_stats()
        n_active = len(db.all_errors(status="active", limit=9999))
        n_resolved = len(db.all_errors(status="resolved", limit=9999))
        c4.metric("Active error patterns", n_active)
        c4.metric("Resolved 🎉", n_resolved)
        if drill["attempts"]:
            c4.metric("Drill pass rate", f"{round(100 * drill['passed'] / drill['attempts'])}%")

        st.subheader("Essay history")
        st.dataframe(
            pd.DataFrame([{
                "#": e["id"], "date": e["created_at"][:10], "task": e["task_type"],
                "words": len(e["text"].split()),
                "overall": e["score_overall"],
                "minutes": round((e["duration_seconds"] or 0) / 60, 1),
            } for e in graded]),
            width="stretch", hide_index=True,
        )

# ------------------------------------------------------------------ ledger

with tab_ledger:
    st.subheader("🧠 Learner profile")
    st.caption("Auto-rewritten after each graded essay; edit freely — the examiner "
               "reads it when designing your practice tasks.")
    profile = db.get_meta(
        "profile",
        "## Strengths\n- (not yet measured)\n\n## Weaknesses\n- (not yet measured)\n\n"
        "## Current focus\n1. Take the diagnostic essay\n\n## Notes\n",
    )
    new_profile = st.text_area("Profile (markdown)", value=profile, height=280,
                               key="profile_edit", label_visibility="collapsed")
    if st.button("Save profile"):
        db.set_meta("profile", new_profile)
        st.success("Profile saved.")

    st.divider()
    st.subheader("📒 Error ledger")
    status_filter = st.selectbox("Status", ["active", "resolved", "all"])
    errs = db.all_errors(status=None if status_filter == "all" else status_filter)
    if errs:
        df = pd.DataFrame([{
            "#": e["id"], "category": e["category"], "severity": e["severity"],
            "original": e["original"], "correction": e["correction"],
            "rule": e["rule"], "status": e["status"],
            "next review": e["next_review"], "reps": e["reps"],
        } for e in errs])
        st.dataframe(df, width="stretch", hide_index=True)

        labels_map = {e["id"]: f"#{e['id']} · {e['category']} · {(e['original'] or '')[:40]}"
                      for e in errs}
        picked = st.multiselect("Select entries to update", options=list(labels_map),
                                format_func=labels_map.get)
        col1, col2 = st.columns(2)
        if col1.button("Mark selected as resolved", disabled=not picked):
            for eid in picked:
                db.set_error_status(eid, "resolved")
            st.rerun()
        if col2.button("Reactivate selected", disabled=not picked):
            for eid in picked:
                db.set_error_status(eid, "active")
            st.rerun()
    else:
        st.caption("No errors logged yet — they appear here after your first graded essay.")

    st.subheader("🔁 Overused words across all essays")
    overused = Counter()
    suggestions = {}
    for e in db.list_essays(500):
        try:
            for w in json.loads(e["overused_json"] or "[]"):
                word = (w.get("word") or "").lower()
                if word:
                    overused[word] += int(w.get("count", 1))
                    if w.get("suggestions"):
                        suggestions[word] = w["suggestions"]
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    if overused:
        st.dataframe(
            pd.DataFrame([{
                "word": w, "total uses": n,
                "try instead": ", ".join(suggestions.get(w, [])[:3]),
            } for w, n in overused.most_common()]),
            width="stretch", hide_index=True,
        )
    else:
        st.caption("No overused-word data yet.")
