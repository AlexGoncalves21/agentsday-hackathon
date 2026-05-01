from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from agents.organizer.second_brain_agent.compiler import WikiCompiler
from agents.organizer.second_brain_agent.markdown import parse_input_document


class InputParserTests(unittest.TestCase):
    def test_parse_input_document_contract(self) -> None:
        workspace = Path.cwd() / ".test-tmp" / uuid4().hex
        workspace.mkdir(parents=True, exist_ok=True)
        try:
            path = workspace / "example.md"
            path.write_text(
                """# Example

## Information

Some dense information.

## Sources

- https://example.com
"""
            )
            document = parse_input_document(path)
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

        self.assertEqual(document.title, "Example")
        self.assertEqual(document.slug, "example")
        self.assertEqual(document.sources, ["https://example.com"])

    def test_scan_mode_preserves_existing_brain_index_and_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_dir = workspace / "input"
            brain_dir = workspace / "brain"
            runs_dir = workspace / "runs"
            input_dir.mkdir()
            (brain_dir / "concepts").mkdir(parents=True)
            (brain_dir / "sources").mkdir(parents=True)
            (brain_dir / "concepts" / "existing-topic.md").write_text("# Existing Topic\n\nPrior information.\n")
            (brain_dir / "sources" / "existing-topic.md").write_text("# Source: Existing Topic\n")
            (input_dir / "new-topic.md").write_text(
                """# New Topic

## Information

New information.

## Sources

- https://example.com/new
"""
            )
            config_path = workspace / "config.yaml"
            config_path.write_text(
                """mode: scan

paths:
  input_dir: input
  brain_dir: brain
  runs_dir: runs

model:
  provider: gemini
  name: gemini-3-flash-preview
"""
            )
            prompt_path = workspace / "prompts.yaml"
            prompt_path.write_text("system: ''\n")

            compiler = WikiCompiler.from_files(config_path, prompt_path, workspace)
            compiler.run()

            index_text = (brain_dir / "index.md").read_text()
            self.assertIn("Existing Topic", index_text)
            self.assertIn("New Topic", index_text)
            self.assertFalse((input_dir / "new-topic.md").exists())

            graph = json.loads((brain_dir / "graph.json").read_text())
            node_ids = {node["id"] for node in graph["nodes"]}
            self.assertIn("concepts/existing-topic.md", node_ids)
            self.assertIn("concepts/new-topic.md", node_ids)

    def test_social_post_inputs_are_curated_into_brain_note_titles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_dir = workspace / "input"
            brain_dir = workspace / "brain"
            runs_dir = workspace / "runs"
            input_dir.mkdir()
            brain_dir.mkdir()
            (input_dir / "naval.md").write_text(
                """# X Post by naval: The promise of AI is no UI.

## Information

X/Twitter post captured from the exact submitted status URL.

Author: naval

Post text:

The promise of AI is no UI.

Linked or media URLs:

- https://x.com/naval/status/1770296527120166927

## Sources

- https://x.com/naval/status/1770296527120166927
"""
            )
            config_path = workspace / "config.yaml"
            config_path.write_text(
                """mode: scan

paths:
  input_dir: input
  brain_dir: brain
  runs_dir: runs

model:
  provider: gemini
  name: gemini-3-flash-preview
"""
            )
            prompt_path = workspace / "prompts.yaml"
            prompt_path.write_text("system: ''\n")

            WikiCompiler.from_files(config_path, prompt_path, workspace).run()

            self.assertTrue((brain_dir / "concepts" / "ai-is-no-ui.md").exists())
            self.assertFalse((brain_dir / "concepts" / "x-post-by-naval-the-promise-of-ai-is-no-ui.md").exists())
            self.assertFalse((input_dir / "naval.md").exists())
            graph = json.loads((brain_dir / "graph.json").read_text())
            labels = {node["label"] for node in graph["nodes"]}
            self.assertIn("AI Is No UI", labels)
            self.assertNotIn("X Post by naval: The promise of AI is no UI.", labels)

    def test_scan_mode_links_new_pages_to_existing_brain_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_dir = workspace / "input"
            brain_dir = workspace / "brain"
            runs_dir = workspace / "runs"
            input_dir.mkdir()
            (brain_dir / "concepts").mkdir(parents=True)
            (brain_dir / "sources").mkdir(parents=True)
            (brain_dir / "concepts" / "intelligence-vs-agency.md").write_text(
                "# Intelligence vs Agency\n\nAI agents connect intelligence, agency, automation, and interfaces.\n"
            )
            (brain_dir / "sources" / "existing.md").write_text("# Source: Existing\n")
            (input_dir / "naval.md").write_text(
                """# X Post by naval: The promise of AI is no UI.

## Information

Post text:

The promise of AI is no UI.

## Sources

- https://x.com/naval/status/1770296527120166927
"""
            )
            config_path = workspace / "config.yaml"
            config_path.write_text(
                """mode: scan

paths:
  input_dir: input
  brain_dir: brain
  runs_dir: runs

model:
  provider: gemini
  name: gemini-3-flash-preview
"""
            )
            prompt_path = workspace / "prompts.yaml"
            prompt_path.write_text("system: ''\n")

            WikiCompiler.from_files(config_path, prompt_path, workspace).run()

            new_page = brain_dir / "concepts" / "ai-is-no-ui.md"
            self.assertIn("intelligence-vs-agency.md", new_page.read_text())
            self.assertFalse((input_dir / "naval.md").exists())
            graph = json.loads((brain_dir / "graph.json").read_text())
            edge_pairs = {(edge["source"], edge["target"]) for edge in graph["edges"]}
            self.assertIn(("concepts/ai-is-no-ui.md", "concepts/intelligence-vs-agency.md"), edge_pairs)
            self.assertEqual(1, len(edge_pairs))

    def test_scan_mode_does_not_link_unrelated_long_notes_to_everything(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_dir = workspace / "input"
            brain_dir = workspace / "brain"
            runs_dir = workspace / "runs"
            input_dir.mkdir()
            (brain_dir / "concepts").mkdir(parents=True)
            (brain_dir / "sources").mkdir(parents=True)
            (brain_dir / "concepts" / "intelligence-vs-agency.md").write_text(
                "# Intelligence vs Agency\n\nAI agents connect intelligence, agency, automation, and interfaces.\n"
            )
            (brain_dir / "concepts" / "decision-theory.md").write_text(
                "# Decision Theory\n\nDecision making, uncertainty, and game theory.\n"
            )
            (brain_dir / "sources" / "existing.md").write_text("# Source: Existing\n")
            (input_dir / "roman.md").write_text(
                """# Roman Empire

## Information

The Roman Empire had government, military administration, public infrastructure, legal systems, and social hierarchy.
This deliberately long note shares generic words with many other subjects, but its title does not describe the same concept.

## Sources

- https://example.com/roman
"""
            )
            config_path = workspace / "config.yaml"
            config_path.write_text(
                """mode: scan

paths:
  input_dir: input
  brain_dir: brain
  runs_dir: runs

model:
  provider: gemini
  name: gemini-3-flash-preview
"""
            )
            prompt_path = workspace / "prompts.yaml"
            prompt_path.write_text("system: ''\n")

            WikiCompiler.from_files(config_path, prompt_path, workspace).run()

            roman_page = brain_dir / "concepts" / "roman-empire.md"
            self.assertTrue(roman_page.exists())
            self.assertNotIn("## Related", roman_page.read_text())
            graph = json.loads((brain_dir / "graph.json").read_text())
            self.assertFalse(any(edge["source"] == "concepts/roman-empire.md" for edge in graph["edges"]))

    def test_failed_input_parse_does_not_delete_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            input_dir = workspace / "input"
            input_dir.mkdir()
            bad_input = input_dir / "broken.md"
            bad_input.write_text(
                """# Broken

## Information

Missing the required sources section.
"""
            )
            config_path = workspace / "config.yaml"
            config_path.write_text(
                """mode: dev

paths:
  input_dir: input
  brain_dir: brain
  runs_dir: runs

model:
  provider: gemini
  name: gemini-3-flash-preview
"""
            )
            prompt_path = workspace / "prompts.yaml"
            prompt_path.write_text("system: ''\n")

            compiler = WikiCompiler.from_files(config_path, prompt_path, workspace)
            with self.assertRaises(ValueError):
                compiler.run()

            self.assertTrue(bad_input.exists())


if __name__ == "__main__":
    unittest.main()
