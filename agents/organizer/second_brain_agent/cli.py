from __future__ import annotations

import argparse
import os
from pathlib import Path

from .compiler import WikiCompiler
from .env import load_dotenv
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
        help="Deprecated: LLM reasoning is now the default for Organizer runs.",
    )
    run_parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Run the local deterministic compiler without model reasoning or LangSmith model traces.",
    )
    run_parser.add_argument(
        "--no-langsmith",
        action="store_true",
        help="Disable LangSmith tracing for this run, even if .env enables it",
    )

    validate_parser = subparsers.add_parser("validate-inputs", help="Validate input Markdown structure")
    validate_parser.add_argument("--input-dir", default="input", help="Input directory")

    subparsers.add_parser("list-models", help="List Gemini generateContent models available to GEMINI_API_KEY")
    subparsers.add_parser("check-langsmith", help="Check LangSmith authentication and workspace access")

    args = parser.parse_args(argv)
    command = args.command or "run"
    workspace = Path.cwd()

    if command == "validate-inputs":
        return _validate_inputs(workspace / args.input_dir)

    if command == "list-models":
        load_dotenv(workspace / ".env")
        return _list_models()

    if command == "check-langsmith":
        load_dotenv(workspace / ".env")
        return _check_langsmith()

    if command == "run":
        config_path = workspace / args.config
        prompt_path = workspace / args.prompts
        load_dotenv(workspace / ".env")
        if args.no_langsmith:
            _disable_langsmith()
        elif not args.deterministic:
            _enable_langsmith_defaults()

        compiler = WikiCompiler.from_files(config_path, prompt_path, workspace, enable_reasoning=not args.deterministic)
        result = compiler.run()
        failed = [check for check in result.quality_checks if not check.passed]
        print(f"Processed {result.inputs_processed} inputs.")
        print(f"Wrote {result.pages_written} compiled pages and {result.source_pages_written} source pages.")
        print(
            f"Organizer loop: {result.iterations_run} iteration(s), "
            f"{'stabilized' if result.stabilized else 'max iterations reached'}."
        )
        print(f"Report: {result.report_path}")
        if failed:
            print("Warnings:")
            for check in failed:
                print(f"- {check.name}: {check.details}")
        return 0

    parser.print_help()
    return 2


def _list_models() -> int:
    import os

    try:
        from google import genai
    except ImportError:
        print("google-genai is not installed. Run `python3 -m pip install -e .` in a Python 3.11+ env.")
        return 1

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is not set. Add it to .env or export it in your shell.")
        return 1

    client = genai.Client(api_key=api_key)
    for model in client.models.list():
        methods = getattr(model, "supported_actions", None) or getattr(model, "supported_generation_methods", None) or []
        if "generateContent" in methods:
            print(getattr(model, "name", ""))
    return 0


def _check_langsmith() -> int:
    endpoint = os.environ.get("LANGSMITH_ENDPOINT") or os.environ.get("LANGCHAIN_ENDPOINT") or "https://api.smith.langchain.com"
    project = os.environ.get("LANGSMITH_PROJECT") or os.environ.get("LANGCHAIN_PROJECT") or "<default>"
    workspace_id = os.environ.get("LANGSMITH_WORKSPACE_ID") or os.environ.get("LANGCHAIN_WORKSPACE_ID")
    print(f"endpoint: {endpoint}")
    print(f"project: {project}")
    print(f"workspace_id: {workspace_id or '<not set>'}")
    print(f"api_key_set: {bool(os.environ.get('LANGSMITH_API_KEY') or os.environ.get('LANGCHAIN_API_KEY'))}")
    if workspace_id and (" " in workspace_id or not _looks_like_uuid(workspace_id)):
        print("warning: LANGSMITH_WORKSPACE_ID should be a workspace UUID, not a display name.")

    try:
        from langsmith import Client
    except ImportError:
        print("langsmith is not installed. Run `python3 -m pip install -e .` in a Python 3.11+ env.")
        return 1

    try:
        client = Client()
        projects = list(client.list_projects(limit=5))
    except Exception as exc:
        print(f"auth_check: failed ({type(exc).__name__}: {exc})")
        return 1

    print(f"auth_check: ok, visible_projects={len(projects)}")
    for project_item in projects:
        print(f"- {getattr(project_item, 'name', '<unnamed>')}")
    return 0


def _disable_langsmith() -> None:
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    for key in [
        "LANGSMITH_API_KEY",
        "LANGCHAIN_API_KEY",
        "LANGSMITH_ENDPOINT",
        "LANGCHAIN_ENDPOINT",
        "LANGSMITH_PROJECT",
        "LANGCHAIN_PROJECT",
        "LANGSMITH_WORKSPACE_ID",
        "LANGCHAIN_WORKSPACE_ID",
    ]:
        os.environ.pop(key, None)


def _enable_langsmith_defaults() -> None:
    if not (os.environ.get("LANGSMITH_API_KEY") or os.environ.get("LANGCHAIN_API_KEY")):
        raise RuntimeError("LANGSMITH_API_KEY is required because Organizer model reasoning is always enabled.")
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", "agentsday")
    os.environ.setdefault("LANGCHAIN_PROJECT", os.environ["LANGSMITH_PROJECT"])


def _looks_like_uuid(value: str) -> bool:
    parts = value.split("-")
    return len(parts) == 5 and all(parts)


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
