from __future__ import annotations

import json
from pathlib import Path

import networkx as nx


def export_graph_html(graph: nx.Graph, communities: dict[int, list[str]], out_path: Path) -> None:
    nodes = [
        {
            "id": n,
            "label": data.get("label", n),
            "kind": data.get("kind", "unknown"),
            "community": _community_for(n, communities),
            "degree": graph.degree(n),
        }
        for n, data in graph.nodes(data=True)
    ]
    edges = [
        {
            "source": u,
            "target": v,
            "relation": data.get("relation", "related_to"),
            "confidence": data.get("confidence", "EXTRACTED"),
        }
        for u, v, data in graph.edges(data=True)
    ]

    html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>GraphMind Enterprise</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 0; padding: 24px; background: #f6f8fb; color: #202430; }}
    .wrap {{ max-width: 1100px; margin: 0 auto; }}
    .card {{ background: #ffffff; border: 1px solid #dde3ef; border-radius: 12px; padding: 16px; margin-bottom: 16px; }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #f2f5fb; border-radius: 8px; padding: 12px; }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <h1>GraphMind Enterprise Report</h1>
    <div class=\"card\">
      <h2>Summary</h2>
      <p>Nodes: {graph.number_of_nodes()} | Edges: {graph.number_of_edges()} | Communities: {len(communities)}</p>
    </div>
    <div class=\"card\">
      <h2>Nodes</h2>
      <pre>{json.dumps(nodes, indent=2)}</pre>
    </div>
    <div class=\"card\">
      <h2>Edges</h2>
      <pre>{json.dumps(edges, indent=2)}</pre>
    </div>
  </div>
</body>
</html>
"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")


def _community_for(node_id: str, communities: dict[int, list[str]]) -> int | None:
    for cid, nodes in communities.items():
        if node_id in nodes:
            return cid
    return None
