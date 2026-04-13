from __future__ import annotations

import re
from pathlib import Path

from graphmind.models import Edge, ExtractionResult, Node

_CREATE_TABLE_RE = re.compile(r"create\\s+table\\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE)


class SqlSchemaExtractor:
    def supports(self, path: Path) -> bool:
        return path.suffix.lower() == ".sql"

    def extract(self, path: Path) -> ExtractionResult:
        text = path.read_text(encoding="utf-8", errors="ignore")
        result = ExtractionResult()

        file_id = f"sql::{path.stem}"
        result.nodes.append(Node(id=file_id, label=path.name, kind="sql_file", source_file=str(path)))

        for table in _CREATE_TABLE_RE.findall(text):
            table_id = f"table::{table.lower()}"
            result.nodes.append(Node(id=table_id, label=table, kind="table", source_file=str(path)))
            result.edges.append(
                Edge(
                    source=file_id,
                    target=table_id,
                    relation="defines",
                    confidence="EXTRACTED",
                    confidence_score=1.0,
                    source_file=str(path),
                )
            )

        return result
