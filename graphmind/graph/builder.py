from __future__ import annotations

import networkx as nx

from graphmind.models import ExtractionResult


class GraphBuilder:
    def build(self, extraction: ExtractionResult) -> nx.Graph:
        graph = nx.Graph()

        for node in extraction.nodes:
            graph.add_node(
                node.id,
                label=node.label,
                kind=node.kind,
                source_file=node.source_file,
                **node.attributes,
            )

        for edge in extraction.edges:
            if edge.source not in graph or edge.target not in graph:
                continue
            graph.add_edge(
                edge.source,
                edge.target,
                relation=edge.relation,
                confidence=edge.confidence,
                confidence_score=edge.confidence_score,
                source_file=edge.source_file,
                **edge.attributes,
            )

        return graph
