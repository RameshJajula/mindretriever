"""MCP server exposing mindretriever tools to VS Code Copilot and Cursor.

When registered as an MCP server, the AI assistant automatically calls these
tools to fetch relevant code context before answering your questions — you
just chat normally and context is included behind the scenes.

Run directly:
    python -m graphmind.mcp_server

Or via the installed entry-point:
    mindretriever-mcp
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(
        "ERROR: 'mcp' package not found.\n"
        "Install it with:  pip install 'mindretriever[mcp]'\n"
        "Or directly:      pip install 'mcp[cli]>=1.0'",
        file=sys.stderr,
    )
    sys.exit(1)

from graphmind.context_budget import FileCategory, FileInfo, TokenBudgetManager
from graphmind.db import (
    EdgeRecord,
    NodeRecord,
    RunRecord,
    SavingsRecord,
    init_db,
    persist_extraction,
    session_scope,
)
from graphmind.pipeline import run_pipeline
from graphmind.prompt_templates import TaskType, PromptTemplateRegistry
from graphmind.retrieval_planner import RetrieverPlanner
from graphmind.token_counter import compute_savings

# ---------------------------------------------------------------------------
# Initialise
# ---------------------------------------------------------------------------

init_db()
_TEMPLATE_REGISTRY = PromptTemplateRegistry()

_SUPPORTED_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte",
    ".go", ".java", ".sql", ".css", ".scss",
    ".md", ".txt", ".rst", ".docx",
}
_CODE_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte",
    ".go", ".java", ".sql", ".css", ".scss",
}
_IGNORE_DIRS = {".git", "node_modules", "venv", ".venv", "dist", "build", "__pycache__"}

mcp = FastMCP(
    "mindretriever",
    instructions=(
        "mindretriever builds a knowledge graph of your codebase. "
        "Call `mindretriever_analyze` once per project (or after large changes), "
        "then call `mindretriever_context` before answering any coding question "
        "to get task-focused, token-optimised code snippets and graph context."
    ),
)

# ---------------------------------------------------------------------------
# Private helpers (no FastAPI dependency)
# ---------------------------------------------------------------------------


def _category(path: Path) -> FileCategory:
    suffix = path.suffix.lower()
    if suffix in _CODE_EXT:
        return FileCategory.CODE
    return FileCategory.DOC


def _read_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        try:
            from docx import Document  # type: ignore

            return "\n".join(p.text for p in Document(str(path)).paragraphs if p.text)
        except Exception:
            return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _collect_files(root: Path, limit: int = 300) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*"):
        if len(files) >= limit:
            break
        if not p.is_file():
            continue
        if any(part in _IGNORE_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in _SUPPORTED_EXT:
            files.append(p)
    return files


def _prioritized_files(nodes: list[NodeRecord], edges: list[EdgeRecord], top: int = 20) -> set[str]:
    counts: Counter[str] = Counter()
    for n in nodes:
        if n.source_file:
            counts[n.source_file] += 1
    for e in edges:
        if e.source_file:
            counts[e.source_file] += 1
    return {p for p, _ in counts.most_common(top)}


def _detect_task(query: str) -> str:
    q = query.lower()
    if any(w in q for w in ("bug", "fix", "error", "issue", "crash", "fail", "broken", "exception")):
        return "bug_fix"
    if any(w in q for w in ("test", "spec", "assert", "coverage", "pytest", "unittest")):
        return "test"
    if any(w in q for w in ("refactor", "clean", "restructure", "rewrite", "simplify")):
        return "refactor"
    if any(w in q for w in ("review", "audit", "check", "security", "lint", "vulnerable")):
        return "review"
    if any(w in q for w in ("optim", "perf", "speed", "slow", "fast", "latency", "memory")):
        return "optimize"
    return "feature"


def _next_steps(task_type: str) -> list[str]:
    return {
        "bug_fix": ["Reproduce the bug with the shown test", "Add a regression test once fixed"],
        "feature": ["Review integration points shown in graph", "Plan DB migrations if needed"],
        "refactor": ["Run full test suite after changes", "Update docs to match new structure"],
        "test": ["Add edge-case coverage", "Check mutation testing score"],
        "review": ["Cross-check security hotspots", "Verify dependencies are up to date"],
        "optimize": ["Benchmark before and after", "Profile with cProfile or py-spy"],
    }.get(task_type, ["Review context and proceed"])


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def mindretriever_analyze(path: str = ".") -> str:
    """Analyze a project directory and build its knowledge graph.

    Run this once per project, or after significant code changes.
    Returns a run_id that you pass to mindretriever_context.

    Args:
        path: Absolute or relative path to the project root. Defaults to the
              current working directory (".").
    """
    target = Path(path).resolve()
    if not target.exists():
        return json.dumps({"error": f"Path does not exist: {target}"})

    try:
        output = run_pipeline(target)
        with session_scope() as session:
            row = RunRecord(
                target_path=str(target),
                files=output.detection.total_files,
                words=output.detection.total_words,
                nodes=output.graph_nodes,
                edges=output.graph_edges,
                communities=output.communities,
            )
            session.add(row)
            session.flush()
            persist_extraction(session, row.id, output.extraction)
            run_id = row.id

        return json.dumps(
            {
                "run_id": run_id,
                "path": str(target),
                "files_analyzed": output.detection.total_files,
                "nodes": output.graph_nodes,
                "edges": output.graph_edges,
                "communities": output.communities,
                "tip": f"Now call mindretriever_context(query=..., run_id={run_id}) before answering coding questions.",
            },
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)})


@mcp.tool()
def mindretriever_context(
    query: str,
    task_type: str = "auto",
    run_id: Optional[int] = None,
    token_budget: int = 8000,
) -> str:
    """Get a token-optimised context pack for a coding question.

    Call this BEFORE answering any coding question. It returns relevant code
    snippets, graph structure, a task-specific prompt template, and suggested
    next steps — keeping the context focused and under the token budget.

    Args:
        query: The user's question or task (e.g. "why does login fail with OAuth?").
        task_type: One of bug_fix | feature | refactor | test | review | optimize.
                   Use "auto" (default) to detect automatically from the query text.
        run_id: Run ID from mindretriever_analyze. Omit to use the most recent run.
        token_budget: Maximum tokens for the context pack (default: 8000).
    """
    if task_type == "auto":
        task_type = _detect_task(query)

    with session_scope() as session:
        if run_id is None:
            run = session.query(RunRecord).order_by(RunRecord.id.desc()).first()
        else:
            run = session.query(RunRecord).filter(RunRecord.id == run_id).first()

        if run is None:
            return json.dumps(
                {
                    "error": (
                        "No analysis run found. "
                        "Call mindretriever_analyze(path='<your project root>') first."
                    )
                }
            )

        nodes = session.query(NodeRecord).filter(NodeRecord.run_id == run.id).all()
        edges = session.query(EdgeRecord).filter(EdgeRecord.run_id == run.id).all()
        actual_run_id = run.id
        target_path = run.target_path

    graph_data = {
        "nodes": [{"id": n.node_key, "label": n.label, "kind": n.kind} for n in nodes],
        "edges": [{"source": e.source_key, "target": e.target_key, "relation": e.relation} for e in edges],
        "communities": [],
        "top_hubs": [],
    }

    root = Path(target_path)
    if not root.exists():
        return json.dumps({"error": f"Project path no longer exists on disk: {target_path}"})

    prioritized = _prioritized_files(nodes, edges)
    file_infos: list[FileInfo] = []
    all_files: dict[str, str] = {}
    metadata: dict[str, dict] = {}
    changed_set: set[str] = set()

    for p in _collect_files(root):
        rel = str(p.relative_to(root)).replace("\\", "/")
        content = _read_text(p)
        if not content:
            continue
        all_files[rel] = content
        metadata[rel] = {"size_bytes": p.stat().st_size}
        file_infos.append(
            FileInfo(
                path=rel,
                category=_category(p),
                size_bytes=p.stat().st_size,
                changed=False,
                depth=0 if rel in prioritized else 1,
            )
        )
        if rel in prioritized:
            changed_set.add(rel)

    if not all_files:
        return json.dumps({"error": "No supported files found at the project path."})

    if not changed_set:
        changed_set = set(list(all_files.keys())[:10])

    allocation = TokenBudgetManager(total_budget=token_budget).allocate(file_infos, changed_set)
    selected = {p for p, _ in allocation.allocated_files}
    available = {k: v for k, v in all_files.items() if k in selected}
    changed_set = (changed_set & available.keys()) or set(list(available.keys())[:10])

    ctx = RetrieverPlanner(token_budget=token_budget).plan_retrieval(
        task_type=task_type,
        query=query,
        graph_data=graph_data,
        changed_files=changed_set,
        available_files=available,
        file_metadata=metadata,
    )

    template = _TEMPLATE_REGISTRY.get_template(
        next((t for t in TaskType if t.value == task_type), TaskType.BUG_FIX)
    )

    # Build the pack text once so we can count its tokens for savings tracking.
    snippets_data = [
        {
            "file": s.file_path,
            "lines": f"{s.start_line}-{s.end_line}",
            "reason": s.reason,
            "content": s.content,
        }
        for s in ctx.code_snippets
    ]
    pack_text = json.dumps(
        {
            "graph_summary": ctx.graph_summary,
            "code_snippets": snippets_data,
            "full_files": ctx.full_files,
        }
    )

    # Compute and persist token savings (best-effort; never block the response).
    try:
        savings = compute_savings(all_files, pack_text)
        with session_scope() as _s:
            _s.add(
                SavingsRecord(
                    run_id=actual_run_id,
                    query=query[:2000],
                    task_type=task_type,
                    model=savings["model"],
                    full_tokens=savings["full_tokens"],
                    pack_tokens=savings["pack_tokens"],
                    saved_tokens=savings["saved_tokens"],
                    savings_pct=savings["savings_pct"],
                    cost_full_usd=savings["cost_full_usd"],
                    cost_pack_usd=savings["cost_pack_usd"],
                    cost_saved_usd=savings["cost_saved_usd"],
                    tiktoken_used=int(savings["tiktoken_used"]),
                )
            )
    except Exception:
        savings = {}

    return json.dumps(
        {
            "run_id": actual_run_id,
            "task_type": task_type,
            "retrieval_tier": ctx.tier.name.lower(),
            "total_tokens": ctx.total_tokens,
            "graph_summary": ctx.graph_summary,
            "code_snippets": snippets_data,
            "full_files": ctx.full_files,
            "prompt_template": (
                {"name": template.name, "sections": template.sections}
                if template
                else None
            ),
            "next_steps": _next_steps(task_type),
            "token_savings": savings,
        },
        indent=2,
    )


@mcp.tool()
def mindretriever_runs(limit: int = 5) -> str:
    """List recent project analysis runs.

    Args:
        limit: Maximum number of runs to return (default: 5).
    """
    with session_scope() as session:
        rows = session.query(RunRecord).order_by(RunRecord.id.desc()).limit(limit).all()
        return json.dumps(
            [
                {
                    "run_id": r.id,
                    "path": r.target_path,
                    "files": r.files,
                    "nodes": r.nodes,
                    "edges": r.edges,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ],
            indent=2,
        )


@mcp.tool()
def mindretriever_savings(limit: int = 20) -> str:
    """Show proof of token and cost savings from using mindretriever.

    Returns per-query savings records plus a lifetime aggregate summary so
    you can see exactly how much money and how many tokens were saved compared
    to sending the full project to the LLM every time.

    Args:
        limit: Number of recent records to include (default: 20).
    """
    with session_scope() as session:
        rows = (
            session.query(SavingsRecord)
            .order_by(SavingsRecord.id.desc())
            .limit(limit)
            .all()
        )
        # Aggregate totals across ALL records (not just the paged limit).
        from sqlalchemy import func  # local import to keep top-level clean

        totals = session.query(
            func.count(SavingsRecord.id).label("total_queries"),
            func.sum(SavingsRecord.full_tokens).label("total_full_tokens"),
            func.sum(SavingsRecord.pack_tokens).label("total_pack_tokens"),
            func.sum(SavingsRecord.saved_tokens).label("total_saved_tokens"),
            func.avg(SavingsRecord.savings_pct).label("avg_savings_pct"),
            func.sum(SavingsRecord.cost_full_usd).label("total_cost_full"),
            func.sum(SavingsRecord.cost_pack_usd).label("total_cost_pack"),
            func.sum(SavingsRecord.cost_saved_usd).label("total_cost_saved"),
        ).one()

        records = [
            {
                "id": r.id,
                "query": r.query,
                "task_type": r.task_type,
                "model": r.model,
                "full_tokens": r.full_tokens,
                "pack_tokens": r.pack_tokens,
                "saved_tokens": r.saved_tokens,
                "savings_pct": r.savings_pct,
                "cost_full_usd": r.cost_full_usd,
                "cost_pack_usd": r.cost_pack_usd,
                "cost_saved_usd": r.cost_saved_usd,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]

        summary = {
            "total_queries": totals.total_queries or 0,
            "total_full_tokens": totals.total_full_tokens or 0,
            "total_pack_tokens": totals.total_pack_tokens or 0,
            "total_saved_tokens": totals.total_saved_tokens or 0,
            "avg_savings_pct": round(totals.avg_savings_pct or 0.0, 1),
            "total_cost_full_usd": round(totals.total_cost_full or 0.0, 4),
            "total_cost_pack_usd": round(totals.total_cost_pack or 0.0, 4),
            "total_cost_saved_usd": round(totals.total_cost_saved or 0.0, 4),
            "note": (
                "Cost estimates use public GPT-4o input pricing ($2.50/1M tokens). "
                "Actual savings depend on your model and whether you use cached inputs."
            ),
        }

    return json.dumps({"summary": summary, "records": records}, indent=2)


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
