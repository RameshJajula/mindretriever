from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from collections import Counter

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from graphmind.cache import ArtifactCache
from graphmind.context_budget import FileInfo, FileCategory, TokenBudgetManager
from graphmind.db import EdgeRecord, NodeRecord, RunRecord, SavingsRecord, init_db, persist_extraction, session_scope
from graphmind.pipeline import run_pipeline
from graphmind.prompt_templates import TaskType, PromptTemplateRegistry
from graphmind.retrieval_planner import RetrieverPlanner
from graphmind.token_counter import compute_savings


class RunRequest(BaseModel):
    path: str = Field(default=".")
    full: bool = Field(default=False)


class RunResponse(BaseModel):
    run_id: int
    files: int
    words: int
    nodes: int
    edges: int
    communities: int
    out_dir: str


class RunHistoryItem(BaseModel):
    id: int
    target_path: str
    files: int
    words: int
    nodes: int
    edges: int
    communities: int
    created_at: str


class UploadResponse(BaseModel):
    folder: str
    files_saved: list[str]


class RunGraphResponse(BaseModel):
    run_id: int
    nodes: int
    edges: int
    graph: dict


class ContextPackRequest(BaseModel):
    run_id: int = Field(description="Run ID to use for context")
    task_type: str = Field(default="bug_fix", description="Task type (bug_fix, feature, refactor, test, review, optimize)")
    query: str = Field(description="User's specific request/question")
    token_budget: int = Field(default=8000, description="Token budget for context")
    include_artifacts: bool = Field(default=True, description="Include cached artifacts")


class ContextPackResponse(BaseModel):
    tier: str = Field(description="Retrieval tier used (graph_summary, snippets, full_files)")
    graph_summary: dict | None = None
    code_snippets: list[dict] = Field(default_factory=list)
    full_files: dict[str, str] = Field(default_factory=dict)
    prompt_template: dict | None = None
    cached_artifacts: dict[str, str] = Field(default_factory=dict)
    total_tokens: int = Field(description="Tokens used in context pack")
    recommended_next_steps: list[str] = Field(default_factory=list)
    token_savings: dict = Field(default_factory=dict, description="Before/after token and cost comparison")


class SavingsItem(BaseModel):
    id: int
    run_id: int
    query: str
    task_type: str
    model: str
    full_tokens: int
    pack_tokens: int
    saved_tokens: int
    savings_pct: float
    cost_full_usd: float
    cost_pack_usd: float
    cost_saved_usd: float
    created_at: str


class SavingsSummary(BaseModel):
    total_queries: int
    total_full_tokens: int
    total_pack_tokens: int
    total_saved_tokens: int
    avg_savings_pct: float
    total_cost_full_usd: float
    total_cost_pack_usd: float
    total_cost_saved_usd: float
    note: str


class SavingsResponse(BaseModel):
    summary: SavingsSummary
    records: list[SavingsItem]


app = FastAPI(title="GraphMind Enterprise API", version="0.1.0")
init_db()
_UPLOAD_DIR = Path("graphmind-out") / "uploads"
_UPLOAD_ALLOWED = {".md", ".docx", ".sql"}
_OUT_DIR = Path("graphmind-out")
_ARTIFACT_CACHE = ArtifactCache(_OUT_DIR / "artifacts")
_BUDGET_MANAGER = TokenBudgetManager(total_budget=8000)
_RETRIEVER = RetrieverPlanner(token_budget=8000)
_TEMPLATE_REGISTRY = PromptTemplateRegistry()

_SUPPORTED_CONTEXT_EXT = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".go", ".java", ".sql", ".css", ".scss", ".md", ".txt", ".rst", ".docx"
}


def _category_for_path(path: Path) -> FileCategory:
    suffix = path.suffix.lower()
    if suffix in {".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".go", ".java", ".sql", ".css", ".scss"}:
        return FileCategory.CODE
    if suffix in {".md", ".txt", ".rst", ".docx"}:
        return FileCategory.DOC
    return FileCategory.OTHER


def _load_text_content(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        try:
            from docx import Document

            doc = Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs if p.text)
        except Exception:
            return ""

    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _collect_repo_files(root: Path, limit: int = 300) -> list[Path]:
    files: list[Path] = []
    ignore_dirs = {".git", "node_modules", "venv", "dist", "build"}

    for path in root.rglob("*"):
        if len(files) >= limit:
            break
        if not path.is_file():
            continue
        if any(part in ignore_dirs for part in path.parts):
            continue
        if path.suffix.lower() not in _SUPPORTED_CONTEXT_EXT:
            continue
        files.append(path)

    return files


def _prioritized_files_from_graph(nodes: list[NodeRecord], edges: list[EdgeRecord], max_files: int = 20) -> set[str]:
    counts: Counter[str] = Counter()
    for n in nodes:
        if n.source_file:
            counts[n.source_file] += 1
    for e in edges:
        if e.source_file:
            counts[e.source_file] += 1

    return set(path for path, _ in counts.most_common(max_files))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/run", response_model=RunResponse)
def run_graphmind(request: RunRequest) -> RunResponse:
    target = Path(request.path).resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail="Target path does not exist")

    output = run_pipeline(target, incremental=not request.full)
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

    return RunResponse(
        run_id=row.id,
        files=output.detection.total_files,
        words=output.detection.total_words,
        nodes=output.graph_nodes,
        edges=output.graph_edges,
        communities=output.communities,
        out_dir=output.out_dir,
    )


@app.post("/api/upload", response_model=UploadResponse)
async def upload_files(
    files: list[UploadFile] | None = File(default=None),
    file: UploadFile | None = File(default=None),
) -> UploadResponse:
    # Accept both `files` (preferred) and `file` (legacy/example compatibility).
    incoming_files: list[UploadFile] = list(files or [])
    if file is not None:
        incoming_files.append(file)

    if not incoming_files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch_dir = _UPLOAD_DIR / stamp
    batch_dir.mkdir(parents=True, exist_ok=True)

    saved: list[str] = []
    for upload in incoming_files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in _UPLOAD_ALLOWED:
            continue

        dst = batch_dir / (upload.filename or f"file{suffix}")
        content = await upload.read()
        dst.write_bytes(content)
        saved.append(str(dst))

    if not saved:
        raise HTTPException(status_code=400, detail="No supported files. Allowed: .md, .docx, .sql")

    return UploadResponse(folder=str(batch_dir), files_saved=saved)


@app.get("/api/runs", response_model=list[RunHistoryItem])
def list_runs(limit: int = 20) -> list[RunHistoryItem]:
    with session_scope() as session:
        rows = session.query(RunRecord).order_by(RunRecord.id.desc()).limit(limit).all()
        return [
            RunHistoryItem(
                id=r.id,
                target_path=r.target_path,
                files=r.files,
                words=r.words,
                nodes=r.nodes,
                edges=r.edges,
                communities=r.communities,
                created_at=r.created_at.isoformat(),
            )
            for r in rows
        ]


@app.get("/api/runs/{run_id}/graph", response_model=RunGraphResponse)
def run_graph(run_id: int) -> RunGraphResponse:
    with session_scope() as session:
        run = session.query(RunRecord).filter(RunRecord.id == run_id).first()
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")

        nodes = session.query(NodeRecord).filter(NodeRecord.run_id == run_id).all()
        edges = session.query(EdgeRecord).filter(EdgeRecord.run_id == run_id).all()

    graph_payload = {
        "nodes": [
            {
                "id": n.node_key,
                "label": n.label,
                "kind": n.kind,
                "source_file": n.source_file,
            }
            for n in nodes
        ],
        "edges": [
            {
                "source": e.source_key,
                "target": e.target_key,
                "relation": e.relation,
                "confidence": e.confidence,
                "confidence_score": e.confidence_score,
                "source_file": e.source_file,
            }
            for e in edges
        ],
    }

    return RunGraphResponse(run_id=run_id, nodes=len(nodes), edges=len(edges), graph=json.loads(json.dumps(graph_payload)))


@app.post("/api/context-pack", response_model=ContextPackResponse)
def get_context_pack(request: ContextPackRequest) -> ContextPackResponse:
    """Generate optimized context pack for LLM queries."""
    with session_scope() as session:
        # Load run metadata
        run = session.query(RunRecord).filter(RunRecord.id == request.run_id).first()
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")

        # Reconstruct graph from persisted nodes/edges
        nodes = session.query(NodeRecord).filter(NodeRecord.run_id == request.run_id).all()
        edges = session.query(EdgeRecord).filter(EdgeRecord.run_id == request.run_id).all()

    # Build graph data
    graph_data = {
        "nodes": [
            {"id": n.node_key, "label": n.label, "kind": n.kind}
            for n in nodes
        ],
        "edges": [
            {"source": e.source_key, "target": e.target_key, "relation": e.relation}
            for e in edges
        ],
        "communities": [],
        "top_hubs": [],
    }

    root = Path(run.target_path)
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail="Run target path no longer exists on disk")

    candidate_paths = _collect_repo_files(root)
    if not candidate_paths:
        raise HTTPException(status_code=400, detail="No supported files found in run target path")

    prioritized_abs = _prioritized_files_from_graph(nodes, edges)

    file_infos: list[FileInfo] = []
    available_files_all: dict[str, str] = {}
    changed_files_set: set[str] = set()
    file_metadata: dict[str, dict] = {}

    for p in candidate_paths:
        rel = str(p.relative_to(root)).replace("\\", "/")
        content = _load_text_content(p)
        if not content:
            continue

        available_files_all[rel] = content
        file_metadata[rel] = {"size_bytes": p.stat().st_size}
        file_infos.append(
            FileInfo(
                path=rel,
                category=_category_for_path(p),
                size_bytes=p.stat().st_size,
                changed=False,
                depth=0 if rel in prioritized_abs else 1,
            )
        )
        if rel in prioritized_abs:
            changed_files_set.add(rel)

    if not available_files_all:
        raise HTTPException(status_code=400, detail="Unable to read any supported text content from target path")

    # Fallback so planner always has at least a few candidate files.
    if not changed_files_set:
        changed_files_set = set(list(available_files_all.keys())[:10])

    budget_manager = TokenBudgetManager(total_budget=request.token_budget)
    allocation = budget_manager.allocate(file_infos, changed_files_set)
    selected_paths = {p for p, _ in allocation.allocated_files}
    available_files = {k: v for k, v in available_files_all.items() if k in selected_paths}
    changed_files_set = changed_files_set.intersection(available_files.keys()) or set(list(available_files.keys())[:10])

    # Plan retrieval tiers with request-specific token budget.
    retriever = RetrieverPlanner(token_budget=request.token_budget)
    tiered_context = retriever.plan_retrieval(
        task_type=request.task_type,
        query=request.query,
        graph_data=graph_data,
        changed_files=changed_files_set,
        available_files=available_files,
        file_metadata=file_metadata,
    )

    # Get prompt template
    template = _TEMPLATE_REGISTRY.get_template(
        next((t for t in TaskType if t.value == request.task_type), TaskType.BUG_FIX)
    )

    # Prepare response
    context_snippets = [
        {
            "file_path": s.file_path,
            "start_line": s.start_line,
            "end_line": s.end_line,
            "content": s.content,
            "reason": s.reason,
        }
        for s in tiered_context.code_snippets
    ]

    pack_text = json.dumps(
        {"graph_summary": tiered_context.graph_summary, "code_snippets": context_snippets, "full_files": tiered_context.full_files}
    )
    savings: dict = {}
    try:
        savings = compute_savings(available_files, pack_text)
        with session_scope() as _s:
            _s.add(
                SavingsRecord(
                    run_id=request.run_id,
                    query=request.query[:2000],
                    task_type=request.task_type,
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
        pass

    return ContextPackResponse(
        tier=tiered_context.tier.name.lower(),
        graph_summary=tiered_context.graph_summary,
        code_snippets=context_snippets,
        full_files=tiered_context.full_files,
        prompt_template={
            "task_type": template.task_type.value,
            "name": template.name,
            "sections": template.sections,
            "required_contexts": template.required_contexts,
        } if template else None,
        cached_artifacts={},
        total_tokens=tiered_context.total_tokens,
        recommended_next_steps=_suggest_next_steps(request.task_type, tiered_context.tier.name),
        token_savings=savings,
    )


def _suggest_next_steps(task_type: str, tier: str) -> list[str]:
    """Generate recommended next steps based on task and tier."""
    suggestions = {
        "bug_fix": [
            "Run the failing test to reproduce",
            "Add breakpoints in the shown code",
            "Check git blame for recent changes",
        ],
        "feature": [
            "Review architecture diagram",
            "Check integration points",
            "Plan database migrations if needed",
        ],
        "refactor": [
            "Run full test suite",
            "Measure performance before/after",
            "Update documentation",
        ],
        "test": [
            "Implement unit tests",
            "Add edge case coverage",
            "Check mutation testing",
        ],
    }
    return suggestions.get(task_type, ["Review context and proceed"])


@app.get("/api/savings", response_model=SavingsResponse)
def get_savings(limit: int = 20) -> SavingsResponse:
    """Return per-query token savings records plus a lifetime aggregate summary.

    Every call to /api/context-pack (or the MCP mindretriever_context tool)
    records how many tokens the naïve full-file approach would have used versus
    how many tokens mindretriever actually returned.  This endpoint surfaces
    that data so you can prove cost reduction over time.
    """
    from sqlalchemy import func

    with session_scope() as session:
        rows = (
            session.query(SavingsRecord)
            .order_by(SavingsRecord.id.desc())
            .limit(limit)
            .all()
        )
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
            SavingsItem(
                id=r.id,
                run_id=r.run_id,
                query=r.query,
                task_type=r.task_type,
                model=r.model,
                full_tokens=r.full_tokens,
                pack_tokens=r.pack_tokens,
                saved_tokens=r.saved_tokens,
                savings_pct=r.savings_pct,
                cost_full_usd=r.cost_full_usd,
                cost_pack_usd=r.cost_pack_usd,
                cost_saved_usd=r.cost_saved_usd,
                created_at=r.created_at.isoformat(),
            )
            for r in rows
        ]

        summary = SavingsSummary(
            total_queries=totals.total_queries or 0,
            total_full_tokens=totals.total_full_tokens or 0,
            total_pack_tokens=totals.total_pack_tokens or 0,
            total_saved_tokens=totals.total_saved_tokens or 0,
            avg_savings_pct=round(totals.avg_savings_pct or 0.0, 1),
            total_cost_full_usd=round(totals.total_cost_full or 0.0, 4),
            total_cost_pack_usd=round(totals.total_cost_pack or 0.0, 4),
            total_cost_saved_usd=round(totals.total_cost_saved or 0.0, 4),
            note=(
                "Cost estimates use public GPT-4o input pricing ($2.50/1M tokens). "
                "Actual savings depend on your model and cached input pricing."
            ),
        )

    return SavingsResponse(summary=summary, records=records)


def main() -> None:
    import uvicorn

    uvicorn.run("mindretriever.api:app", host="0.0.0.0", port=8000, reload=False)
