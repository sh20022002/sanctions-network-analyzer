"""
main.py — CLI entry point for the Sanctions Network Analyzer.

Usage:
    python main.py --targets data/targets.csv
    python main.py --targets data/targets.csv --neo4j --clear-db
    python main.py --targets data/targets.csv --output data/results.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

from ingestion.opencorporates import bulk_build_profiles
from ingestion.ofac import get_sanctioned_names
from analysis.graph import build_graph, find_shared_officers, find_shell_chains
from analysis.risk_scoring import score_all_nodes, get_high_risk_nodes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


def load_targets(csv_path: str) -> list[tuple[str, str]]:
    """
    Load company targets from a CSV file.

    Expected columns: 'name', 'jurisdiction'
    The 'jurisdiction' column is optional (defaults to empty string).

    Args:
        csv_path: Path to the CSV file.

    Returns:
        List of (company_name, jurisdiction_code) tuples.
    """
    df = pd.read_csv(csv_path)
    if "name" not in df.columns:
        raise ValueError("CSV must have a 'name' column.")
    jur_col = "jurisdiction" if "jurisdiction" in df.columns else None
    targets = []
    for _, row in df.iterrows():
        name = str(row["name"]).strip()
        jur = str(row[jur_col]).strip() if jur_col else ""
        targets.append((name, jur))
    return targets


def run(args: argparse.Namespace):
    # ── 1. Load targets ────────────────────────────────────────────────────
    logger.info("Loading targets from %s", args.targets)
    targets = load_targets(args.targets)
    logger.info("Loaded %d targets.", len(targets))

    # ── 2. Fetch OFAC sanctions list ───────────────────────────────────────
    logger.info("Fetching OFAC SDN list…")
    sanctioned = get_sanctioned_names()
    logger.info("Loaded %d sanctioned entity names.", len(sanctioned))

    # ── 3. Fetch company profiles from OpenCorporates ──────────────────────
    logger.info("Fetching company profiles from OpenCorporates…")
    profiles = bulk_build_profiles(targets)
    logger.info("Retrieved %d profiles.", len(profiles))

    # ── 4. Build graph ─────────────────────────────────────────────────────
    logger.info("Building network graph…")
    G = build_graph(profiles, sanctioned_names=sanctioned)
    logger.info(
        "Graph: %d nodes, %d edges.", G.number_of_nodes(), G.number_of_edges()
    )

    # ── 5. Pattern detection ───────────────────────────────────────────────
    shared = find_shared_officers(G)
    chains = find_shell_chains(G, min_length=3)

    logger.info("=== Shared Officers (Layering indicator) ===")
    for person, companies in shared.items():
        logger.info("  %s  ←→  %s", person, ", ".join(companies))

    logger.info("=== Shell Chains (≥3 hops) ===")
    for chain in chains:
        labels = [G.nodes[n].get("label", n) for n in chain]
        logger.info("  %s", " → ".join(labels))

    # ── 6. Risk scoring ────────────────────────────────────────────────────
    logger.info("Scoring nodes…")
    scored = score_all_nodes(G)
    high_risk = get_high_risk_nodes(scored)

    logger.info("=== High-Risk Nodes ===")
    for node in high_risk:
        logger.info(
            "  [%.2f] %s (%s)  flags: %s",
            node.score, node.label, node.node_type, node.flags,
        )

    # ── 7. Neo4j export (optional) ─────────────────────────────────────────
    if args.neo4j:
        from export.neo4j_export import Neo4jExporter
        logger.info("Exporting to Neo4j…")
        with Neo4jExporter() as exporter:
            exporter.export_graph(G, clear_first=args.clear_db)
            exporter.add_risk_scores(scored)
        logger.info("Neo4j export complete.")

    # ── 8. JSON output (optional) ──────────────────────────────────────────
    if args.output:
        output = {
            "summary": {
                "nodes": G.number_of_nodes(),
                "edges": G.number_of_edges(),
                "high_risk_count": len(high_risk),
                "shared_officers": len(shared),
                "shell_chains": len(chains),
            },
            "high_risk_nodes": [
                {
                    "id": n.node_id,
                    "label": n.label,
                    "type": n.node_type,
                    "score": n.score,
                    "flags": n.flags,
                    "betweenness": n.betweenness,
                    "pagerank": n.pagerank,
                    "sanctions_distance": n.sanctions_distance,
                }
                for n in high_risk
            ],
            "shared_officers": {k: v for k, v in shared.items()},
            "shell_chains": [
                [G.nodes[n].get("label", n) for n in chain]
                for chain in chains
            ],
        }
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        logger.info("Results saved to %s", args.output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sanctions Network Analyzer — detect evasion patterns in corporate graphs."
    )
    parser.add_argument(
        "--targets", required=True,
        help="Path to CSV file with columns: name, jurisdiction",
    )
    parser.add_argument(
        "--output", default="data/output.json",
        help="Path to write JSON results (default: data/output.json)",
    )
    parser.add_argument(
        "--neo4j", action="store_true",
        help="Export graph to Neo4j after analysis",
    )
    parser.add_argument(
        "--clear-db", action="store_true",
        help="Clear Neo4j database before importing (use with caution)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
