from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .config import load_agent_config, load_prompt_config
from .graph import GraphBuildResult, build_graph_files, load_previous_state
from .markdown import markdown_list, parse_input_document, relative_markdown_link, slugify
from .models import AgentConfig, BrainPage, ExistingBrainPage, InputDocument, PromptConfig, QualityCheck
from .quality import evaluate_brain
from .reasoning import OrganizerReasoner
from .taxonomy import CATEGORIES, category_for, group_by_category, related_slugs_for, semantic_links_for
from .trace import TraceRecorder

MIN_LOOP_ITERATIONS = 2
MAX_RELATED_SLUGS = 6
GENERATED_MARKDOWN_SECTION_RE = re.compile(
    r"(?ms)^#{1,6}\s*(?:Source Trace|Related|Brain links that should probably exist later):?\s*\n.*?(?=^#{1,6}\s+|\Z)"
)
BRAIN_LINKS_BLOCK_RE = re.compile(
    r"(?ms)^Brain links that should probably exist later:\s*\n(?:^[ \t]*[-*].*(?:\n|$)|^[ \t]*\n)*"
)
SEMANTIC_IGNORED_SECTION_RE = re.compile(r"(?ms)^#{1,6}\s*(?:Sources|Source URLs)\s*\n.*?(?=^#{1,6}\s+|\Z)")


@dataclass(frozen=True)
class CompileResult:
    inputs_processed: int
    pages_written: int
    source_pages_written: int
    graph_result: GraphBuildResult
    quality_checks: List[QualityCheck]
    report_path: Path
    iterations_run: int
    stabilized: bool


class WikiCompiler:
    def __init__(
        self,
        config: AgentConfig,
        prompts: PromptConfig,
        workspace: Path,
        reasoner: OrganizerReasoner | None = None,
    ) -> None:
        self.config = config
        self.prompts = prompts
        self.workspace = workspace
        self.trace = TraceRecorder(config.paths.runs_dir)
        self.reasoner = reasoner

    @classmethod
    def from_files(
        cls,
        config_path: Path,
        prompt_path: Path,
        workspace: Path,
        enable_reasoning: bool = False,
    ) -> "WikiCompiler":
        config = load_agent_config(config_path, workspace)
        prompts = load_prompt_config(prompt_path)
        reasoner = OrganizerReasoner(config, prompts) if enable_reasoning else None
        return cls(config=config, prompts=prompts, workspace=workspace, reasoner=reasoner)

    def run(self) -> CompileResult:
        self.trace.reset()
        self.trace.event("start", "Starting Organizer run", mode=self.config.mode)
        previous_graph_state = load_previous_state(self.config.paths.brain_dir)
        docs = self._load_inputs()
        self._prepare_output_dirs()
        existing_pages = self._existing_brain_pages()
        pages, iterations_run, stabilized = self._run_planning_loop(docs, existing_pages)
        self._write_brain_pages(pages)
        self._write_source_pages(pages)
        self._write_base_files(docs)
        self._write_index(docs, pages)
        self._write_open_questions(docs, pages)
        self._write_changelog(docs, pages)
        graph_result = self._write_graph(previous_graph_state)
        quality_checks = evaluate_brain(self.config.paths.brain_dir, docs, pages)
        for check in quality_checks:
            self.trace.subagent("critic", f"{check.name}: {'passed' if check.passed else 'failed'} - {check.details}")
        report_path = self._write_run_reports(docs, pages, graph_result, quality_checks, iterations_run, stabilized)
        self.trace.subagent("archivist", f"Wrote run report to {self._repo_rel(report_path)}.")
        self._delete_processed_inputs(docs)
        self.trace.flush_subagents()
        self.trace.event("finish", "Finished Organizer run", report=self._repo_rel(report_path))
        return CompileResult(
            inputs_processed=len(docs),
            pages_written=len(pages),
            source_pages_written=len(docs),
            graph_result=graph_result,
            quality_checks=quality_checks,
            report_path=report_path,
            iterations_run=iterations_run,
            stabilized=stabilized,
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

    def _delete_processed_inputs(self, docs: List[InputDocument]) -> None:
        input_dir = self.config.paths.input_dir.resolve()
        deleted = []
        for doc in docs:
            input_path = doc.path.resolve()
            if input_path == input_dir or input_dir not in input_path.parents:
                raise ValueError(f"Refusing to delete unsafe input path: {input_path}")
            input_path.unlink(missing_ok=True)
            deleted.append(self._repo_rel(input_path))
        self.trace.subagent("archivist", f"Deleted {len(deleted)} processed input file(s): {', '.join(deleted)}.")

    def _run_planning_loop(
        self,
        docs: List[InputDocument],
        existing_pages: Dict[str, ExistingBrainPage],
    ) -> tuple[Dict[str, BrainPage], int, bool]:
        max_iterations = max(1, self.config.loop.max_iterations)
        min_iterations = min(max_iterations, MIN_LOOP_ITERATIONS)
        pages: Dict[str, BrainPage] = {}
        stabilized = False
        iterations_run = 0

        for iteration in range(1, max_iterations + 1):
            iterations_run = iteration
            self.trace.event(
                "loop",
                "Starting Organizer planning loop iteration",
                iteration=iteration,
                max_iterations=max_iterations,
            )
            if not pages:
                pages = self._plan_pages(docs, existing_pages)

            critique = self._critique_page_plan(docs, pages, existing_pages)
            if critique:
                self.trace.subagent("critic", f"Iteration {iteration}: requested fixes: {'; '.join(critique)}.")
            else:
                self.trace.subagent("critic", f"Iteration {iteration}: page plan passed critique.")
            if self.reasoner:
                model_critique = self.reasoner.critique_page_plan(iteration, docs, pages, critique)
                self.trace.subagent("critic", f"Iteration {iteration} model critique: {model_critique}")

            improved_pages, changes = self._improve_page_plan(pages, existing_pages)
            if changes:
                self.trace.subagent("synthesizer", f"Iteration {iteration}: refined page plan: {'; '.join(changes)}.")
            else:
                self.trace.subagent("synthesizer", f"Iteration {iteration}: no page-plan refinements needed.")

            pages = improved_pages
            if not critique and not changes and iteration >= min_iterations:
                stabilized = True
                self.trace.event("loop", "Organizer planning loop stabilized", iteration=iteration)
                break

        if not stabilized:
            self.trace.event("loop", "Organizer planning loop reached max iterations", iterations=iterations_run)
        return pages, iterations_run, stabilized

    def _plan_pages(self, docs: List[InputDocument], existing_pages: Dict[str, ExistingBrainPage]) -> Dict[str, BrainPage]:
        pages: Dict[str, BrainPage] = {}
        curated_docs = [self._semantic_input_document(self._curate_document(doc)) for doc in docs]
        relation_docs = curated_docs + [
            InputDocument(
                path=page.path,
                title=page.title,
                information=self._semantic_note_text(self._markdown_text(page.path)),
                sources=[],
                slug=page.slug,
            )
            for page in existing_pages.values()
        ]
        for doc, curated_doc in zip(docs, curated_docs):
            category = category_for(curated_doc)
            page_path = self.config.paths.brain_dir / category / f"{curated_doc.slug}.md"
            pages[curated_doc.slug] = BrainPage(
                title=curated_doc.title,
                category=category,
                slug=curated_doc.slug,
                path=page_path,
                source_doc=doc,
                related_slugs=related_slugs_for(curated_doc, relation_docs),
            )
            self.trace.subagent(
                "curator",
                f"Assigned `{doc.title}` to `{category}/{curated_doc.slug}.md` as `{curated_doc.title}`.",
            )
        return pages

    def _critique_page_plan(
        self,
        docs: List[InputDocument],
        pages: Dict[str, BrainPage],
        existing_pages: Dict[str, ExistingBrainPage],
    ) -> List[str]:
        issues = []
        represented_inputs = {page.source_doc.path.resolve() for page in pages.values()}
        missing_inputs = [doc.path.name for doc in docs if doc.path.resolve() not in represented_inputs]
        if missing_inputs:
            issues.append(f"missing compiled pages for {', '.join(missing_inputs)}")

        available_slugs = set(pages) | set(existing_pages)
        for page in pages.values():
            if page.slug in page.related_slugs:
                issues.append(f"`{page.slug}` links to itself")
            unknown = [slug for slug in page.related_slugs if slug not in available_slugs]
            if unknown:
                issues.append(f"`{page.slug}` links to unavailable pages: {', '.join(unknown)}")
            if len(page.related_slugs) > MAX_RELATED_SLUGS:
                issues.append(f"`{page.slug}` has too many related links")

        for page in pages.values():
            for related_slug in page.related_slugs:
                related = pages.get(related_slug)
                if related and page.slug not in related.related_slugs:
                    issues.append(f"`{page.slug}` and `{related_slug}` need reciprocal related links")
        return issues

    def _improve_page_plan(
        self,
        pages: Dict[str, BrainPage],
        existing_pages: Dict[str, ExistingBrainPage],
    ) -> tuple[Dict[str, BrainPage], List[str]]:
        available_slugs = set(pages) | set(existing_pages)
        related_by_slug = {
            slug: self._clean_related_slugs(page.related_slugs, slug, available_slugs) for slug, page in pages.items()
        }
        changes = []

        for slug, related_slugs in list(related_by_slug.items()):
            for related_slug in list(related_slugs):
                if related_slug not in pages:
                    continue
                reciprocal = related_by_slug.setdefault(related_slug, [])
                if slug not in reciprocal and len(reciprocal) < MAX_RELATED_SLUGS:
                    reciprocal.append(slug)

        improved_pages = {}
        for slug, page in pages.items():
            related_slugs = related_by_slug.get(slug, [])[:MAX_RELATED_SLUGS]
            if related_slugs != page.related_slugs:
                changes.append(f"`{slug}` related links normalized")
            improved_pages[slug] = replace(page, related_slugs=related_slugs)
        return improved_pages, changes

    def _clean_related_slugs(self, related_slugs: List[str], page_slug: str, available_slugs: set[str]) -> List[str]:
        clean = []
        for related_slug in related_slugs:
            if related_slug == page_slug or related_slug not in available_slugs or related_slug in clean:
                continue
            clean.append(related_slug)
            if len(clean) == MAX_RELATED_SLUGS:
                break
        return clean

    def _curate_document(self, doc: InputDocument) -> InputDocument:
        title = self._curated_title(doc)
        if title == doc.title:
            return doc
        return replace(doc, title=title, slug=slugify(title))

    def _semantic_input_document(self, doc: InputDocument) -> InputDocument:
        return replace(doc, information=self._clean_note_information(doc.information))

    def _curated_title(self, doc: InputDocument) -> str:
        lowered_title = doc.title.lower()
        if lowered_title.startswith(("x post by ", "twitter post by ")):
            post_text = self._extract_social_post_text(doc.information)
            if post_text:
                return self._concept_title_from_sentence(post_text)
        return doc.title

    def _extract_social_post_text(self, information: str) -> str:
        lines = information.splitlines()
        for index, line in enumerate(lines):
            if line.strip().lower() != "post text:":
                continue
            for candidate in lines[index + 1 :]:
                stripped = candidate.strip()
                if not stripped:
                    continue
                if stripped.lower().startswith("linked or media urls:"):
                    return ""
                return stripped
        return ""

    def _concept_title_from_sentence(self, sentence: str) -> str:
        cleaned = sentence.strip().strip('"').strip("'").rstrip(".!?")
        if cleaned.lower() == "the promise of ai is no ui":
            return "AI Is No UI"
        words = cleaned.split()
        if len(words) > 10:
            cleaned = " ".join(words[:10])
        return cleaned[:1].upper() + cleaned[1:]

    def _write_base_files(self, docs: List[InputDocument]) -> None:
        self._write_readme(docs)
        self._write_schema()
        self.trace.subagent("archivist", "Wrote README.md and schema.md.")

    def _write_readme(self, docs: List[InputDocument]) -> None:
        brain_dir = self.config.paths.brain_dir
        input_count = self._brain_input_count(default=len(docs))
        content = f"""# Personal Second Brain

This Markdown wiki was compiled from enriched input files in `{self._repo_rel(self.config.paths.input_dir)}`.

The current build includes {input_count} input files. In dev mode, the brain is rebuilt from scratch on every run so the compiler behavior stays repeatable while prompts and schemas evolve.

Start with [index.md](index.md), then browse concepts, people, companies, topics, events, works, and sources.
"""
        self._write(brain_dir / "README.md", content)

    def _write_schema(self) -> None:
        content = """# Brain Schema

Each compiled page should contain:

- A short title.
- Dense, source-backed information.
- Source URLs when available.

Core folders:

- `topics/`: broad areas and cross-cutting themes.
- `concepts/`: reusable ideas, models, techniques, and patterns.
- `people/`: people.
- `companies/`: companies and organizations.
- `projects/`: products, repositories, tools, and initiatives.
- `events/`: historical events, releases, incidents, and dated milestones.
- `works/`: books, essays, videos, fictional works, papers, and authored artifacts.
- `sources/`: one durable summary per processed input file.

Uncertain claims should stay visible and should be carried into `open_questions.md`.
"""
        self._write(self.config.paths.brain_dir / "schema.md", content)

    def _write_index(self, docs: List[InputDocument], pages: Dict[str, BrainPage]) -> None:
        index_path = self.config.paths.brain_dir / "index.md"
        source_pages = self._source_pages()
        lines = [
            "# Brain Index",
            "",
            "This index is generated at the end of the Organizer build and links to the Markdown files that make up the compiled second brain.",
            "",
            f"Compiled inputs: {len(source_pages) or len(docs)}",
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
            category_pages = self._category_pages(category)
            if not category_pages:
                continue
            lines.extend([f"## {category.title()}", ""])
            for page_path in category_pages:
                link = relative_markdown_link(index_path, page_path, self._markdown_title(page_path))
                lines.append(f"- {link}")
            lines.append("")
        lines.extend(["## Sources", ""])
        for source_path in source_pages:
            link = relative_markdown_link(index_path, source_path, self._markdown_title(source_path).replace("Source: ", ""))
            lines.append(f"- {link}")
        self._write(index_path, "\n".join(lines))
        self.trace.subagent("archivist", "Generated final brain/index.md with core, compiled, and source links.")

    def _write_graph(self, previous_graph_state: Dict[str, object]) -> GraphBuildResult:
        graph_result = build_graph_files(
            self.config.paths.brain_dir,
            previous_graph_state,
            datetime.now().astimezone(),
            self._semantic_graph_links(),
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
        existing_questions = ""
        questions_path = self.config.paths.brain_dir / "open_questions.md"
        if self.config.mode != "dev" and questions_path.exists():
            existing_questions = questions_path.read_text(encoding="utf-8").strip()
        for doc in docs:
            lowered = doc.information.lower()
            if "uncertain" in lowered or "likely" in lowered or "could" in lowered:
                page = next((candidate for candidate in pages.values() if candidate.source_doc.path == doc.path), None)
                if not page:
                    continue
                link = relative_markdown_link(self.config.paths.brain_dir / "open_questions.md", page.path, page.title)
                questions.append(f"- Review uncertainty in {link}.")
        if not questions:
            questions.append("- No obvious unresolved questions were detected during this deterministic pass.")
        content = "# Open Questions\n\n" + "\n".join(questions) + "\n"
        if existing_questions and existing_questions != "# Open Questions":
            content = existing_questions + "\n\n## Latest Scan\n\n" + "\n".join(questions) + "\n"
        self._write(questions_path, content)
        self.trace.subagent("critic", f"Collected {len(questions)} open-question notes.")

    def _write_changelog(self, docs: List[InputDocument], pages: Dict[str, BrainPage]) -> None:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        lines = [
            "# Changelog",
            "",
            f"## {now}",
            "",
            f"- Mode: `{self.config.mode}`.",
            f"- Processed {len(docs)} input files.",
            f"- Wrote {len(pages)} compiled pages and {len(docs)} source summaries.",
            "- Updated index, schema, open questions, changelog, and run report.",
        ]
        changelog_path = self.config.paths.brain_dir / "changelog.md"
        if self.config.mode != "dev" and changelog_path.exists():
            existing = changelog_path.read_text(encoding="utf-8").strip()
            content = "\n".join(lines) + "\n\n" + "\n".join(existing.splitlines()[1:]).strip() + "\n"
        else:
            content = "\n".join(lines) + "\n"
        self._write(changelog_path, content)
        self.trace.subagent("archivist", "Updated changelog.md.")

    def _write_brain_pages(self, pages: Dict[str, BrainPage]) -> None:
        for page in pages.values():
            doc = page.source_doc
            information = self._clean_note_information(doc.information)
            lines = [
                f"# {page.title}",
                "",
                "## Information",
                "",
                information,
                "",
                "## Sources",
                "",
                markdown_list(doc.sources),
            ]
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
            content = f"""# Source: {doc.title}

## Input

- Original input file: `{doc.path.name}`

## Compiled Into

- {compiled_link}

## Information

{doc.information}

## Source URLs

{markdown_list(doc.sources)}
"""
            self._write(source_path, content)
            self.trace.subagent("archivist", f"Wrote source summary `{self._repo_rel(source_path)}`.")

    def _semantic_graph_links(self) -> Dict[str, List[Dict[str, object]]]:
        documents = self._graph_documents()
        rel_by_slug = {document.slug: self._brain_rel(document.path) for document in documents}
        planned_links: Dict[str, List[Dict[str, object]]] = {}
        for document in documents:
            source_rel = rel_by_slug[document.slug]
            planned_links[source_rel] = [
                {
                    "target": rel_by_slug[link["slug"]],
                    "shared_terms": link["terms"],
                    "score": link["score"],
                }
                for link in semantic_links_for(document, documents)
                if link["slug"] in rel_by_slug
            ]
        self.trace.subagent(
            "critic",
            f"Built semantic graph links from TF-IDF note overlap across {len(documents)} compiled page(s).",
        )
        return planned_links

    def _graph_documents(self) -> List[InputDocument]:
        documents = []
        for category in ["topics", "concepts", "people", "companies", "projects", "events", "works"]:
            for path in self._category_pages(category):
                documents.append(
                    InputDocument(
                        path=path,
                        title=self._markdown_title(path),
                        information=self._semantic_note_text(self._markdown_text(path)),
                        sources=[],
                        slug=path.stem,
                    )
                )
        return documents

    def _brain_rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.config.paths.brain_dir.resolve()).as_posix()

    def _clean_note_information(self, text: str) -> str:
        cleaned = GENERATED_MARKDOWN_SECTION_RE.sub("", text)
        cleaned = BRAIN_LINKS_BLOCK_RE.sub("", cleaned)
        return cleaned.strip()

    def _semantic_note_text(self, text: str) -> str:
        cleaned = self._clean_note_information(text)
        cleaned = SEMANTIC_IGNORED_SECTION_RE.sub("", cleaned)
        return cleaned.strip()

    def _write_run_reports(
        self,
        docs: List[InputDocument],
        pages: Dict[str, BrainPage],
        graph_result: GraphBuildResult,
        quality_checks: List[QualityCheck],
        iterations_run: int,
        stabilized: bool,
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

## Organizer Loop

- Iterations run: {iterations_run}
- Stabilized: {'yes' if stabilized else 'no'}

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
        existing_pages = self._existing_brain_pages()
        for slug in page.related_slugs:
            related = pages.get(slug)
            if related:
                links.append(relative_markdown_link(page.path, related.path, related.title))
                continue
            existing = existing_pages.get(slug)
            if existing:
                links.append(relative_markdown_link(page.path, existing.path, existing.title))
        return links

    def _existing_brain_pages(self) -> Dict[str, ExistingBrainPage]:
        pages: Dict[str, ExistingBrainPage] = {}
        if self.config.mode == "dev":
            return pages
        for category in ["topics", "concepts", "people", "companies", "projects", "events", "works"]:
            for path in self._category_pages(category):
                slug = path.stem
                pages[slug] = ExistingBrainPage(
                    title=self._markdown_title(path),
                    category=category,
                    slug=slug,
                    path=path,
                )
        return pages

    def _brain_input_count(self, default: int) -> int:
        source_pages = self._source_pages()
        return len(source_pages) if source_pages else default

    def _category_pages(self, category: str) -> List[Path]:
        category_dir = self.config.paths.brain_dir / category
        if not category_dir.exists():
            return []
        return sorted(category_dir.glob("*.md"), key=lambda path: self._markdown_title(path).lower())

    def _source_pages(self) -> List[Path]:
        source_dir = self.config.paths.brain_dir / "sources"
        if not source_dir.exists():
            return []
        return sorted(source_dir.glob("*.md"), key=lambda path: self._markdown_title(path).lower())

    def _markdown_title(self, path: Path) -> str:
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("# "):
                    return line[2:].strip()
        except FileNotFoundError:
            return path.stem.replace("-", " ").title()
        return path.stem.replace("-", " ").title()

    def _markdown_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""

    def _repo_rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.workspace.resolve()).as_posix()

    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
