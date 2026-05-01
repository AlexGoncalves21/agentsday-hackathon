from __future__ import annotations

import argparse
from pathlib import Path

from .compiler import WikiCompiler
from .config import load_agent_config, load_prompt_config
from .deep_agent import run_deep_agent
from .markdown import parse_input_document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Organizer second brain compiler")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Compile input Markdown into brain/")
    run_parser.add_argument("--config", default="agents/organizer/config.yaml", help="Path to Organizer config YAML")
    run_parser.add_argument(
        "--prompts",
        default="agents/organizer/prompts/organizer.yaml",
        help="Path to Organizer prompt YAML",
    )
    run_parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Run through LangChain Deep Agents instead of the deterministic compiler",
    )

    validate_parser = subparsers.add_parser("validate-inputs", help="Validate input Markdown structure")
    validate_parser.add_argument("--input-dir", default="input", help="Input directory")

    args = parser.parse_args(argv)
    command = args.command or "run"
    workspace = Path.cwd()

    if command == "validate-inputs":
        return _validate_inputs(workspace / args.input_dir)

    if command == "run":
        config_path = workspace / args.config
        prompt_path = workspace / args.prompts
        if args.use_llm:
            config = load_agent_config(config_path, workspace)
            prompts = load_prompt_config(prompt_path)
            result = run_deep_agent(config, prompts, workspace)
            print(result)
            return 0

        compiler = WikiCompiler.from_files(config_path, prompt_path, workspace)
        result = compiler.run()
        failed = [check for check in result.quality_checks if not check.passed]
        print(f"Processed {result.inputs_processed} inputs.")
        print(f"Wrote {result.pages_written} compiled pages and {result.source_pages_written} source pages.")
        print(f"Report: {result.report_path}")
        if failed:
            print("Warnings:")
            for check in failed:
                print(f"- {check.name}: {check.details}")
        return 0

    parser.print_help()
    return 2


def _validate_inputs(input_dir: Path) -> int:
    paths = sorted(input_dir.glob("*.md"))
    if not paths:
        print(f"No Markdown files found in {input_dir}")
        return 1
    errors = []
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
