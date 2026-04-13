from __future__ import annotations

from pathlib import Path

from .config import GraphMindConfig
from .models import DetectionResult

_DOC_EXT = {".md", ".txt", ".rst"}
_DOCX_EXT = {".docx"}
_CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".go", ".java", ".sql", ".css", ".scss"}
_PAPER_EXT = {".pdf"}


def _bucket_for_suffix(suffix: str) -> str | None:
    s = suffix.lower()
    if s in _CODE_EXT:
        return "code"
    if s in _DOC_EXT:
        return "document"
    if s in _DOCX_EXT:
        return "document"
    if s in _PAPER_EXT:
        return "paper"
    return None


def _count_words(path: Path) -> int:
    if path.suffix.lower() == ".docx":
        try:
            from docx import Document

            doc = Document(str(path))
            return len(" ".join(p.text for p in doc.paragraphs).split())
        except Exception:
            return 0

    try:
        return len(path.read_text(encoding="utf-8", errors="ignore").split())
    except Exception:
        return 0


def detect(config: GraphMindConfig) -> DetectionResult:
    files: dict[str, list[str]] = {"code": [], "document": [], "paper": []}
    total_words = 0

    for path in config.root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in config.ignore_dirs for part in path.parts):
            continue
        if path.suffix.lower() not in config.include_ext:
            continue

        bucket = _bucket_for_suffix(path.suffix)
        if not bucket:
            continue

        files[bucket].append(str(path))
        total_words += _count_words(path)

    total_files = sum(len(v) for v in files.values())
    return DetectionResult(files=files, total_files=total_files, total_words=total_words)
