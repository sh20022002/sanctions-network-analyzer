"""
export/neo4j_export.py — Write the graph to a Neo4j instance.

Uses the official neo4j Python driver. Run Neo4j locally (Docker is easiest):

    docker run -p 7474:7474 -p 7687:7687 \
        -e NEO4J_AUTH=neo4j/yourpassword \
        neo4j:5

Then open http://localhost:7474 for the browser UI or connect Bloom/Linkurious.

Cypher schema created:
  (:Company  {id, name, jurisdiction, status, sanctioned})
  (:Person   {id, name, sanctioned})
  (:Nonprofit{id, name, foreign_funding_ratio, sanctioned})
  [:OFFICER_OF {role, active}]
  [:FUNDS       {amount}]
"""

import logging
from typing import Any

import networkx as nx

from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False
    logger.warning("neo4j package not installed. Run: pip install neo4j")


# ── Cypher templates ──────────────────────────────────────────────────────────

_MERGE_NODE = """
MERGE (n:{label} {{id: $id}})
SET n += $props
"""

_MERGE_EDGE = """
MATCH (a {{id: $src_id}})
MATCH (b {{id: $dst_id}})
MERGE (a)-[r:{rel_type}]->(b)
SET r += $props
"""


def _node_label(node_type: str) -> str:
    """Map internal node type string to Neo4j label."""
    return {
        "company": "Company",
        "person": "Person",
        "nonprofit": "Nonprofit",
    }.get(node_type, "Entity")


def _rel_label(relation: str) -> str:
    """Map internal relation string to Neo4j relationship type."""
    return relation.upper().replace(" ", "_")


class Neo4jExporter:
    """Writes a NetworkX DiGraph to Neo4j via Bolt."""

    def __init__(self):
        if not _NEO4J_AVAILABLE:
            raise ImportError("Install the neo4j package: pip install neo4j")
        self._driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
        )

    def close(self):
        self._driver.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _run(self, session: Any, query: str, **params):
        session.run(query, **params)

    def clear_database(self, session: Any):
        """Delete all nodes and relationships (use with care)."""
        session.run("MATCH (n) DETACH DELETE n")
        logger.warning("Neo4j database cleared.")

    def export_graph(self, G: nx.DiGraph, clear_first: bool = False):
        """
        Export all nodes and edges from the NetworkX graph to Neo4j.

        Args:
            G:           The graph to export.
            clear_first: Wipe the database before importing (default: False).
        """
        with self._driver.session() as session:
            if clear_first:
                self.clear_database(session)

            # ── Nodes ──────────────────────────────────────────────────────
            for node_id, attrs in G.nodes(data=True):
                label = _node_label(attrs.get("type", "entity"))
                props = {k: v for k, v in attrs.items() if v is not None}
                props["id"] = node_id
                session.run(
                    _MERGE_NODE.format(label=label),
                    id=node_id,
                    props=props,
                )

            logger.info("Exported %d nodes to Neo4j.", G.number_of_nodes())

            # ── Edges ──────────────────────────────────────────────────────
            for src, dst, edge_attrs in G.edges(data=True):
                rel = _rel_label(edge_attrs.get("relation", "related_to"))
                props = {k: v for k, v in edge_attrs.items() if k != "relation" and v is not None}
                session.run(
                    _MERGE_EDGE.format(rel_type=rel),
                    src_id=src,
                    dst_id=dst,
                    props=props,
                )

            logger.info("Exported %d edges to Neo4j.", G.number_of_edges())

    def add_risk_scores(self, scored_nodes: list):
        """
        Attach composite risk scores to existing Neo4j nodes.

        Args:
            scored_nodes: List of NodeRisk objects from risk_scoring.score_all_nodes().
        """
        with self._driver.session() as session:
            for risk in scored_nodes:
                session.run(
                    "MATCH (n {id: $id}) SET n.risk_score = $score, n.flags = $flags",
                    id=risk.node_id,
                    score=risk.score,
                    flags=risk.flags,
                )
        logger.info("Risk scores written to Neo4j for %d nodes.", len(scored_nodes))
