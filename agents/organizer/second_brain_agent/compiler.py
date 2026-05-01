from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .config import load_agent_config, load_prompt_config
from .graph import GraphBuildResult, build_graph_files, load_previous_state
from .markdown import markdown_list, parse_input_document, relative_markdown_link
from .models import AgentConfig, BrainPage, InputDocument, PromptConfig, QualityCheck
from .quality import evaluate_brain
from .taxonomy import CATEGORIES, category_for, group_by_category, related_slugs_for
from .trace import TraceRecorder


@dataclass(frozen=True)
class CompileResult:
    inputs_processed: int
    pages_written: int
    source_pages_written: int
    graph_result: GraphBuildResult
    quality_checks: List[QualityCheck]
    report_path: Path


class WikiCompiler:
    def __init__(self, config: AgentConfig, prompts: PromptConfig, workspace: Path) -> None:
        self.config = config
        self.prompts = prompts
        self.workspace = workspace
        self.trace = TraceRecorder(config.paths.runs_dir)

    @classmethod
    def from_files(
        cls,
        config_path: Path,
        prompt_path: Path,
        workspace: Path,
    ) -> "WikiCompiler":
        return cls(
            config=load_agent_config(config_path, workspace),
            prompts=load_prompt_config(prompt_path),
            workspace=workspace,
        )

    def run(self) -> CompileResult:
        self.trace.reset()
        self.trace.event("start", "Starting Organizer run", mode=self.config.mode)
        previous_graph_state = load_previous_state(self.config.paths.brain_dir)
        docs = self._load_inputs()
        self._prepare_output_dirs()
        pages = self._plan_pages(docs)
        self._write_base_files(docs)
        self._write_brain_pages(pages)
        self._write_source_pages(pages)
        self._write_index(docs, pages)
        self._write_open_questions(docs, pages)
        self._write_changelog(docs, pages)
        graph_result = self._write_graph(previous_graph_state)
        quality_checks = evaluate_brain(self.config.paths.brain_dir, docs, pages)
        for check in quality_checks:
            self.trace.subagent("critic", f"{check.name}: {'passed' if check.passed else 'failed'} - {check.details}")
        report_path = self._write_run_reports(docs, pages, graph_result, quality_checks)
        self.trace.subagent("archivist", f"Wrote run report to {self._repo_rel(report_path)}.")
        self.trace.flush_subagents()
        self.trace.event("finish", "Finished Organizer run", report=self._repo_rel(report_path))
        return CompileResult(
            inputs_processed=len(docs),
            pages_written=len(pages),
            source_pages_written=len(docs),
            graph_result=graph_result,
            quality_checks=quality_checks,
            report_path=report_path,
        )

    def _load_inputs(self) -> List[InputDocument]:
        input_dir = self.config.paths.input_dir
        if not input_dir.exists():
            raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
        docs = [parse_input_document(path) for path in sorted(input_dir.glob("*.md"))]
        if not docs:
            raise ValueError(f"No Markdown inputs found in {input_dir}")
        self.trace.event(
            "load",
            "Loaded input Markdown files",
            count=len(docs),
            inputs=[self._repo_rel(doc.path) for doc in docs],
        )
        return docs

    def _prepare_output_dirs(self) -> None:
        brain_dir = self.config.paths.brain_dir
        runs_dir = self.config.paths.runs_dir
        if self.config.mode == "dev" and brain_dir.exists():
            self._safe_rmtree(brain_dir)
        brain_dir.mkdir(parents=True, exist_ok=True)
        runs_dir.mkdir(parents=True, exist_ok=True)
        for category in CATEGORIES:
            (brain_dir / category).mkdir(parents=True, exist_ok=True)
        self.trace.event(
            "prepare",
            "Prepared output directories",
            brain_dir=self._repo_rel(brain_dir),
            runs_dir=self._repo_rel(runs_dir),
            rebuilt=self.config.mode == "dev",
        )

    def _safe_rmtree(self, path: Path) -> None:
        resolved = path.resolve()
        workspace = self.workspace.resolve()
        if resolved == workspace or workspace not in resolved.parents:
            raise ValueError(f"Refusing to delete unsafe path: {resolved}")
        shutil.rmtree(resolved)

    def _plan_pages(self, docs: List[InputDocument]) -> Dict[str, BrainPage]:
        pages: Dict[str, BrainPage] = {}
        for doc in docs:
            category = category_for(doc)
            page_path = self.config.paths.brain_dir / category / f"{doc.slug}.md"
            pages[doc.slug] = BrainPage(
                title=doc.title,
                category=category,
                slug=doc.slug,
                path=page_path,
                source_doc=doc,
                related_slugs=related_slugs_for(doc, docs),
            )
            self.trace.subagent(
                "curator",
                f"Assigned `{doc.title}` to `{category}/{doc.slug}.md`.",
            )
        return pages

    def _write_base_files(self, docs: List[InputDocument]) -> None:
        self._write_readme(docs)
        self._write_schema()
        self.trace.subagent("archivist", "Wrote README.md and schema.md.")

    def _write_readme(self, docs: List[InputDocument]) -> None:
        brain_dir = self.config.paths.brain_dir
        content = f"""# Personal Second Brain

This Markdown wiki was compiled from enriched input files in `{self._repo_rel(self.config.paths.input_dir)}`.

The current build processed {len(docs)} input files. In dev mode, the brain is rebuilt from scratch on every run so the compiler behavior stays repeatable while prompts and schemas evolve.

Start with [index.md](index.md), then browse concepts, people, companies, topics, events, works, and sources.
"""
        self._write(brain_dir / "README.md", content)

    def _write_schema(self) -> None:
        content = """# Brain Schema

Each compiled page should contain:

- A short title.
- Dense, source-backed information.
- Links to the source summary page and original URLs.
- Related pages when useful.

Core folders:

- `topics/`: broad areas and cross-cutting themes.
- `concepts/`: reusable ideas, models, techniques, and patterns.
- `people/`: people.
- `companies/`: companies and organizations.
- `projects/`: products, repositories, tools, and initiatives.
- `events/`: historical events, releases, incidents, and dated milestones.
- `works/`: books, essays, videos, fictional works, papers, and authored artifacts.
- `sources/`: one summary per raw input file.

Uncertain claims should stay visible and should be carried into `open_questions.md`.
"""
        self._write(self.config.paths.brain_dir / "schema.md", content)

    def _write_index(self, docs: List[InputDocument], pages: Dict[str, BrainPage]) -> None:
        grouped_docs = group_by_category(docs)
        index_path = self.config.paths.brain_dir / "index.md"
        lines = [
            "# Brain Index",
            "",
            "This index is generated at the end of the Organizer build and links to the Markdown files that make up the compiled second brain.",
            "",
            f"Compiled inputs: {len(docs)}",
            "",
            "## Core",
            "",
        ]
        for name in ["README.md", "schema.md", "open_questions.md", "changelog.md"]:
            core_path = self.config.paths.brain_dir / name
            lines.append(f"- {relative_markdown_link(index_path, core_path, name)}")
        lines.append(f"- {relative_markdown_link(index_path, self.config.paths.brain_dir / 'graph.json', 'graph.json')}")
        lines.append(
            f"- {relative_markdown_link(index_path, self.config.paths.brain_dir / 'graph_diff.json', 'graph_diff.json')}"
        )
        lines.append("")
        for category in ["topics", "concepts", "people", "companies", "projects", "events", "works"]:
            category_docs = grouped_docs.get(category, [])
            if not category_docs:
                continue
            lines.extend([f"## {category.title()}", ""])
            for doc in category_docs:
                page = pages[doc.slug]
                link = relative_markdown_link(index_path, page.path, page.title)
                lines.append(f"- {link}")
            lines.append("")
        lines.extend(["## Sources", ""])
        for doc in sorted(docs, key=lambda item: item.title.lower()):
            source_path = self.config.paths.brain_dir / "sources" / doc.path.name
            link = relative_markdown_link(index_path, source_path, doc.title)
            lines.append(f"- {link}")
        self._write(index_path, "\n".join(lines))
        self.trace.subagent("archivist", "Generated final brain/index.md with core, compiled, and source links.")

    def _write_graph(self, previous_graph_state: Dict[str, object]) -> GraphBuildResult:
        graph_result = build_graph_files(
            self.config.paths.brain_dir,
            previous_graph_state,
            datetime.now().astimezone(),
        )
        self.trace.subagent(
            "archivist",
            f"Wrote graph artifacts with {graph_result.node_count} nodes, {graph_result.edge_count} edges, "
            f"{graph_result.new_nodes} new nodes, {graph_result.changed_nodes} changed nodes, "
            f"and {graph_result.new_edges} new edges.",
        )
        return graph_result

    def _write_open_questions(self, docs: List[InputDocument], pages: Dict[str, BrainPage]) -> None:
        questions = []
        for doc in docs:
            lowered = doc.information.lower()
            if "uncertain" in lowered or "likely" in lowered or "could" in lowered:
                page = pages[doc.slug]
                link = relative_markdown_link(self.config.paths.brain_dir / "open_questions.md", page.path, page.title)
                questions.append(f"- Review uncertainty in {link}.")
        if not questions:
            questions.append("- No obvious unresolved questions were detected during this deterministic pass.")
        content = "# Open Questions\n\n" + "\n".join(questions) + "\n"
        self._write(self.config.paths.brain_dir / "open_questions.md", content)
        self.trace.subagent("critic", f"Collected {len(questions)} open-question notes.")

    def _write_changelog(self, docs: List[InputDocument], pages: Dict[str, BrainPage]) -> None:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        lines = [
            "# Changelog",
            "",
            f"## {now}",
            "",
            f"- Mode: `{self.config.mode}`.",
            f"- Rebuilt brain from {len(docs)} input files.",
            f"- Wrote {len(pages)} compiled pages and {len(docs)} source summaries.",
            "- Updated index, schema, open questions, changelog, and run report.",
        ]
        self._write(self.config.paths.brain_dir / "changelog.md", "\n".join(lines) + "\n")
        self.trace.subagent("archivist", "Updated changelog.md.")

    def _write_brain_pages(self, pages: Dict[str, BrainPage]) -> None:
        for page in pages.values():
            doc = page.source_doc
            source_page = self.config.paths.brain_dir / "sources" / doc.path.name
            input_link = relative_markdown_link(page.path, doc.path, doc.path.name)
            source_summary_link = relative_markdown_link(page.path, source_page, "source summary")
            related_links = self._related_links(page, pages)
            lines = [
                f"# {page.title}",
                "",
                "## Information",
                "",
                doc.information,
                "",
                "## Source Trace",
                "",
                f"- Input file: {input_link}",
                f"- Source summary: {source_summary_link}",
                "",
                "## Sources",
                "",
                markdown_list(doc.sources),
            ]
            if related_links:
                lines.extend(["", "## Related", "", markdown_list(related_links)])
            self._write(page.path, "\n".join(lines) + "\n")
            self.trace.subagent(
                "synthesizer",
                f"Wrote `{self._repo_rel(page.path)}` with {len(doc.sources)} source URL(s).",
            )

    def _write_source_pages(self, pages: Dict[str, BrainPage]) -> None:
        for page in pages.values():
            doc = page.source_doc
            source_path = self.config.paths.brain_dir / "sources" / doc.path.name
            compiled_link = relative_markdown_link(source_path, page.path, page.title)
            input_link = relative_markdown_link(source_path, doc.path, doc.path.name)
            content = f"""# Source: {doc.title}

## Input

- {input_link}

## Compiled Into

- {compiled_link}

## Information

{doc.information}

## Source URLs

{markdown_list(doc.sources)}
"""
            self._write(source_path, content)
            self.trace.subagent("archivist", f"Wrote source summary `{self._repo_rel(source_path)}`.")

    def _write_run_reports(
        self,
        docs: List[InputDocument],
        pages: Dict[str, BrainPage],
        graph_result: GraphBuildResult,
        quality_checks: List[QualityCheck],
    ) -> Path:
        now = datetime.now().astimezone()
        latest = self.config.paths.runs_dir / "latest_report.md"
        checks = "\n".join(
            f"- [{'x' if check.passed else ' '}] {check.name}: {check.details}" for check in quality_checks
        )
        input_lines = "\n".join(f"- {self._repo_rel(doc.path)}" for doc in docs)
        page_lines = "\n".join(f"- {self._repo_rel(page.path)}" for page in pages.values())
        status = "Passed" if all(check.passed for check in quality_checks) else "Passed with warnings"
        content = f"""# Run Report

Date: {now.isoformat(timespec="seconds")}
Mode: `{self.config.mode}`

## Inputs Processed

{input_lines}

## Pages Written

{page_lines}

## Quality Checks

{checks}

## Index

- brain/index.md
- brain/graph.json
- brain/graph_diff.json

## Graph

- Nodes: {graph_result.node_count}
- Edges: {graph_result.edge_count}
- New nodes: {graph_result.new_nodes}
- Changed nodes: {graph_result.changed_nodes}
- New edges: {graph_result.new_edges}
- Removed edges: {graph_result.removed_edges}

## Trace

- runs/trace.jsonl
- runs/subagents/curator.md
- runs/subagents/synthesizer.md
- runs/subagents/critic.md
- runs/subagents/archivist.md

## Final Status

{status}
"""
        self._write(latest, content)
        return latest

    def _related_links(self, page: BrainPage, pages: Dict[str, BrainPage]) -> List[str]:
        links = []
        for slug in page.related_slugs:
            related = pages.get(slug)
            if related:
                links.append(relative_markdown_link(page.path, related.path, related.title))
        return links

    def _repo_rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.workspace.resolve()).as_posix()

    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n")
