# AI Signal Radar

Tiny CLI that pulls AI/LLM signals from public feeds and writes a dated digest in markdown, Discord, or Slack format.

## Why
Local "what should I look at today?" feed consolidator for the maker loop. No API keys needed.

## Install
```bash
cd /home/ubuntu/.openclaw/workspace/maker/projects/ai-signal-radar
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run
```bash
source .venv/bin/activate

# Default markdown output
python -m src.radar --limit 8

# Discord-friendly format (compact, emojis)
python -m src.radar --format discord --limit 5

# Slack format
python -m src.radar --format slack --limit 5

# Filter by keywords (custom comma-separated)
python -m src.radar --keywords "gpt,agent,rag" --include-all

# Only items since a date
python -m src.radar --since 2026-02-01

# Also write JSON dump
python -m src.radar --json
```

Output: `out/YYYY-MM-DD.md` (or `.txt` for discord/slack formats)

## Features
- **Sources**: Hugging Face blog, arXiv cs.AI RSS, r/LocalLLaMA RSS, r/MachineLearning RSS, Hacker News (Algolia)
- **Formats**: markdown (default), Discord (compact), Slack (with links)
- **Filtering**: Keywords (built-in AI/LLM defaults or custom), date filtering (`--since`)
- **Output**: Markdown, JSON dump, stdout for piping

## Notes
- Reddit RSS can rate-limit; lower `--limit` if issues.
- arXiv sometimes has sparse entries on weekends.
