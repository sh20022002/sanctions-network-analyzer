"""
config.py — Central configuration loaded from environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── OpenCorporates ────────────────────────────────────────────────────────────
OPENCORP_BASE = "https://api.opencorporates.com/v0.4"
OPENCORP_TOKEN: str | None = os.getenv("OPENCORPORATES_API_TOKEN")

# ── Neo4j ─────────────────────────────────────────────────────────────────────
NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")

# ── OFAC ──────────────────────────────────────────────────────────────────────
# Official OFAC SDN CSV — no auth required
OFAC_SDN_URL = (
    "https://www.treasury.gov/ofac/downloads/sdn.csv"
)

# ── Risk thresholds ───────────────────────────────────────────────────────────
# Nodes with betweenness centrality above this are flagged as bridges
BETWEENNESS_ALERT_THRESHOLD: float = 0.05

# Nodes whose PageRank-based risk score is above this are flagged
RISK_SCORE_ALERT_THRESHOLD: float = 0.7

# Number of hops from a sanctioned entity that still counts as "proximity risk"
SANCTIONS_HOP_LIMIT: int = 2

# ── HTTP ──────────────────────────────────────────────────────────────────────
REQUEST_DELAY_SECONDS: float = 0.5   # polite delay between API calls
REQUEST_TIMEOUT_SECONDS: int = 15
