"""
analysis/graph.py — Graph construction from ingested data.

Builds a directed NetworkX graph where:
  - Nodes: companies, people (officers), nonprofits
  - Edges: directorship, ownership, funding relationships

Node attributes include 'type', 'jurisdiction', and 'sanctioned' flag.
Edge attributes include 'relation' and 'weight'.
"""

import logging
from typing import Any

import networkx as nx

from ingestion.opencorporates import CompanyProfile, Officer
from ingestion.guidestar import NonprofitProfile

logger = logging.getLogger(__name__)

# ── Node type constants ───────────────────────────────────────────────────────
NODE_COMPANY = "company"
NODE_PERSON = "person"
NODE_NONPROFIT = "nonprofit"

# ── Edge relation constants ───────────────────────────────────────────────────
REL_OFFICER = "officer_of"       # person -> company
REL_FUNDS = "funds"              # nonprofit/company -> nonprofit/company
REL_SUBSIDIARY = "subsidiary_of" # company -> parent company


def build_graph(
    company_profiles: list[CompanyProfile],
    nonprofit_profiles: list[NonprofitProfile] | None = None,
    sanctioned_names: set[str] | None = None,
    ofac_relationships: dict[str, list[str]] | None = None,
) -> nx.DiGraph:
    """
    Construct a directed graph from ingested corporate and nonprofit data.

    Args:
        company_profiles:   List of CompanyProfile objects from OpenCorporates.
        nonprofit_profiles: Optional list of NonprofitProfile from Guidestar.
        sanctioned_names:   Set of normalized OFAC-sanctioned entity names.
        ofac_relationships: Dict of OFAC entity relationships.

    Returns:
        A NetworkX DiGraph ready for analysis.
    """
    G = nx.DiGraph()
    sanctioned = sanctioned_names or set()
    relationships = ofac_relationships or {}

    def _node_id(name: str, jurisdiction: str = "") -> str:
        """Deterministic node identifier."""
        return f"{name.lower().strip()}|{jurisdiction.lower()}"

    def _is_sanctioned(name: str) -> bool:
        normalized = name.lower().strip()
        return any(s in normalized or normalized in s for s in sanctioned)

    # ── Add company nodes and officer edges ───────────────────────────────────
    for profile in company_profiles:
        company_id = _node_id(profile.name, profile.jurisdiction)
        G.add_node(
            company_id,
            label=profile.name,
            type=NODE_COMPANY,
            jurisdiction=profile.jurisdiction,
            status=profile.status,
            sanctioned=_is_sanctioned(profile.name),
        )
        logger.debug("Added company node: %s", company_id)

        for officer in profile.officers:
            if not officer.name:
                continue
            person_id = _node_id(officer.name)
            if not G.has_node(person_id):
                G.add_node(
                    person_id,
                    label=officer.name,
                    type=NODE_PERSON,
                    jurisdiction="",
                    sanctioned=_is_sanctioned(officer.name),
                )
            G.add_edge(
                person_id,
                company_id,
                relation=REL_OFFICER,
                role=officer.role,
                active=not officer.inactive,
            )

    # ── Add nonprofit nodes ───────────────────────────────────────────────────
    for npo in (nonprofit_profiles or []):
        npo_id = _node_id(npo.name)
        G.add_node(
            npo_id,
            label=npo.name,
            type=NODE_NONPROFIT,
            jurisdiction="il",
            foreign_funding_ratio=npo.foreign_funding_ratio,
            sanctioned=_is_sanctioned(npo.name),
        )

    # ── Add OFAC relationships ───────────────────────────────────────────────
    for entity_name, related_entities in relationships.items():
        entity_id = _node_id(entity_name)
        if not G.has_node(entity_id):
            # Add the entity as a node if it doesn't exist
            G.add_node(
                entity_id,
                label=entity_name,
                type=NODE_COMPANY,  # Assume company unless we know otherwise
                jurisdiction="",    # Unknown jurisdiction
                sanctioned=_is_sanctioned(entity_name),
            )

        for related in related_entities:
            related_id = _node_id(related)
            if not G.has_node(related_id):
                G.add_node(
                    related_id,
                    label=related,
                    type=NODE_COMPANY,
                    jurisdiction="",
                    sanctioned=_is_sanctioned(related),
                )
            # Add bidirectional relationship
            G.add_edge(entity_id, related_id, relation="ofac_linked_to", weight=1.0)
            G.add_edge(related_id, entity_id, relation="ofac_linked_to", weight=1.0)

    return G


def find_shared_officers(G: nx.DiGraph) -> dict[str, list[str]]:
    """
    Identify person nodes connected to more than one company node.

    This is a primary indicator of nominee directors / Layering.

    Returns:
        Dict mapping person node IDs to lists of connected company labels.
    """
    shared: dict[str, list[str]] = {}
    for node, attrs in G.nodes(data=True):
        if attrs.get("type") != NODE_PERSON:
            continue
        companies = [
            G.nodes[target]["label"]
            for target in G.successors(node)
            if G.nodes[target].get("type") == NODE_COMPANY
        ]
        if len(companies) > 1:
            shared[attrs["label"]] = companies

    return shared


def find_shell_chains(G: nx.DiGraph, min_length: int = 3) -> list[list[str]]:
    """
    Detect chains of companies connected only through single-officer bridges.

    A chain A -> B -> C -> D where each link is a single person director
    is a classic Shell Chain pattern.

    Args:
        min_length: Minimum chain length to report.

    Returns:
        List of chains, each chain being a list of company node IDs.
    """
    chains = []
    company_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == NODE_COMPANY]

    for start in company_nodes:
        for end in company_nodes:
            if start == end:
                continue
            try:
                path = nx.shortest_path(G, start, end)
                if len(path) >= min_length:
                    # Only report paths that go exclusively through person nodes
                    intermediates = path[1:-1]
                    if all(
                        G.nodes[n].get("type") == NODE_PERSON
                        for n in intermediates
                    ):
                        chains.append(path)
            except nx.NetworkXNoPath:
                pass

    return chains


def flag_sanctions_proximity(
    G: nx.DiGraph,
    hop_limit: int = 2,
) -> dict[str, int]:
    """
    For every non-sanctioned node, compute the shortest hop distance
    to the nearest sanctioned node.

    Args:
        hop_limit: Nodes within this many hops of a sanctioned entity are flagged.

    Returns:
        Dict mapping node IDs to their minimum distance to a sanctioned node.
        Only nodes within hop_limit are included.
    """
    sanctioned_nodes = [n for n, d in G.nodes(data=True) if d.get("sanctioned")]
    proximity: dict[str, int] = {}

    for snode in sanctioned_nodes:
        lengths = nx.single_source_shortest_path_length(G, snode, cutoff=hop_limit)
        for node, dist in lengths.items():
            if node == snode:
                continue
            if node not in proximity or proximity[node] > dist:
                proximity[node] = dist

    return proximity
