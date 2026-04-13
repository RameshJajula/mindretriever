from __future__ import annotations

from pathlib import Path

from graphmind.cache import changed_files, save_cache
from graphmind.config import GraphMindConfig
from graphmind.detect import detect
from graphmind.exporters.html_exporter import export_graph_html
from graphmind.exporters.json_exporter import export_graph_json
from graphmind.extractors.registry import ExtractionRegistry
from graphmind.graph.analytics import detect_communities
from graphmind.graph.builder import GraphBuilder
from graphmind.models import PipelineOutput


def run_pipeline(root: str | Path, *, incremental: bool = True) -> PipelineOutput:
    config = GraphMindConfig.from_root(root)
    detection = detect(config)

    all_paths = []
    for bucket in ("code", "document", "paper"):
        all_paths.extend(Path(p) for p in detection.files.get(bucket, []))

    cache_file = config.out_dir / "cache" / "file_hashes.json"
    if incremental:
        targets, latest_hashes = changed_files(all_paths, cache_file)
    else:
        targets = all_paths
        latest_hashes = {str(p): "full-run" for p in all_paths}

    registry = ExtractionRegistry()
    extraction = registry.run(targets)

    builder = GraphBuilder()
    graph = builder.build(extraction)
    communities = detect_communities(graph)

    config.out_dir.mkdir(parents=True, exist_ok=True)
    export_graph_json(graph, communities, config.out_dir / "graph.json")
    export_graph_html(graph, communities, config.out_dir / "graph.html")

    report = _render_report(detection, graph.number_of_nodes(), graph.number_of_edges(), len(communities))
    (config.out_dir / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")

    save_cache(cache_file, latest_hashes)

    return PipelineOutput(
        detection=detection,
        extraction=extraction,
        graph_nodes=graph.number_of_nodes(),
        graph_edges=graph.number_of_edges(),
        communities=len(communities),
        out_dir=str(config.out_dir),
    )


def _render_report(detection, nodes: int, edges: int, communities: int) -> str:
    return "\n".join(
        [
            "# GraphMind Enterprise Report",
            "",
            "## Corpus",
            f"- Files: {detection.total_files}",
            f"- Words: {detection.total_words}",
            f"- Code: {len(detection.files.get('code', []))}",
            f"- Documents: {len(detection.files.get('document', []))}",
            f"- Papers: {len(detection.files.get('paper', []))}",
            "",
            "## Graph",
            f"- Nodes: {nodes}",
            f"- Edges: {edges}",
            f"- Communities: {communities}",
        ]
    )
