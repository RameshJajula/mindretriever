from __future__ import annotations

from pathlib import Path
from typing import Protocol

from graphmind.models import ExtractionResult


class Extractor(Protocol):
    def supports(self, path: Path) -> bool:
        ...

    def extract(self, path: Path) -> ExtractionResult:
        ...
