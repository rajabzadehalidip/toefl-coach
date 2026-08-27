#!/bin/zsh
# Launch the TOEFL Writing Coach — no path or venv knowledge required.
# Usage:  ./run.sh          (or:  /Users/al/.zcode/workspace/default/toefl-coach/run.sh)

cd "$(dirname "$0")" || exit 1

# Optional: put OPENROUTER_API_KEY=sk-or-... in a .env file next to this script.
[ -f .env ] && source .env

# Run with the project's own Python — no conda/venv activation needed.
exec .venv/bin/streamlit run app.py
