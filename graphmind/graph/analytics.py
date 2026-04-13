from __future__ import annotations

import networkx as nx


def detect_communities(graph: nx.Graph) -> dict[int, list[str]]:
    if graph.number_of_nodes() == 0:
        return {}
    if graph.number_of_edges() == 0:
        return {i: [n] for i, n in enumerate(graph.nodes())}

    communities = nx.community.louvain_communities(graph, seed=42)
    return {i: sorted(list(nodes)) for i, nodes in enumerate(communities)}


def top_hubs(graph: nx.Graph, limit: int = 10) -> list[dict[str, int | str]]:
    ranked = sorted(graph.degree, key=lambda x: x[1], reverse=True)
    output: list[dict[str, int | str]] = []
    for node_id, degree in ranked[:limit]:
        output.append({"id": node_id, "label": graph.nodes[node_id].get("label", node_id), "degree": degree})
    return output
