from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph


def export_graph_json(graph: nx.Graph, communities: dict[int, list[str]], out_path: Path) -> None:
    node_to_community = {
        node: cid
        for cid, nodes in communities.items()
        for node in nodes
    }
    data = json_graph.node_link_data(graph, edges="links")
    for node in data["nodes"]:
        node["community"] = node_to_community.get(node["id"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
