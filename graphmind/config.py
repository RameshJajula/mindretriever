from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class GovernancePolicy:
    redact_emails: bool = True
    redact_keys: bool = True
    max_file_mb: int = 5


@dataclass(slots=True)
class GraphMindConfig:
    root: Path
    out_dir: Path = Path("graphmind-out")
    ignore_dirs: set[str] = field(default_factory=lambda: {".git", "node_modules", "venv", "dist", "build"})
    include_ext: set[str] = field(
        default_factory=lambda: {
            ".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".go", ".java", ".sql", ".css", ".scss", ".md", ".txt", ".rst", ".docx", ".pdf"
        }
    )
    policy: GovernancePolicy = field(default_factory=GovernancePolicy)

    @classmethod
    def from_root(cls, root: str | Path) -> "GraphMindConfig":
        return cls(root=Path(root).resolve())
