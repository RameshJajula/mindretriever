from __future__ import annotations

from pathlib import Path

from .docx_semantic import DocxSemanticExtractor
from .python_ast import PythonAstExtractor
from .sql_schema import SqlSchemaExtractor
from .text_semantic import TextSemanticExtractor
from .typescript_semantic import TypeScriptSemanticExtractor
from .vue_svelte_semantic import VueSvelteSemanticExtractor
from graphmind.models import ExtractionResult


class ExtractionRegistry:
    def __init__(self) -> None:
        self._extractors = [
            PythonAstExtractor(),
            SqlSchemaExtractor(),
            TypeScriptSemanticExtractor(),
            VueSvelteSemanticExtractor(),
            TextSemanticExtractor(),
            DocxSemanticExtractor(),
        ]

    def run(self, paths: list[Path]) -> ExtractionResult:
        merged = ExtractionResult()
        seen_nodes: set[str] = set()
        seen_edges: set[tuple[str, str, str, str]] = set()

        for path in paths:
            for extractor in self._extractors:
                if not extractor.supports(path):
                    continue
                part = extractor.extract(path)
                for node in part.nodes:
                    if node.id in seen_nodes:
                        continue
                    merged.nodes.append(node)
                    seen_nodes.add(node.id)
                for edge in part.edges:
                    key = (edge.source, edge.target, edge.relation, edge.source_file)
                    if key in seen_edges:
                        continue
                    merged.edges.append(edge)
                    seen_edges.add(key)
                break

        return merged
