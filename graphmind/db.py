from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from graphmind.models import ExtractionResult

_DB_PATH = Path("graphmind-out") / "graphmind.db"
_ENGINE = create_engine(f"sqlite:///{_DB_PATH}", future=True)
_Session = sessionmaker(bind=_ENGINE, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RunRecord(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_path: Mapped[str] = mapped_column(String(500))
    files: Mapped[int] = mapped_column(Integer)
    words: Mapped[int] = mapped_column(Integer)
    nodes: Mapped[int] = mapped_column(Integer)
    edges: Mapped[int] = mapped_column(Integer)
    communities: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class NodeRecord(Base):
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    node_key: Mapped[str] = mapped_column(String(300), index=True)
    label: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(80))
    source_file: Mapped[str] = mapped_column(String(1000))


class EdgeRecord(Base):
    __tablename__ = "edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    source_key: Mapped[str] = mapped_column(String(300), index=True)
    target_key: Mapped[str] = mapped_column(String(300), index=True)
    relation: Mapped[str] = mapped_column(String(120))
    confidence: Mapped[str] = mapped_column(String(40))
    confidence_score: Mapped[float] = mapped_column(Float)
    source_file: Mapped[str] = mapped_column(String(1000))


class SavingsRecord(Base):
    """Tracks token savings for every mindretriever_context / /api/context-pack call."""

    __tablename__ = "savings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    query: Mapped[str] = mapped_column(Text)
    task_type: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(60))
    # Raw project (naïve full-file approach)
    full_tokens: Mapped[int] = mapped_column(Integer)
    # Mindretriever context pack
    pack_tokens: Mapped[int] = mapped_column(Integer)
    saved_tokens: Mapped[int] = mapped_column(Integer)
    savings_pct: Mapped[float] = mapped_column(Float)
    # Dollar estimates
    cost_full_usd: Mapped[float] = mapped_column(Float)
    cost_pack_usd: Mapped[float] = mapped_column(Float)
    cost_saved_usd: Mapped[float] = mapped_column(Float)
    tiktoken_used: Mapped[bool] = mapped_column(Integer)  # SQLite has no bool column
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)



def init_db() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(_ENGINE)


def persist_extraction(session: Session, run_id: int, extraction: ExtractionResult) -> None:
    for node in extraction.nodes:
        session.add(
            NodeRecord(
                run_id=run_id,
                node_key=node.id,
                label=node.label,
                kind=node.kind,
                source_file=node.source_file,
            )
        )

    for edge in extraction.edges:
        session.add(
            EdgeRecord(
                run_id=run_id,
                source_key=edge.source,
                target_key=edge.target,
                relation=edge.relation,
                confidence=edge.confidence,
                confidence_score=edge.confidence_score,
                source_file=edge.source_file,
            )
        )


@contextmanager
def session_scope() -> Iterator[Session]:
    session = _Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
