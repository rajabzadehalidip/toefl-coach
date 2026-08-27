"""ETS TOEFL iBT writing rubrics (condensed but faithful), 0-5 scale.

The grader prompt quotes these so scores track the real test instead of
generic "AI feedback" drift.
"""

ACADEMIC_DISCUSSION_RUBRIC = """\
Score 5 — The response is a relevant and clearly developed contribution to the
online discussion. It consistently uses a range of precise vocabulary and
syntactic variety; sentence structure and word choice are effective. Errors
are rare and minor (typos or slips), never obscuring meaning. The writer's
position is clear from the start and engages meaningfully with the discussion.

Score 4 — The response is mostly relevant and well developed. Language is
generally effective with some variety; there may be occasional imprecision or
a few noticeable errors, but meaning is always clear. Position is clear;
connection to the discussion is evident.

Score 3 — The response is mostly relevant but development is limited: ideas
may be vague, repetitive, or only partially elaborated. Vocabulary and
sentence structures are functional but uneven in range. Errors are noticeable
and sometimes slow understanding, though the main ideas remain clear.

Score 2 — The response is only partially relevant and incompletely developed;
it may lean on generalities or repeat the given posts. Vocabulary is limited,
sentence structures mostly simple; frequent errors cause real strain for the
reader.

Score 1 — Little relevant content; very limited development, vocabulary, and
control of grammar. Errors obscure meaning.

Score 0 — Blank, off-topic, written in another language, or merely copies the
given material."""

INTEGRATED_RUBRIC = """\
Score 5 — The response selects the important information from the lecture and
relates it accurately to the relevant reading information. It is clearly
organized, and language use is accurate and effective, with only minor slips.

Score 4 — The response is good in selecting and connecting the lecture's key
points to the reading, though it may contain slight imprecision or omit one
minor point. Mostly well organized; good control of language with a few
noticeable errors that never obscure meaning.

Score 3 — The response includes some relevant information from the lecture and
reading but is vague or omits a key point; connections between sources may be
only partially clear. Occasional lapses in clarity; a fair range of language
with errors that sometimes impede understanding.

Score 2 — The response misses or misrepresents key ideas from the lecture
and/or reading; connections are limited or inaccurate. Vocabulary and
structures are basic; frequent errors place a heavy burden on the reader.

Score 1 — Little or no relevant or accurate information from either source;
very limited language control. Errors obscure meaning.

Score 0 — Blank, off-topic, copies the sources only, or is in another
language."""

RUBRICS = {
    "academic_discussion": ACADEMIC_DISCUSSION_RUBRIC,
    "integrated": INTEGRATED_RUBRIC,
    # Custom prompts are graded with the discussion rubric as the closest
    # general-purpose academic writing standard.
    "custom": ACADEMIC_DISCUSSION_RUBRIC,
}


def rubric_text(task_type: str) -> str:
    return RUBRICS.get(task_type, ACADEMIC_DISCUSSION_RUBRIC)
