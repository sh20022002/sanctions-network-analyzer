# Sanctions Network Analyzer

A graph-based tool for detecting sanctions evasion, shell-company chains, and
subversive funding networks by cross-referencing corporate registries, OFAC
sanctions lists, and nonprofit databases.

## How It Works

1. **Ingestion** — Pull company officers from OpenCorporates, sanctioned
   entities from OFAC, and Israeli nonprofit financials from Guidestar.
2. **Graph Construction** — Build a directed graph where nodes are companies,
   people, or nonprofits and edges represent ownership, directorship, or
   funding relationships.
3. **Risk Scoring** — Score every node using Betweenness Centrality, PageRank,
   and proximity to sanctioned entities.
4. **Export** — Write the graph to Neo4j for visual investigation with
   Neo4j Bloom / Linkurious, or export to JSON/CSV.

## Detected Patterns

| Pattern | Description |
|---|---|
| Shell Chain | Long chain of companies across jurisdictions masking the origin of funds |
| Fan-In | Many small entities funneling money to a single hub |
| Layering | Nominee directors appearing across dozens of unrelated companies |
| Sanctions Proximity | Entity connected (≤ 2 hops) to an OFAC-listed company |

## Installation

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your credentials.

## Quick Start

```bash
# Analyze a list of target companies
python main.py --targets data/targets.csv --output data/output.json

# Export results to Neo4j
python main.py --targets data/targets.csv --neo4j
```

## Data Sources

| Source | What it provides | Access |
|---|---|---|
| [OpenCorporates](https://opencorporates.com) | Company officers, registration data | Free tier / paid API |
| [OFAC SDN List](https://ofac.treasury.gov/specially-designated-nationals-and-blocked-persons-list-sdn-human-readable-lists) | US sanctions targets | Public |
| [Guidestar Israel](https://www.guidestar.org.il) | Israeli nonprofit financials | Public scrape |
| [Aleph / OCCRP](https://aleph.occrp.org) | Leaks, corporate registries, corruption data | Free (rate-limited) |

## Project Structure

```
sanctions-network-analyzer/
├── ingestion/
│   ├── opencorporates.py   # OpenCorporates API client
│   ├── ofac.py             # OFAC SDN list parser
│   └── guidestar.py        # Israeli nonprofit scraper
├── analysis/
│   ├── graph.py            # Graph construction (NetworkX)
│   └── risk_scoring.py     # Centrality + risk metrics
├── export/
│   └── neo4j_export.py     # Neo4j Cypher writer
├── data/
│   └── targets.csv         # Example input
├── tests/
├── config.py
├── main.py
├── requirements.txt
└── .env.example
```
