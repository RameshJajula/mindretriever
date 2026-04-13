from __future__ import annotations

import re
from pathlib import Path

from graphmind.models import Edge, ExtractionResult, Node
from graphmind.security import redact_text


_STYLE_EXT = {".css", ".scss"}
_CSS_SELECTOR_RE = re.compile(r"^\s*([.#][A-Za-z_][A-Za-z0-9_-]*)\s*\{")


class TextSemanticExtractor:
    def __init__(self, *, redact_emails: bool = True, redact_keys: bool = True) -> None:
        self.redact_emails = redact_emails
        self.redact_keys = redact_keys

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in {".md", ".txt", ".rst", ".css", ".scss"}

    def extract(self, path: Path) -> ExtractionResult:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        text = redact_text(raw, redact_emails=self.redact_emails, redact_keys=self.redact_keys)
        result = ExtractionResult()
        seen_nodes: set[str] = set()
        seen_edges: set[tuple[str, str, str]] = set()

        file_id = f"doc::{path.stem}"
        kind = "document" if path.suffix.lower() in {".md", ".txt", ".rst"} else "code_file"
        result.nodes.append(Node(id=file_id, label=path.name, kind=kind, source_file=str(path)))
        seen_nodes.add(file_id)

        for line_num, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                concept = line.lstrip("#").strip()
                concept_id = f"concept::{path.stem}::{concept.lower().replace(' ', '_')}"
                if concept_id not in seen_nodes:
                    result.nodes.append(
                        Node(
                            id=concept_id,
                            label=concept,
                            kind="concept",
                            source_file=str(path),
                            attributes={"line": line_num},
                        )
                    )
                    seen_nodes.add(concept_id)

                edge_key = (file_id, concept_id, "describes")
                if edge_key not in seen_edges:
                    result.edges.append(
                        Edge(
                            source=file_id,
                            target=concept_id,
                            relation="describes",
                            confidence="EXTRACTED",
                            confidence_score=1.0,
                            source_file=str(path),
                        )
                    )
                    seen_edges.add(edge_key)

            if path.suffix.lower() in _STYLE_EXT:
                selector_match = _CSS_SELECTOR_RE.match(line)
                if selector_match:
                    selector = selector_match.group(1)
                    selector_id = f"selector::{path.stem}::{selector.lower()}"
                    if selector_id not in seen_nodes:
                        result.nodes.append(
                            Node(
                                id=selector_id,
                                label=selector,
                                kind="selector",
                                source_file=str(path),
                                attributes={"line": line_num},
                            )
                        )
                        seen_nodes.add(selector_id)
                    edge_key = (file_id, selector_id, "contains")
                    if edge_key not in seen_edges:
                        result.edges.append(
                            Edge(
                                source=file_id,
                                target=selector_id,
                                relation="contains",
                                confidence="EXTRACTED",
                                confidence_score=1.0,
                                source_file=str(path),
                            )
                        )
                        seen_edges.add(edge_key)

        return result
