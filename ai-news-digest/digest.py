#!/usr/bin/env python3
"""ai-news-digest

Fetch a few RSS feeds and render a small markdown digest.

Why: quick, local “what’s up” + idea generator for maker loops.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
from dataclasses import dataclass
from typing import Iterable

import feedparser
import requests


@dataclass
class Source:
    name: str
    url: str
    limit: int = 8


SOURCES: list[Source] = [
    Source("Hugging Face Blog", "https://huggingface.co/blog/feed.xml", limit=8),
    Source("arXiv cs.AI", "https://export.arxiv.org/rss/cs.AI", limit=12),
    Source("Hacker News Frontpage", "https://hnrss.org/frontpage", limit=12),
]


def _clean(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s


def fetch_feed(url: str, timeout: int = 20) -> feedparser.FeedParserDict:
    # requests first so we can set UA + timeouts consistently.
    r = requests.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": "ai-news-digest/0.1 (+https://github.com/openclaw/openclaw)"
        },
    )
    r.raise_for_status()
    return feedparser.parse(r.text)


def pick_items(parsed: feedparser.FeedParserDict, limit: int) -> list[dict]:
    items = []
    for entry in (parsed.entries or [])[:limit]:
        title = _clean(getattr(entry, "title", ""))
        link = _clean(getattr(entry, "link", ""))
        published = _clean(getattr(entry, "published", ""))
        items.append({"title": title, "link": link, "published": published})
    return items


def render_markdown(sections: list[tuple[str, list[dict]]]) -> str:
    now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    lines: list[str] = []
    lines.append(f"# AI News Digest ({now})")
    lines.append("")

    for name, items in sections:
        lines.append(f"## {name}")
        if not items:
            lines.append("- (no items parsed)")
            lines.append("")
            continue
        for it in items:
            pub = f" — {it['published']}" if it.get("published") else ""
            lines.append(f"- [{it['title']}]({it['link']}){pub}")
        lines.append("")

    # Simple heuristics to propose build ideas
    lines.append("## 3 build ideas (actionable)")
    lines.append("1. **Local eval harness for tool-using agents**: wrap a few common tasks (web snapshot, file edit, shell cmd) and score success/failure; store JSONL results.")
    lines.append("2. **RSS→Discord ‘no-spam’ notifier**: track seen GUIDs, only post when keyword match + threshold (e.g., ‘agents’, ‘kernels’, ‘eval’).")
    lines.append("3. **Paper-to-code starter**: given an arXiv link, auto-create a project folder with README, citation, and TODO checklist (repro, datasets, baselines).")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="digest.md", help="Output markdown path")
    args = ap.parse_args()

    sections: list[tuple[str, list[dict]]] = []
    for src in SOURCES:
        try:
            parsed = fetch_feed(src.url)
            items = pick_items(parsed, src.limit)
        except Exception as e:  # noqa: BLE001
            items = []
            sections.append((f"{src.name} (error: {e.__class__.__name__})", items))
            continue
        sections.append((src.name, items))

    md = render_markdown(sections)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"Wrote {args.out} ({len(md)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
