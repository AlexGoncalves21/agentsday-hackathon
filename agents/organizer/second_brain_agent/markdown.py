from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Iterable, List

from .models import InputDocument

URL_RE = re.compile(r"(?:https?|telegram)://[^\s)>]+")


class InputParseError(ValueError):
    """Raised when an input Markdown file does not match the researcher contract."""


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    lowered = normalized.lower().replace("'", "").replace("`", "")
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "untitled"


def parse_input_document(path: Path) -> InputDocument:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("# "):
        raise InputParseError(f"{path} must start with '# Title'")

    title = lines[0][2:].strip()
    try:
        info_idx = lines.index("## Information")
        sources_idx = lines.index("## Sources")
    except ValueError as exc:
        raise InputParseError(f"{path} must contain '## Information' and '## Sources'") from exc

    if info_idx >= sources_idx:
        raise InputParseError(f"{path} has '## Sources' before '## Information'")

    information = "\n".join(lines[info_idx + 1 : sources_idx]).strip()
    sources_text = "\n".join(lines[sources_idx + 1 :]).strip()
    sources = extract_urls(sources_text)

    if not title:
        raise InputParseError(f"{path} has an empty title")
    if not information:
        raise InputParseError(f"{path} has an empty information section")
    if not sources:
        raise InputParseError(f"{path} must include at least one source URL")

    return InputDocument(
        path=path,
        title=title,
        information=information,
        sources=sources,
        slug=slugify(title),
    )


def extract_urls(text: str) -> List[str]:
    urls = []
    for match in URL_RE.findall(text):
        urls.append(match.rstrip(".,;"))
    return list(dict.fromkeys(urls))


def markdown_list(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def relative_markdown_link(from_file: Path, to_file: Path, label: str) -> str:
    rel = Path(os_relpath(to_file, start=from_file.parent)).as_posix()
    return f"[{label}]({rel})"


def os_relpath(path: Path, start: Path) -> str:
    import os

    return os.path.relpath(path, start=start)
