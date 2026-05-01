from __future__ import annotations

import re

from .models import Classification


URL_RE = re.compile(r"https?://[^\s<>)\]]+")
X_STATUS_RE = re.compile(
    r"https?://(?:www\.)?(?:x|twitter)\.com/[^/\s]+/status(?:es)?/(\d+)",
    re.IGNORECASE,
)


def extract_urls(text: str) -> list[str]:
    urls = [match.rstrip(".,;") for match in URL_RE.findall(text)]
    return list(dict.fromkeys(urls))


def classify_submission(text: str) -> Classification:
    stripped = text.strip()
    urls = extract_urls(stripped)
    x_url = next((url for url in urls if X_STATUS_RE.search(url)), None)
    x_match = X_STATUS_RE.search(x_url) if x_url else None
    if x_match:
        return Classification("x_url", urls=urls, primary_url=x_url, x_status_id=x_match.group(1))

    if urls:
        return Classification("web_url", urls=urls, primary_url=urls[0])

    if stripped.endswith("?"):
        return Classification("question")

    words = stripped.split()
    if 1 <= len(words) <= 6 and _looks_like_topic(stripped):
        return Classification("topic_or_concept")

    return Classification("note")


def _looks_like_topic(value: str) -> bool:
    if value[:1].isupper():
        return True
    lowered = value.lower()
    topic_markers = {
        "ai",
        "ml",
        "llm",
        "agent",
        "agents",
        "research",
        "theory",
        "framework",
        "frameworks",
        "pattern",
        "patterns",
    }
    return any(word.strip(".,;:") in topic_markers for word in lowered.split())
