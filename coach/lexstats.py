"""Deterministic lexical metrics — no LLM, computed locally for every essay.

These give objective, chartable signals (sentence variety, lexical range,
vague-word reliance) that complement the rubric scores.
"""

import re
from statistics import pstdev
from typing import Dict

# Words that flag vague, informal, or over-relied-on vocabulary in essays.
VAGUE = [
    "very", "really", "so", "a lot", "a lot of", "lots of",
    "good", "bad", "big", "small", "thing", "things", "stuff",
    "important", "interesting", "nice", "nowadays",
    "in my opinion", "i think", "as we all know",
]

_WORD_RE = re.compile(r"[A-Za-z'’]+")


def analyze(text: str) -> Dict:
    """Compute lexical statistics for an essay."""
    lowered = text.lower()
    words = _WORD_RE.findall(lowered)
    sentences = [s for s in re.split(r"[.!?]+(?:\s|$)", text) if s.strip()]
    sent_lens = [len(_WORD_RE.findall(s.lower())) for s in sentences]
    n = len(words)
    vague = {v: lowered.count(v) for v in VAGUE if lowered.count(v)}
    # "a lot of" also contains "a lot" — don't double count.
    if "a lot of" in vague and "a lot" in vague:
        vague["a lot"] -= vague["a lot of"]
        if vague["a lot"] <= 0:
            del vague["a lot"]
    return {
        "words": n,
        "sentences": len(sentences),
        "avg_sentence_len": round(n / len(sentences), 1) if sentences else 0,
        "sentence_len_std": round(pstdev(sent_lens), 1) if len(sent_lens) > 1 else 0.0,
        "type_token_ratio": round(len(set(words)) / n, 3) if n else 0.0,
        "long_word_ratio": round(sum(1 for w in words if len(w) >= 7) / n, 3) if n else 0.0,
        "vague_counts": vague,
    }


def format_metrics(m: Dict) -> str:
    """One-line human-readable summary of the metrics."""
    vague = ", ".join(f"{w}×{c}" for w, c in sorted(m.get("vague_counts", {}).items(), key=lambda kv: -kv[1]))
    return (
        f"{m['words']} words · {m['sentences']} sentences · "
        f"avg {m['avg_sentence_len']} words/sentence · variety σ {m['sentence_len_std']} · "
        f"TTR {m['type_token_ratio']} · long-word ratio {m['long_word_ratio']}"
        + (f" · vague: {vague}" if vague else "")
    )
