from __future__ import annotations

import unittest
from pathlib import Path
import shutil
from uuid import uuid4

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


if __name__ == "__main__":
    unittest.main()
