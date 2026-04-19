"""
analysis/risk_scoring.py — Node risk scoring using graph centrality metrics.

Risk model:
  score = w1 * betweenness + w2 * pagerank + w3 * sanctions_proximity + w4 * foreign_funding

Each component is normalized to [0, 1] before weighting.
Nodes with score >= RISK_SCORE_ALERT_THRESHOLD are considered high-risk.
"""

import logging
from dataclasses import dataclass, field

import networkx as nx

from config import (
    BETWEENNESS_ALERT_THRESHOLD,
    RISK_SCORE_ALERT_THRESHOLD,
    SANCTIONS_HOP_LIMIT,
)
from analysis.graph import flag_sanctions_proximity

logger = logging.getLogger(__name__)

# ── Scoring weights (must sum to 1.0) ─────────────────────────────────────────
W_BETWEENNESS = 0.35
W_PAGERANK = 0.25
W_SANCTIONS = 0.30
W_FOREIGN_FUNDING = 0.10


@dataclass
class NodeRisk:
    """Risk assessment for a single node."""
    node_id: str
    label: str
    node_type: str
    score: float                        # composite 0.0–1.0
    betweenness: float = 0.0
    pagerank: float = 0.0
    sanctions_distance: int | None = None  # None = no sanctioned neighbor found
    foreign_funding_ratio: float | None = None
    flags: list[str] = field(default_factory=list)


def _normalize(values: dict[str, float]) -> dict[str, float]:
    """Min-max normalize a dict of floats to [0, 1]."""
    if not values:
        return {}
    vmin = min(values.values())
    vmax = max(values.values())
    span = vmax - vmin or 1.0
    return {k: (v - vmin) / span for k, v in values.items()}


def score_all_nodes(G: nx.DiGraph) -> list[NodeRisk]:
    """
    Compute a composite risk score for every node in the graph.

    Components
    ----------
    - Betweenness Centrality: nodes that act as critical bridges.
    - PageRank: nodes connected to other high-influence nodes.
    - Sanctions Proximity: closeness (in hops) to OFAC-listed entities.
    - Foreign Funding Ratio: for nonprofit nodes, declared foreign political income.

    Returns:
        List of NodeRisk objects sorted by score descending.
    """
    # ── Raw centrality metrics ─────────────────────────────────────────────
    betweenness_raw = nx.betweenness_centrality(G, normalized=True)
    pagerank_raw = nx.pagerank(G, alpha=0.85)

    # ── Sanctions proximity (invert distance: closer = higher risk) ────────
    proximity_map = flag_sanctions_proximity(G, hop_limit=SANCTIONS_HOP_LIMIT)
    sanctions_raw: dict[str, float] = {}
    for node in G.nodes():
        dist = proximity_map.get(node)
        if G.nodes[node].get("sanctioned"):
            sanctions_raw[node] = 1.0          # is sanctioned → max risk
        elif dist is not None:
            # distance 1 → 0.9, distance 2 → 0.5, etc.
            sanctions_raw[node] = 1.0 / dist
        else:
            sanctions_raw[node] = 0.0

    # ── Normalize each metric ──────────────────────────────────────────────
    bet_n = _normalize(betweenness_raw)
    pr_n = _normalize(pagerank_raw)
    san_n = _normalize(sanctions_raw)

    # ── Build NodeRisk objects ─────────────────────────────────────────────
    results: list[NodeRisk] = []
    for node, attrs in G.nodes(data=True):
        bet = bet_n.get(node, 0.0)
        pr = pr_n.get(node, 0.0)
        san = san_n.get(node, 0.0)
        ffr = attrs.get("foreign_funding_ratio") or 0.0

        composite = (
            W_BETWEENNESS * bet
            + W_PAGERANK * pr
            + W_SANCTIONS * san
            + W_FOREIGN_FUNDING * ffr
        )

        flags: list[str] = []
        if bet > BETWEENNESS_ALERT_THRESHOLD:
            flags.append("HIGH_BETWEENNESS_BRIDGE")
        if attrs.get("sanctioned"):
            flags.append("SANCTIONED_ENTITY")
        if proximity_map.get(node, 999) <= SANCTIONS_HOP_LIMIT:
            flags.append(f"WITHIN_{proximity_map[node]}_HOPS_OF_SANCTIONED")
        if ffr >= 0.20:
            flags.append("HIGH_FOREIGN_FUNDING")

        results.append(NodeRisk(
            node_id=node,
            label=attrs.get("label", node),
            node_type=attrs.get("type", "unknown"),
            score=round(composite, 4),
            betweenness=round(betweenness_raw.get(node, 0.0), 6),
            pagerank=round(pagerank_raw.get(node, 0.0), 6),
            sanctions_distance=proximity_map.get(node),
            foreign_funding_ratio=attrs.get("foreign_funding_ratio"),
            flags=flags,
        ))

    return sorted(results, key=lambda r: r.score, reverse=True)


def get_high_risk_nodes(
    scored: list[NodeRisk],
    threshold: float = RISK_SCORE_ALERT_THRESHOLD,
) -> list[NodeRisk]:
    """Return only the nodes above the risk threshold or that are sanctioned."""
    return [n for n in scored if n.score >= threshold or "SANCTIONED_ENTITY" in n.flags]
