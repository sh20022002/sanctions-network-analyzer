"""
tests/test_graph.py — Unit tests for graph construction and pattern detection.

Run with: pytest tests/
"""

import pytest
import networkx as nx

from analysis.graph import (
    build_graph,
    find_shared_officers,
    find_shell_chains,
    flag_sanctions_proximity,
    NODE_COMPANY, NODE_PERSON,
)
from ingestion.opencorporates import CompanyProfile, Officer


# ── Fixtures ──────────────────────────────────────────────────────────────────

def make_profile(name: str, jur: str, officers: list[tuple[str, str]]) -> CompanyProfile:
    return CompanyProfile(
        name=name,
        jurisdiction=jur,
        company_number="12345",
        status="active",
        registered_address=None,
        incorporation_date=None,
        officers=[
            Officer(name=n, role=r, company_number="12345", jurisdiction=jur)
            for n, r in officers
        ],
    )


@pytest.fixture
def simple_profiles():
    return [
        make_profile("Alpha Corp", "gb", [("John Smith", "director"), ("Jane Doe", "secretary")]),
        make_profile("Beta LLC",   "us", [("John Smith", "director"), ("Bob Brown", "director")]),
        make_profile("Gamma SA",   "fr", [("Bob Brown", "director")]),
    ]


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_graph_node_count(simple_profiles):
    G = build_graph(simple_profiles)
    companies = [n for n, d in G.nodes(data=True) if d.get("type") == NODE_COMPANY]
    people    = [n for n, d in G.nodes(data=True) if d.get("type") == NODE_PERSON]
    assert len(companies) == 3
    assert len(people) == 3  # John Smith, Jane Doe, Bob Brown


def test_shared_officers_detected(simple_profiles):
    G = build_graph(simple_profiles)
    shared = find_shared_officers(G)
    # John Smith appears in Alpha Corp and Beta LLC
    assert "john smith" in shared
    assert len(shared["john smith"]) == 2
    # Bob Brown appears in Beta LLC and Gamma SA
    assert "bob brown" in shared


def test_sanctioned_flag(simple_profiles):
    G = build_graph(simple_profiles, sanctioned_names={"alpha corp"})
    node = next(
        n for n, d in G.nodes(data=True)
        if d.get("label", "").lower() == "alpha corp"
    )
    assert G.nodes[node]["sanctioned"] is True


def test_sanctions_proximity(simple_profiles):
    G = build_graph(simple_profiles, sanctioned_names={"alpha corp"})
    proximity = flag_sanctions_proximity(G, hop_limit=2)
    # John Smith is directly connected to Alpha Corp (distance 1 via edge direction)
    # (from person -> company, so BFS from sanctioned company reaches person in 1 hop
    #  only if we use undirected traversal — verify the actual graph direction)
    assert len(proximity) > 0


def test_no_false_shared_officer():
    profiles = [
        make_profile("Solo Corp", "gb", [("Unique Person", "director")]),
    ]
    G = build_graph(profiles)
    shared = find_shared_officers(G)
    assert "unique person" not in shared
