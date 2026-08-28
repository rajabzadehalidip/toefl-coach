"""Design system for the TOEFL Writing Coach.

Tokens come from the generated design system: study purple (#7C3AED) with a
success green (#059669), soft lavender surfaces, Lora for headings (scholarly)
and Raleway for body text. All UI polish lives here so app.py stays logic-only.
"""

from __future__ import annotations

from typing import Dict, Optional

import streamlit as st

PRIMARY = "#7C3AED"
PRIMARY_SOFT = "#EDE9FE"
ACCENT = "#059669"
BG = "#FAF5FF"
SURFACE = "#FFFFFF"
BORDER = "#EFE7FC"
TEXT = "#0F172A"
MUTED = "#64748B"
AMBER = "#D97706"
RED = "#DC2626"

_CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Lora:wght@500;600;700&family=Raleway:wght@400;500;600;700&display=swap');

:root {{
  --tfc-primary: {PRIMARY};
  --tfc-primary-soft: {PRIMARY_SOFT};
  --tfc-accent: {ACCENT};
  --tfc-surface: {SURFACE};
  --tfc-border: {BORDER};
  --tfc-text: {TEXT};
  --tfc-muted: {MUTED};
}}

/* ---- typography ---- */
html, body, .stApp, button, input, textarea, [data-testid="stMarkdownContainer"] {{
  font-family: 'Raleway', 'Source Sans Pro', sans-serif;
  color: var(--tfc-text);
}}
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMetricValue"] {{
  font-family: 'Lora', Georgia, serif;
  letter-spacing: -0.01em;
}}
[data-testid="stMarkdownContainer"] h1 {{ font-size: 1.85rem; }}
[data-testid="stMarkdownContainer"] h2 {{ font-size: 1.3rem; margin-top: 1.2rem; }}
[data-testid="stMarkdownContainer"] h3 {{ font-size: 1.05rem; }}
[data-testid="stMarkdownContainer"] p {{ line-height: 1.55; }}

/* ---- metric cards ---- */
[data-testid="stMetric"] {{
  background: var(--tfc-surface);
  border: 1px solid var(--tfc-border);
  border-radius: 14px;
  padding: 12px 16px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}}
[data-testid="stMetricValue"] {{ font-size: 1.6rem; }}
[data-testid="stMetricLabel"] p {{
  color: var(--tfc-muted); font-weight: 600; font-size: 0.78rem;
  text-transform: uppercase; letter-spacing: 0.06em;
}}

/* ---- buttons ---- */
.stButton > button {{
  border-radius: 12px;
  font-weight: 600;
  border: 1px solid var(--tfc-border);
  transition: transform 0.12s ease, box-shadow 0.15s ease, filter 0.15s ease;
}}
.stButton > button[kind="primary"], .stForm button[kind="primary"] {{
  background: linear-gradient(180deg, #8B5CF6, var(--tfc-primary));
  border: none; color: #fff;
  box-shadow: 0 2px 8px rgba(124, 58, 237, 0.28);
}}
.stButton > button:hover, .stForm button:hover {{
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(124, 58, 237, 0.20);
}}
.stButton > button[kind="secondary"]:hover, .stForm button[kind="secondary"]:hover {{
  border-color: var(--tfc-primary);
}}

/* ---- tabs ---- */
[data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 1px solid var(--tfc-border); }}
[data-baseweb="tab"] {{
  font-size: 0.95rem; font-weight: 600; color: var(--tfc-muted); padding: 10px 16px;
}}
[data-baseweb="tab"][aria-selected="true"] {{ color: var(--tfc-primary); }}
[data-baseweb="tab-highlight"] {{
  background: var(--tfc-primary); height: 3px; border-radius: 3px 3px 0 0;
}}

/* ---- surfaces ---- */
[data-testid="stExpander"] {{
  border: 1px solid var(--tfc-border); border-radius: 14px;
  background: var(--tfc-surface);
}}
[data-testid="stExpander"] details {{ border: none; }}
[data-testid="stAlert"] {{ border-radius: 12px; border: 1px solid var(--tfc-border); }}
[data-testid="stDataFrame"] {{
  border: 1px solid var(--tfc-border); border-radius: 12px; overflow: hidden;
}}
div[data-testid="stVerticalBlockBorderWrapper"] {{
  border-radius: 14px !important; border-color: var(--tfc-border) !important;
}}
[data-testid="stSidebar"] > div {{ background: #F5F0FE; }}
[data-testid="stSidebar"] * {{ color: {TEXT}; }}
hr {{ border-color: var(--tfc-border); }}
[data-testid="stCaptionContainer"] p {{ color: var(--tfc-muted); }}
[data-testid="stMarkdownContainer"] a {{ color: var(--tfc-primary); font-weight: 600; }}

/* ---- score cards (feedback) ---- */
.tfc-score-row {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 4px 0 10px; }}
.tfc-card {{
  flex: 1 1 150px; min-width: 140px;
  background: var(--tfc-surface); border: 1px solid var(--tfc-border);
  border-radius: 14px; padding: 14px 16px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}}
.tfc-card-overall {{
  background: var(--tfc-primary-soft); border-color: #DDD3F8;
}}
.tfc-label {{
  font-size: 0.74rem; font-weight: 700; color: var(--tfc-muted);
  text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 4px;
}}
.tfc-value {{ font-family: 'Lora', Georgia, serif; font-size: 2.1rem; line-height: 1.1; }}
.tfc-value span {{ font-size: 0.95rem; color: var(--tfc-muted); margin-left: 4px; }}
.tfc-pillrow {{ min-height: 22px; margin-top: 6px; }}
.tfc-pill {{
  display: inline-block; font-size: 0.75rem; font-weight: 700;
  border-radius: 999px; padding: 2px 10px;
}}
.tfc-pill-up {{ background: #ECFDF5; color: {ACCENT}; }}
.tfc-pill-down {{ background: #FEF2F2; color: {RED}; }}
.tfc-pill-neutral {{ background: #F1F5F9; color: var(--tfc-muted); }}

@media (prefers-reduced-motion: reduce) {{
  * {{ transition: none !important; animation: none !important; }}
}}
"""


def inject_css() -> None:
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


def brand_block(version: str) -> str:
    """Sidebar brand header."""
    return (
        '<div style="margin-bottom: 6px;">'
        '<div style="font-family: Lora, Georgia, serif; font-weight: 700; '
        f'font-size: 1.15rem; color: {TEXT};">TOEFL Writing Coach</div>'
        '<div style="font-size: 0.78rem; '
        f'color: {MUTED};">Personal AI writing tutor &middot; v{version}</div>'
        "</div>"
    )


def score_band(v: float) -> str:
    """Semantic color for a 0-5 rubric score."""
    if v >= 4:
        return ACCENT
    if v >= 3:
        return AMBER
    return RED


def score_cards(scores: Dict[str, float], prev: Optional[float] = None) -> str:
    """Four score tiles (Overall + the three rubric dimensions) as HTML."""
    items = [("Overall", "overall"), ("Development", "development"),
             ("Organization", "organization"), ("Language use", "language")]
    tiles = []
    for label, key in items:
        v = float(scores.get(key, 0))
        if key == "overall":
            if prev is None:
                pill = '<span class="tfc-pill tfc-pill-neutral">first essay</span>'
            else:
                d = round(v - prev, 1)
                if d > 0:
                    pill = f'<span class="tfc-pill tfc-pill-up">&#9650; {d:.1f} vs previous</span>'
                elif d < 0:
                    pill = f'<span class="tfc-pill tfc-pill-down">&#9660; {abs(d):.1f} vs previous</span>'
                else:
                    pill = '<span class="tfc-pill tfc-pill-neutral">no change</span>'
        else:
            pill = ""
        tiles.append(
            f'<div class="tfc-card{" tfc-card-overall" if key == "overall" else ""}">'
            f'<div class="tfc-label">{label}</div>'
            f'<div class="tfc-value" style="color:{score_band(v)}">{v:.1f}<span>/ 5</span></div>'
            f'<div class="tfc-pillrow">{pill}</div></div>'
        )
    return f'<div class="tfc-score-row">{"".join(tiles)}</div>'
