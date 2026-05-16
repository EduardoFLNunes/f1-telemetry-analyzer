"""
Motorsport Knowledge Graph
Relational database for linking drivers, corners, mistakes, and setups.
"""
import networkx as nx
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class MotorsportKnowledgeGraph:
    """
    Builds a semantic graph of motorsport intelligence.
    Links: Driver -> Corner -> CommonMistake -> SetupChange.
    """
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_driver_node(self, driver_id: str, traits: Dict[str, Any]):
        self.graph.add_node(driver_id, type="driver", **traits)

    def add_corner_node(self, track_id: str, corner_id: int, archetype: str):
        node_id = f"{track_id}_T{corner_id}"
        self.graph.add_node(node_id, type="corner", archetype=archetype)

    def link_mistake_to_corner(self, driver_id: str, corner_id: str, mistake_type: str, count: int = 1):
        """Creates or updates a 'MISTAKE_AT' relationship."""
        edge_id = (driver_id, corner_id)
        if self.graph.has_edge(*edge_id):
            self.graph[edge_id[0]][edge_id[1]]["count"] += count
        else:
            self.graph.add_edge(*edge_id, type="MISTAKE_AT", mistake=mistake_type, count=count)

    def query_driver_weaknesses(self, driver_id: str) -> List[Dict[str, Any]]:
        """Finds recurring mistakes and problematic corners for a driver."""
        if driver_id not in self.graph: return []
        
        weaknesses = []
        for neighbor in self.graph.neighbors(driver_id):
            edge = self.graph[driver_id][neighbor]
            if edge.get("type") == "MISTAKE_AT" and edge.get("count", 0) > 3:
                weaknesses.append({
                    "corner": neighbor,
                    "mistake": edge["mistake"],
                    "count": edge["count"]
                })
        return weaknesses

    def save_graph(self, path: str):
        """Persists the graph to disk (GraphML or JSON)."""
        nx.write_graphml(self.graph, path)
        logger.info(f"Knowledge Graph saved to {path}")
