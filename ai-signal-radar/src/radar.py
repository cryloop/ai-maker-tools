from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Optional

import feedparser
import requests
from dateutil import tz
from dateutil import parser as dateparser

HF_BLOG_RSS = "https://huggingface.co/blog/feed.xml"
ARXIV_CSAI_RSS = "https://export.arxiv.org/rss/cs.AI"
LOCAL_LLAMMA_RSS = "https://www.reddit.com/r/LocalLLaMA/.rss"
MACHINE_LEARNING_RSS = "https://www.reddit.com/r/MachineLearning/.rss"
HN_ALGOLIA_LLM = "https://hn.algolia.com/api/v1/search?query=llm&tags=story&hitsPerPage=30"

USER_AGENT = "ai-signal-radar/0.1 (+https://github.com/openclaw/openclaw)"

# Default keyword filters for AI/LLM signals
DEFAULT_KEYWORDS = ["llm", "gpt", "model", "ai", "transformer", "clip", "embedding", "rag", "fine-tun", "agent", "eval", "benchmark"]


def _matches_keywords(title: str, keywords: list[str]) -> bool:
    """Check if title matches any keyword (case-insensitive)."""
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in keywords)


def filter_by_keywords(items: list, keywords: list, include_all: bool = False):
    """Filter items by keywords. If include_all=True, keep items even if no match (for broad discovery)."""
    if not keywords:
        return items
    filtered = [it for it in items if _matches_keywords(it.title, keywords)]
    if include_all:
        # Keep all items but prioritize matches
        return filtered + [it for it in items if it not in filtered]
    return filtered


@dataclass
class Item:
    source: str
    title: str
    url: str
    published: Optional[str] = None
    score: Optional[int] = None


def _clean(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s


def fetch_rss(url: str, source: str, limit: int, timeout: int = 20) -> list[Item]:
    # feedparser can fetch itself, but we want to set UA consistently.
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    r.raise_for_status()
    feed = feedparser.parse(r.text)
    out: list[Item] = []
    for e in feed.entries[:limit]:
        title = _clean(getattr(e, "title", ""))
        link = getattr(e, "link", "") or ""
        published = getattr(e, "published", None) or getattr(e, "updated", None)
        if title and link:
            out.append(Item(source=source, title=title, url=link, published=published))
    return out


def fetch_hn_algolia(url: str, limit: int, timeout: int = 20) -> list[Item]:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    hits = data.get("hits", [])
    out: list[Item] = []
    for h in hits:
        title = _clean(h.get("title") or "")
        link = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        points = h.get("points")
        created_at = h.get("created_at")
        if title and link:
            out.append(Item(source="Hacker News (Algolia: llm)", title=title, url=link, published=created_at, score=points))
    # Prefer higher points if present, otherwise keep order.
    out.sort(key=lambda x: (x.score is None, -(x.score or 0)))
    return out[:limit]


def now_utc_date() -> dt.date:
    return dt.datetime.now(tz=tz.UTC).date()


def render_md(day: dt.date, groups: list, format_mode: str = "markdown") -> str:
    if format_mode == "discord":
        return render_discord(day, groups)
    elif format_mode == "slack":
        return render_slack(day, groups)
    # Default: markdown
    lines: list = []
    lines.append(f"# AI Signal Radar — {day.isoformat()}")
    lines.append("")
    lines.append("Sources: Hugging Face blog, arXiv cs.AI RSS, r/LocalLLaMA RSS, r/MachineLearning RSS, HN Algolia query.")
    lines.append("")

    for (group, items) in groups:
        lines.append(f"## {group}")
        if not items:
            lines.append("- (no items fetched)")
            lines.append("")
            continue
        for it in items:
            meta = []
            if it.score is not None:
                meta.append(f"{it.score} points")
            if it.published:
                try:
                    meta.append(dateparser.parse(str(it.published)).date().isoformat())
                except Exception:  # noqa: BLE001
                    meta.append(_clean(str(it.published))[:32])
            meta_s = f" ({', '.join(meta)})" if meta else ""
            lines.append(f"- [{it.title}]({it.url}){meta_s}")
        lines.append("")

    lines.append("## 3 quick follow-ups (auto-generated heuristics)")
    lines.append("- Skim HF blog post titles for tooling you can *ship* this week (agents, evals, runtimes).")
    lines.append("- Pull 1 arXiv paper that suggests a measurable technique; write a minimal reproduction script.")
    lines.append("- From r/LocalLLaMA + HN: identify 1 recurring pain point; build a tiny CLI to reduce it.")
    lines.append("")
    return "\n".join(lines)


def render_discord(day: dt.date, groups: list) -> str:
    """Render a compact Discord-friendly format."""
    lines: list = []
    lines.append(f"**📡 AI Signal Radar — {day.isoformat()}**")
    lines.append("")

    for (group, items) in groups:
        if not items:
            continue
        lines.append(f"**{group}**")
        for it in items[:5]:  # Limit to top 5 per source for Discord
            meta = []
            if it.score is not None:
                meta.append(f"⬆{it.score}")
            if it.published:
                try:
                    meta.append(dateparser.parse(str(it.published)).date().isoformat()[-5:])
                except Exception:  # noqa: BLE001
                    pass
            meta_s = f" {', '.join(meta)}" if meta else ""
            # Truncate long titles
            title = it.title[:80] + "..." if len(it.title) > 80 else it.title
            lines.append(f"• {title}{meta_s}")
        lines.append("")
    return "\n".join(lines)


def render_slack(day: dt.date, groups: list) -> str:
    """Render a Slack-friendly format with emojis."""
    lines: list = []
    lines.append(f"📡 *AI Signal Radar — {day.isoformat()}*")
    lines.append("")

    for (group, items) in groups:
        if not items:
            continue
        lines.append(f"*{group}*")
        for it in items[:5]:
            meta = []
            if it.score is not None:
                meta.append(f"⬆{it.score}")
            meta_s = f" ({', '.join(meta)})" if meta else ""
            title = it.title[:80] + "..." if len(it.title) > 80 else it.title
            lines.append(f"• <{it.url}|{title}>{meta_s}")
        lines.append("")
    return "\n".join(lines)


def write_digest(out_dir: str, day: dt.date, md: str, fmt: str = "markdown") -> str:
    os.makedirs(out_dir, exist_ok=True)
    ext = ".txt" if fmt in ("discord", "slack") else ".md"
    path = os.path.join(out_dir, f"{day.isoformat()}{ext}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Generate a small daily AI/LLM signal digest.")
    ap.add_argument("--limit", type=int, default=8, help="items per source")
    ap.add_argument("--out", type=str, default=os.path.join(os.path.dirname(__file__), "..", "out"), help="output directory")
    ap.add_argument("--json", dest="write_json", action="store_true", help="also write a JSON dump")
    ap.add_argument("--format", type=str, choices=["markdown", "discord", "slack"], default="markdown", help="output format")
    ap.add_argument("--since", type=str, help="only include items published after this date (YYYY-MM-DD)")
    ap.add_argument("--keywords", type=str, help="comma-separated keywords to filter (default: built-in AI/LLM keywords)")
    ap.add_argument("--include-all", action="store_true", help="include all items but prioritize keyword matches")
    args = ap.parse_args(argv)

    # Parse keywords
    keywords = DEFAULT_KEYWORDS
    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]

    # Parse since date
    since_date: Optional[dt.date] = None
    if args.since:
        since_date = dt.date.fromisoformat(args.since)

    day = now_utc_date()

    groups: list = []
    groups.append(("Hugging Face — Blog", fetch_rss(HF_BLOG_RSS, "Hugging Face — Blog", args.limit)))

    # arXiv rss export sometimes has no entries on weekends (skipDays).
    groups.append(("arXiv — cs.AI", fetch_rss(ARXIV_CSAI_RSS, "arXiv — cs.AI", args.limit)))

    # Reddit RSS is rate-limited occasionally.
    try:
        groups.append(("Reddit — r/LocalLLaMA", fetch_rss(LOCAL_LLAMMA_RSS, "Reddit — r/LocalLLaMA", args.limit)))
    except Exception as e:  # noqa: BLE001
        groups.append(("Reddit — r/LocalLLaMA", [Item(source="Reddit — r/LocalLLaMA", title=f"(fetch failed: {type(e).__name__}: {e})", url=LOCAL_LLAMMA_RSS)]))

    # Added r/MachineLearning RSS
    try:
        groups.append(("Reddit — r/MachineLearning", fetch_rss(MACHINE_LEARNING_RSS, "Reddit — r/MachineLearning", args.limit)))
    except Exception as e:  # noqa: BLE001
        groups.append(("Reddit — r/MachineLearning", [Item(source="Reddit — r/MachineLearning", title=f"(fetch failed: {type(e).__name__}: {e})", url=MACHINE_LEARNING_RSS)]))

    groups.append(("Hacker News", fetch_hn_algolia(HN_ALGOLIA_LLM, args.limit)))

    # Apply keyword filtering
    filtered_groups: list = []
    for name, items in groups:
        filtered = filter_by_keywords(items, keywords, args.include_all)
        # Apply date filter
        if since_date:
            date_filtered = []
            for it in filtered:
                if it.published:
                    try:
                        item_date = dateparser.parse(str(it.published)).date()
                        if item_date >= since_date:
                            date_filtered.append(it)
                    except Exception:
                        date_filtered.append(it)  # Keep if we can't parse
                else:
                    date_filtered.append(it)  # Keep if no date
            filtered_groups.append((name, date_filtered))
        else:
            filtered_groups.append((name, filtered))

    # Render in requested format
    md = render_md(day, filtered_groups, args.format)
    
    # Write output
    out_path = write_digest(os.path.abspath(args.out), day, md, args.format)

    if args.write_json:
        dump = {
            "date": day.isoformat(),
            "format": args.format,
            "keywords": keywords,
            "since": args.since,
            "groups": [
                {
                    "name": name,
                    "items": [
                        {
                            "source": it.source,
                            "title": it.title,
                            "url": it.url,
                            "published": it.published,
                            "score": it.score,
                        }
                        for it in items
                    ],
                }
                for (name, items) in filtered_groups
            ],
        }
        json_path = os.path.splitext(out_path)[0] + ".json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(dump, f, indent=2)

    # Print to stdout for piping
    print(md)
    print(f"\n[Written to: {out_path}]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
