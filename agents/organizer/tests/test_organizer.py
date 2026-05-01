from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.organizer.second_brain_agent.markdown import parse_input_document


class InputParserTests(unittest.TestCase):
    def test_parse_input_document_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "example.md"
            path.write_text(
                """# Example

## Information

Some dense information.

## Sources

- https://example.com
"""
            )
            document = parse_input_document(path)

        self.assertEqual(document.title, "Example")
        self.assertEqual(document.slug, "example")
        self.assertEqual(document.sources, ["https://example.com"])


if __name__ == "__main__":
    unittest.main()
