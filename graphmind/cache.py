from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_cache(cache_file: Path) -> dict[str, str]:
    if not cache_file.exists():
        return {}
    return json.loads(cache_file.read_text(encoding="utf-8"))


def save_cache(cache_file: Path, data: dict[str, str]) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


def changed_files(paths: list[Path], cache_file: Path) -> tuple[list[Path], dict[str, str]]:
    existing = load_cache(cache_file)
    latest: dict[str, str] = {}
    changed: list[Path] = []

    for p in paths:
        digest = sha256_file(p)
        key = str(p)
        latest[key] = digest
        if existing.get(key) != digest:
            changed.append(p)

    return changed, latest


class ArtifactCache:
    """Cache reusable artifacts like module summaries and API contracts."""
    
    def __init__(self, cache_dir: Path):
        """Initialize artifact cache directory."""
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = cache_dir / "artifacts.json"
    
    def _get_artifact_path(self, artifact_hash: str) -> Path:
        """Get filesystem path for an artifact by hash."""
        return self.cache_dir / f"{artifact_hash}.artifact"
    
    def put(self, artifact_type: str, content: str, source_hash: str) -> str:
        """
        Cache an artifact.
        
        Args:
            artifact_type: Type of artifact (e.g., 'module_summary', 'api_contract')
            content: Artifact content (text, JSON, etc.)
            source_hash: Hash of source file(s) this artifact was generated from
            
        Returns:
            Artifact hash for retrieval
        """
        artifact_hash = hashlib.sha256(f"{artifact_type}:{content}".encode()).hexdigest()[:16]
        artifact_path = self._get_artifact_path(artifact_hash)
        
        # Store artifact
        artifact_path.write_text(content, encoding="utf-8")
        
        # Update index
        index = self._load_index()
        index[artifact_hash] = {
            "type": artifact_type,
            "source_hash": source_hash,
            "size": len(content),
            "compressed": False,
        }
        self._save_index(index)
        
        return artifact_hash
    
    def get(self, artifact_hash: str) -> str | None:
        """Retrieve an artifact by hash."""
        artifact_path = self._get_artifact_path(artifact_hash)
        if artifact_path.exists():
            return artifact_path.read_text(encoding="utf-8")
        return None
    
    def get_by_source(self, source_hash: str, artifact_type: str) -> str | None:
        """
        Retrieve artifact by source hash and type.
        
        Useful for finding existing artifact for a file.
        """
        index = self._load_index()
        for artifact_hash, metadata in index.items():
            if (metadata.get("source_hash") == source_hash and 
                metadata.get("type") == artifact_type):
                return self.get(artifact_hash)
        return None
    
    def invalidate(self, source_hash: str) -> int:
        """
        Invalidate all artifacts from a given source.
        
        Returns:
            Number of artifacts removed
        """
        index = self._load_index()
        removed = 0
        
        for artifact_hash, metadata in list(index.items()):
            if metadata.get("source_hash") == source_hash:
                artifact_path = self._get_artifact_path(artifact_hash)
                if artifact_path.exists():
                    artifact_path.unlink()
                del index[artifact_hash]
                removed += 1
        
        self._save_index(index)
        return removed
    
    def clear(self) -> None:
        """Clear all cached artifacts."""
        for artifact_file in self.cache_dir.glob("*.artifact"):
            artifact_file.unlink()
        self.index_file.unlink(missing_ok=True)
    
    def _load_index(self) -> dict:
        """Load artifact index."""
        if self.index_file.exists():
            return json.loads(self.index_file.read_text(encoding="utf-8"))
        return {}
    
    def _save_index(self, index: dict) -> None:
        """Save artifact index."""
        self.index_file.write_text(
            json.dumps(index, indent=2),
            encoding="utf-8"
        )
