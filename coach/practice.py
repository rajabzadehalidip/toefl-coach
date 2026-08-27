"""Practice-task generation (weakness-aware) and formatting for display."""

from __future__ import annotations

from typing import Dict

from . import prompts
from .llm import chat_json

# Official timing per task type, in minutes (custom is a relaxed default).
TASK_DURATIONS = {"academic_discussion": 10, "integrated": 20, "custom": 25}

TASK_LABELS = {
    "academic_discussion": "Academic Discussion (10 min)",
    "integrated": "Integrated: Reading + Lecture (20 min)",
    "custom": "Custom prompt (untimed-ish)",
}


def generate_task(api_key: str, model: str, task_type: str,
                  weakness_summary: str = "") -> Dict:
    """Ask the examiner agent for a fresh TOEFL-style task.

    If a weakness summary is supplied (top error categories + learner profile),
    the task is quietly engineered to exercise those weak spots.
    """
    system = (
        prompts.EXAMINER_INTEGRATED
        if task_type == "integrated"
        else prompts.EXAMINER_ACADEMIC
    )

    context = (
        prompts.WEAKNESS_CONTEXT.format(summary=weakness_summary)
        if weakness_summary.strip()
        else "\n\nNo learner history yet — pick a common, accessible academic topic."
    )
    task = chat_json(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": "Generate one task." + context},
        ],
        api_key,
        model,
        temperature=0.9,
    )
    task["_type"] = task_type
    return task


def format_task(task: Dict) -> str:
    """Render a task dict as markdown for the practice screen."""
    kind = task.get("_type")

    if kind == "custom":
        return task.get("prompt_text", "Free writing: pick any topic.")

    if kind == "integrated":
        return (
            f"### 📖 {task.get('title', 'Integrated task')}\n\n"
            f"**READING — {task.get('reading_title', '')}**\n\n"
            f"{task.get('reading_passage', '')}\n\n"
            "---\n\n"
            f"**🎧 LECTURE (transcript)**\n\n"
            f"{task.get('lecture_transcript', '')}\n\n"
            f"*{task.get('instructions', '')}*"
        )

    # academic discussion
    return (
        f"### 💬 {task.get('title', 'Discussion')} — {task.get('course', '')}\n\n"
        f"👩‍🏫 **{task.get('professor', 'Professor')}:** {task.get('professor_question', '')}\n\n"
        f"🧑 **{task.get('student1', 'Student 1')}:** {task.get('student1_post', '')}\n\n"
        f"👩 **{task.get('student2', 'Student 2')}:** {task.get('student2_post', '')}\n\n"
        f"*{task.get('instructions', '')}*"
    )
