from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List

from .models import BrainPage, InputDocument, QualityCheck


def evaluate_brain(
    brain_dir: Path,
    input_docs: Iterable[InputDocument],
    pages_by_slug: Dict[str, BrainPage],
) -> List[QualityCheck]:
    docs = list(input_docs)
    checks = [
        _check_all_inputs_represented(docs, pages_by_slug),
        _check_source_pages_exist(brain_dir, docs),
        _check_source_urls_preserved(brain_dir, docs),
        _check_core_files(brain_dir),
        _check_index_links(brain_dir, pages_by_slug.values(), docs),
    ]
    return checks


def _check_all_inputs_represented(
    docs: List[InputDocument],
    pages_by_slug: Dict[str, BrainPage],
) -> QualityCheck:
    represented_input_paths = {page.source_doc.path.resolve() for page in pages_by_slug.values()}
    missing = [doc.title for doc in docs if doc.path.resolve() not in represented_input_paths]
    return QualityCheck(
        name="Every input represented",
        passed=not missing,
        details="All inputs have a compiled brain page." if not missing else ", ".join(missing),
    )


def _check_source_pages_exist(brain_dir: Path, docs: List[InputDocument]) -> QualityCheck:
    missing = [doc.path.name for doc in docs if not (brain_dir / "sources" / doc.path.name).exists()]
    return QualityCheck(
        name="Source summaries created",
        passed=not missing,
        details="All inputs have source summary pages." if not missing else ", ".join(missing),
    )


def _check_source_urls_preserved(brain_dir: Path, docs: List[InputDocument]) -> QualityCheck:
    missing = []
    for doc in docs:
        source_page = brain_dir / "sources" / doc.path.name
        text = source_page.read_text() if source_page.exists() else ""
        for source in doc.sources:
            if source not in text:
                missing.append(f"{doc.path.name}: {source}")
    return QualityCheck(
        name="Source URLs preserved",
        passed=not missing,
        details="All source URLs are preserved." if not missing else "; ".join(missing),
    )


def _check_core_files(brain_dir: Path) -> QualityCheck:
    required = [
        "README.md",
        "schema.md",
        "index.md",
        "open_questions.md",
        "changelog.md",
        "graph.json",
        "graph_diff.json",
    ]
    missing = [name for name in required if not (brain_dir / name).exists()]
    return QualityCheck(
        name="Core brain files exist",
        passed=not missing,
        details="All core files exist." if not missing else ", ".join(missing),
    )


def _check_index_links(
    brain_dir: Path,
    pages: Iterable[BrainPage],
    docs: Iterable[InputDocument],
) -> QualityCheck:
    index_path = brain_dir / "index.md"
    index_text = index_path.read_text() if index_path.exists() else ""
    expected = ["README.md", "schema.md", "open_questions.md", "changelog.md", "graph.json", "graph_diff.json"]
    expected.extend(page.path.name for page in pages)
    expected.extend(doc.path.name for doc in docs)
    missing = [name for name in expected if name not in index_text]
    return QualityCheck(
        name="Index links Markdown files",
        passed=not missing,
        details="Index links core, compiled, and source Markdown files." if not missing else ", ".join(missing),
    )
