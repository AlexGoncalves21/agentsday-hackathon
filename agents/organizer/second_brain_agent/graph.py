from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
WIKI_LINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")

STATE_FILE = ".graph_state.json"
GRAPH_FILE = "graph.json"
DIFF_FILE = "graph_diff.json"
HISTORY_FILE = "graph_history.json"
EXCLUDED_GRAPH_FILES = {"README.md", "changelog.md", "index.md", "open_questions.md", "schema.md"}
EXCLUDED_GRAPH_PREFIXES = ("sources/",)


@dataclass(frozen=True)
class GraphBuildResult:
    graph_path: Path
    diff_path: Path
    state_path: Path
    node_count: int
    edge_count: int
    new_nodes: int
    changed_nodes: int
    new_edges: int
    removed_edges: int


def load_previous_state(brain_dir: Path) -> Dict[str, Any]:
    state_path = brain_dir / STATE_FILE
    if not state_path.exists():
        return {"nodes": {}, "edges": {}}
    try:
        return json.loads(state_path.read_text())
    except json.JSONDecodeError:
        return {"nodes": {}, "edges": {}}


def build_graph_files(
    brain_dir: Path,
    previous_state: Dict[str, Any],
    generated_at: datetime,
) -> GraphBuildResult:
    nodes = _build_nodes(brain_dir, previous_state)
    edges = _build_edges(brain_dir, nodes, previous_state)
    graph = _graph_payload(nodes, edges, generated_at)
    diff = _diff_payload(nodes, edges, previous_state, graph["build_id"], generated_at)
    state = _state_payload(nodes, edges, graph["build_id"], generated_at)

    graph_path = brain_dir / GRAPH_FILE
    diff_path = brain_dir / DIFF_FILE
    state_path = brain_dir / STATE_FILE
    history_path = brain_dir / HISTORY_FILE
    _write_json(graph_path, graph)
    _write_json(diff_path, diff)
    _write_json(state_path, state)
    _append_history(history_path, graph)

    return GraphBuildResult(
        graph_path=graph_path,
        diff_path=diff_path,
        state_path=state_path,
        node_count=len(nodes),
        edge_count=len(edges),
        new_nodes=len(diff["new_nodes"]),
        changed_nodes=len(diff["changed_nodes"]),
        new_edges=len(diff["new_edges"]),
        removed_edges=len(diff["removed_edges"]),
    )


def _build_nodes(brain_dir: Path, previous_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    previous_nodes = previous_state.get("nodes", {})
    nodes = []
    for path in sorted(brain_dir.rglob("*.md")):
        if path.name.startswith("."):
            continue
        rel = _rel(path, brain_dir)
        if _is_excluded_graph_node(rel):
            continue
        text = path.read_text()
        digest = _hash_text(text)
        previous = previous_nodes.get(rel)
        if not previous:
            status = "new"
        elif previous.get("hash") != digest:
            status = "changed"
        else:
            status = "unchanged"
        nodes.append(
            {
                "id": rel,
                "label": _title_for(path, text),
                "type": _type_for(rel),
                "path": f"brain/{rel}",
                "status": status,
                "hash": digest,
                "summary": _summary(text),
            }
        )
    return nodes


def _build_edges(
    brain_dir: Path,
    nodes: List[Dict[str, Any]],
    previous_state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    node_ids = {node["id"] for node in nodes}
    previous_edges = previous_state.get("edges", {})
    seen = set()
    edges = []
    for node_id in sorted(node_ids):
        source_path = brain_dir / node_id
        for target_id, link_type in _extract_internal_links(source_path, brain_dir, node_ids):
            edge_id = f"{node_id}->{target_id}"
            if edge_id in seen:
                continue
            seen.add(edge_id)
            status = "unchanged" if edge_id in previous_edges else "new"
            edges.append(
                {
                    "id": edge_id,
                    "source": node_id,
                    "target": target_id,
                    "type": link_type,
                    "status": status,
                    "hash": _hash_text(edge_id),
                }
            )
    return sorted(edges, key=lambda edge: edge["id"])


def _extract_internal_links(source_path: Path, brain_dir: Path, node_ids: set[str]) -> Iterable[Tuple[str, str]]:
    text = source_path.read_text()
    for raw_target in MARKDOWN_LINK_RE.findall(text):
        target = raw_target.split("#", 1)[0].strip()
        if not target or "://" in target or not target.endswith(".md"):
            continue
        resolved = (source_path.parent / target).resolve()
        if not _is_within(resolved, brain_dir):
            continue
        target_id = _rel(resolved, brain_dir)
        if target_id in node_ids and target_id != _rel(source_path, brain_dir):
            yield target_id, "markdown_link"

    for raw_target in WIKI_LINK_RE.findall(text):
        normalized = raw_target.strip().replace(" ", "-").lower()
        candidates = [node_id for node_id in node_ids if Path(node_id).stem.lower() == normalized]
        for target_id in candidates:
            if target_id != _rel(source_path, brain_dir):
                yield target_id, "wiki_link"


def _graph_payload(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], generated_at: datetime) -> Dict[str, Any]:
    content = {"nodes": nodes, "edges": edges}
    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "build_id": _hash_text(json.dumps(content, sort_keys=True)),
        "nodes": nodes,
        "edges": edges,
    }


def _diff_payload(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    previous_state: Dict[str, Any],
    build_id: str,
    generated_at: datetime,
) -> Dict[str, Any]:
    node_ids = {node["id"] for node in nodes}
    edge_ids = {edge["id"] for edge in edges}
    previous_nodes = set(previous_state.get("nodes", {}).keys())
    previous_edges = set(previous_state.get("edges", {}).keys())
    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "build_id": build_id,
        "previous_build_id": previous_state.get("build_id"),
        "new_nodes": [node["id"] for node in nodes if node["status"] == "new"],
        "changed_nodes": [node["id"] for node in nodes if node["status"] == "changed"],
        "unchanged_nodes": [node["id"] for node in nodes if node["status"] == "unchanged"],
        "removed_nodes": sorted(previous_nodes - node_ids),
        "new_edges": [edge["id"] for edge in edges if edge["status"] == "new"],
        "removed_edges": sorted(previous_edges - edge_ids),
    }


def _state_payload(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    build_id: str,
    generated_at: datetime,
) -> Dict[str, Any]:
    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "build_id": build_id,
        "nodes": {node["id"]: {"hash": node["hash"]} for node in nodes},
        "edges": {edge["id"]: {"hash": edge["hash"]} for edge in edges},
    }


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _append_history(path: Path, graph: Dict[str, Any]) -> None:
    history: Dict[str, Any] = {"graphs": []}
    if path.exists():
        try:
            history = json.loads(path.read_text())
        except json.JSONDecodeError:
            history = {"graphs": []}

    graphs = [
        _sanitize_graph(entry)
        for entry in history.get("graphs", [])
        if entry.get("build_id") != graph["build_id"]
    ]
    graphs.append(graph)
    _write_json(path, {"graphs": graphs[-50:]})


def _sanitize_graph(graph: Dict[str, Any]) -> Dict[str, Any]:
    return {
        **graph,
        "nodes": [node for node in graph.get("nodes", []) if not _is_excluded_graph_node(node.get("id", ""))],
        "edges": [
            edge
            for edge in graph.get("edges", [])
            if not _is_excluded_graph_node(edge.get("source", ""))
            and not _is_excluded_graph_node(edge.get("target", ""))
        ],
    }


def _is_excluded_graph_node(rel_path: str) -> bool:
    return rel_path in EXCLUDED_GRAPH_FILES or rel_path.startswith(EXCLUDED_GRAPH_PREFIXES)


def _title_for(path: Path, text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ").replace("_", " ").title()


def _type_for(rel_path: str) -> str:
    parts = Path(rel_path).parts
    if len(parts) == 1:
        return "core"
    folder = parts[0]
    return {
        "companies": "company",
        "concepts": "concept",
        "events": "event",
        "people": "person",
        "projects": "project",
        "sources": "source",
        "topics": "topic",
        "works": "work",
    }.get(folder, folder.rstrip("s"))


def _summary(text: str, limit: int = 240) -> str:
    compact = " ".join(line for line in text.splitlines() if not line.startswith("#"))
    compact = " ".join(compact.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _is_within(path: Path, parent: Path) -> bool:
    resolved_parent = parent.resolve()
    resolved_path = path.resolve()
    return resolved_path == resolved_parent or resolved_parent in resolved_path.parents


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()
