from __future__ import annotations

from pathlib import Path

from graphmind.models import Edge, ExtractionResult, Node
from graphmind.security import redact_text


class DocxSemanticExtractor:
    def __init__(self, *, redact_emails: bool = True, redact_keys: bool = True) -> None:
        self.redact_emails = redact_emails
        self.redact_keys = redact_keys

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() == ".docx"

    def extract(self, path: Path) -> ExtractionResult:
        result = ExtractionResult()
        file_id = f"doc::{path.stem}"
        result.nodes.append(Node(id=file_id, label=path.name, kind="document", source_file=str(path)))

        try:
            from docx import Document

            doc = Document(str(path))
            for idx, para in enumerate(doc.paragraphs, start=1):
                text = redact_text(
                    para.text.strip(),
                    redact_emails=self.redact_emails,
                    redact_keys=self.redact_keys,
                )
                if not text:
                    continue

                if para.style and para.style.name.lower().startswith("heading"):
                    concept_id = f"concept::{path.stem}::{idx}"
                    result.nodes.append(
                        Node(
                            id=concept_id,
                            label=text[:120],
                            kind="concept",
                            source_file=str(path),
                            attributes={"paragraph": idx},
                        )
                    )
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
        except Exception:
            # Keep document node even if parsing fails.
            return result

        return result
