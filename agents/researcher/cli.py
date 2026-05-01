from __future__ import annotations

import argparse
from pathlib import Path

from agents.organizer.second_brain_agent.markdown import parse_input_document

from .clients import smoke_test
from .config import load_research_config
from .service import ResearcherService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Researcher Telegram enrichment agent")
    subparsers = parser.add_subparsers(dest="command")

    process_parser = subparsers.add_parser("process", help="Research and save one submission")
    process_parser.add_argument("text", help="Telegram-style text, URL, topic, or note")

    validate_parser = subparsers.add_parser("validate", help="Validate generated input Markdown")
    validate_parser.add_argument("--input-dir", default="input")

    subparsers.add_parser("smoke-test", help="Check external API auth without printing secrets")

    args = parser.parse_args(argv)
    command = args.command or "process"
    workspace = Path.cwd()

    if command == "process":
        service = ResearcherService.from_workspace(workspace)
        result = service.process_submission(args.text)
        print(f"Saved: {result.path}")
        print(f"Type: {result.submission_type}")
        print(f"Status: {'ok' if result.success else 'failed'}")
        if result.error:
            print(f"Error: {result.error}")
        return 0 if result.success else 1

    if command == "validate":
        return _validate(workspace / args.input_dir)

    if command == "smoke-test":
        config = load_research_config(workspace)
        results = smoke_test(config)
        for name, ok in results.items():
            print(f"{name}: {'ok' if ok else 'failed'}")
        return 0 if all(results.values()) else 1

    parser.print_help()
    return 2


def _validate(input_dir: Path) -> int:
    paths = sorted(input_dir.glob("*.md"))
    if not paths:
        print(f"No Markdown files found in {input_dir}")
        return 1
    errors: list[str] = []
    for path in paths:
        try:
            parse_input_document(path)
        except Exception as exc:
            errors.append(f"{path}: {exc}")
    if errors:
        print("Invalid inputs:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Validated {len(paths)} input files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

