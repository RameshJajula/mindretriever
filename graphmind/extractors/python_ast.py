from __future__ import annotations

import ast
from pathlib import Path

from graphmind.models import Edge, ExtractionResult, Node


class PythonAstExtractor:
    def supports(self, path: Path) -> bool:
        return path.suffix.lower() == ".py"

    def extract(self, path: Path) -> ExtractionResult:
        text = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(text)
        result = ExtractionResult()

        file_id = f"file::{path.stem}"
        result.nodes.append(Node(id=file_id, label=path.name, kind="file", source_file=str(path)))

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                fn_id = f"fn::{path.stem}::{node.name}"
                result.nodes.append(
                    Node(
                        id=fn_id,
                        label=node.name,
                        kind="function",
                        source_file=str(path),
                        attributes={"line": node.lineno},
                    )
                )
                result.edges.append(
                    Edge(
                        source=file_id,
                        target=fn_id,
                        relation="contains",
                        confidence="EXTRACTED",
                        confidence_score=1.0,
                        source_file=str(path),
                    )
                )

        return result
