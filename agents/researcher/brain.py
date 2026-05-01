from __future__ import annotations

from pathlib import Path


class BrainReader:
    def __init__(self, brain_dir: Path) -> None:
        self.brain_dir = brain_dir

    def read_index(self) -> str:
        index_path = self.brain_dir / "index.md"
        if not index_path.is_file():
            raise FileNotFoundError(f"brain/index.md not found at {index_path}")
        return index_path.read_text(encoding="utf-8")

    def available_paths(self) -> set[str]:
        if not self.brain_dir.is_dir():
            return set()
        root = self.brain_dir.resolve()
        paths: set[str] = set()
        for path in root.rglob("*.md"):
            try:
                relative = path.resolve().relative_to(root)
            except ValueError:
                continue
            paths.add(relative.as_posix())
        return paths

    def read_note(self, rel_path: str) -> str:
        cleaned = rel_path.strip().lstrip("/").lstrip("\\")
        if cleaned.startswith("brain/"):
            cleaned = cleaned[len("brain/") :]
        candidate = (self.brain_dir / cleaned).resolve()
        root = self.brain_dir.resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"path escapes brain/: {rel_path}") from exc
        if not candidate.is_file():
            raise FileNotFoundError(f"brain note not found: {rel_path}")
        return candidate.read_text(encoding="utf-8")

    def normalize(self, rel_path: str) -> str:
        cleaned = rel_path.strip().lstrip("/").lstrip("\\")
        if cleaned.startswith("brain/"):
            cleaned = cleaned[len("brain/") :]
        return cleaned.replace("\\", "/")
