# ai-news-digest

Tiny CLI that pulls a few AI-ish RSS feeds (Hugging Face blog, arXiv cs.AI, Hacker News frontpage) and emits a markdown digest + 3 build ideas.

## Setup

```bash
cd maker/projects/ai-news-digest
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
source .venv/bin/activate
python digest.py --out digest.md
cat digest.md
```

## Notes
- Feeds are public RSS; no keys.
- If you want different sources, edit `SOURCES` in `digest.py`.
