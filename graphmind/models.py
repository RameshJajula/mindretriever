from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Node:
    id: str
    label: str
    kind: str
    source_file: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Edge:
    source: str
    target: str
    relation: str
    confidence: str
    confidence_score: float
    source_file: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExtractionResult:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)


@dataclass(slots=True)
class DetectionResult:
    files: dict[str, list[str]]
    total_files: int
    total_words: int


@dataclass(slots=True)
class PipelineOutput:
    detection: DetectionResult
    extraction: ExtractionResult
    graph_nodes: int
    graph_edges: int
    communities: int
    out_dir: str


@dataclass(slots=True)
class ContextSnippet:
    """A code snippet for LLM context."""
    file_path: str
    start_line: int
    end_line: int
    content: str
    reason: str


@dataclass(slots=True)
class ContextPack:
    """Optimized context for LLM queries."""
    tier: str  # "graph_summary", "snippets", "full_files"
    graph_summary: dict[str, Any] | None = None
    code_snippets: list[ContextSnippet] = field(default_factory=list)
    full_files: dict[str, str] = field(default_factory=dict)
    prompt_template: dict[str, Any] | None = None
    cached_artifacts: dict[str, str] = field(default_factory=dict)
    total_tokens: int = 0
    recommended_actions: list[str] = field(default_factory=list)
