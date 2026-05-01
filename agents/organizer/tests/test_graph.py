from __future__ import annotations

import tempfile
import unittest
import json
from datetime import datetime, timezone
from pathlib import Path

from agents.organizer.second_brain_agent.graph import build_graph_files


class GraphBuilderTests(unittest.TestCase):
    def test_extracts_internal_markdown_links(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            brain = Path(tmp) / "brain"
            concepts = brain / "concepts"
            concepts.mkdir(parents=True)
            (brain / "README.md").write_text("# Brain\n\n[Game](concepts/game.md)\n")
            (brain / "open_questions.md").write_text("# Open Questions\n\n[Game](concepts/game.md)\n")
            (concepts / "game.md").write_text("# Game\n\n[Decision](decision.md)\n[Overview](overview.md)\n")
            (concepts / "decision.md").write_text("# Decision\n")
            (concepts / "overview.md").write_text("# Overview\n")

            result = build_graph_files(brain, {"nodes": {}, "edges": {}}, datetime.now(timezone.utc))

            self.assertEqual(result.node_count, 3)
            graph_text = (brain / "graph.json").read_text()
            self.assertNotIn("README.md", graph_text)
            self.assertNotIn("open_questions.md", graph_text)
            self.assertIn("concepts/game.md->concepts/decision.md", graph_text)
            self.assertIn("concepts/game.md->concepts/overview.md", graph_text)
            graph = json.loads(result.graph_path.read_text())
            history = json.loads((brain / "graph_history.json").read_text())
            self.assertEqual(history["graphs"][0]["build_id"], graph["build_id"])


if __name__ == "__main__":
    unittest.main()
