from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path

from .classifier import extract_urls
from .models import ResearchDraft


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    lowered = normalized.lower().replace("'", "").replace("`", "")
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return (slug[:70].strip("-") or "submission")


def telegram_source(timestamp: datetime) -> str:
    return f"telegram://submission/{timestamp.strftime('%Y%m%d%H%M%S')}"


def note_draft(text: str, timestamp: datetime) -> ResearchDraft:
    urls = extract_urls(text)
    source_urls = urls or [telegram_source(timestamp)]
    title = _title_from_text(text) or "Telegram Note"
    information = "\n".join(
        [
            "Submitted via Telegram as a personal note.",
            "",
            text.strip(),
        ]
    )
    return ResearchDraft(title=title, information=information.strip(), sources=source_urls)


def failure_draft(title: str, submitted: str, reason: str, sources: list[str]) -> ResearchDraft:
    clean_sources = sources or ["telegram://submission/failed"]
    information = "\n".join(
        [
            "Researcher could not extract or research useful content from the submitted item.",
            "",
            f"Submitted item: {submitted.strip()}",
            "",
            f"Reason: {reason}",
        ]
    )
    return ResearchDraft(
        title=f"Failed Extraction: {title}",
        information=information,
        sources=clean_sources,
        success=False,
        error=reason,
    )


def write_input_markdown(input_dir: Path, draft: ResearchDraft, timestamp: datetime) -> Path:
    input_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{timestamp:%Y-%m-%d-%H%M%S}-{slugify(draft.title)}.md"
    path = input_dir / filename
    path.write_text(render_markdown(draft), encoding="utf-8")
    return path


def render_markdown(draft: ResearchDraft) -> str:
    sources = draft.sources or ["telegram://submission/missing-source"]
    lines = [
        f"# {draft.title.strip() or 'Untitled'}",
        "",
        "## Information",
        "",
        draft.information.strip() or "No information was extracted.",
        "",
        "## Sources",
        "",
    ]
    lines.extend(f"- {source}" for source in list(dict.fromkeys(sources)))
    return "\n".join(lines).rstrip() + "\n"


def _title_from_text(text: str) -> str:
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if not first_line:
        return ""
    title = re.sub(r"\s+", " ", first_line)
    return title[:80].rstrip(" .,:;")

