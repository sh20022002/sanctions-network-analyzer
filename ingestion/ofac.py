"""
ingestion/ofac.py — OFAC Specially Designated Nationals (SDN) list parser.

Downloads the official US Treasury SDN CSV and returns a set of normalized
entity names that can be matched against nodes in the network graph.

Source: https://ofac.treasury.gov/specially-designated-nationals-and-blocked-persons-list-sdn-human-readable-lists
"""

import logging
import re
from io import StringIO
from pathlib import Path

import requests
import pandas as pd

from config import OFAC_SDN_URL, REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# Local cache path — avoids re-downloading on every run
_CACHE_PATH = Path(__file__).parent.parent / "data" / "sdn_cache.csv"

# SDN CSV columns (Treasury publishes them without a header row)
_SDN_COLUMNS = [
    "ent_num", "sdn_name", "sdn_type", "program", "title",
    "call_sign", "vess_type", "tonnage", "grt", "vess_flag",
    "vess_owner", "remarks",
]


def _normalize(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    name = name.lower()
    name = re.sub(r"[^\w\s]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def download_sdn(force: bool = False) -> pd.DataFrame:
    """
    Download (or load from cache) the OFAC SDN list.

    Args:
        force: Re-download even if a cache file exists.

    Returns:
        DataFrame with at minimum 'sdn_name' and 'sdn_type' columns.
    """
    if _CACHE_PATH.exists() and not force:
        logger.info("Loading SDN list from cache: %s", _CACHE_PATH)
        return pd.read_csv(_CACHE_PATH, header=None, names=_SDN_COLUMNS, low_memory=False)

    logger.info("Downloading OFAC SDN list from %s", OFAC_SDN_URL)
    resp = requests.get(OFAC_SDN_URL, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()

    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_bytes(resp.content)
    logger.info("Saved SDN cache to %s", _CACHE_PATH)

    return pd.read_csv(StringIO(resp.text), header=None, names=_SDN_COLUMNS, low_memory=False)


def get_sanctioned_names(force_download: bool = False) -> set[str]:
    """
    Return a set of normalized SDN entity names for fast membership testing.

    Args:
        force_download: Re-fetch the list even if cached.

    Returns:
        Set of normalized (lowercase, punctuation-stripped) entity names.
    """
    df = download_sdn(force=force_download)
    names = df["sdn_name"].dropna().astype(str)
    return {_normalize(n) for n in names}


def is_sanctioned(entity_name: str, sanctioned_set: set[str]) -> bool:
    """
    Check whether a single entity name appears in the SDN list.

    Args:
        entity_name:    Name of company or person to check.
        sanctioned_set: Pre-built set from get_sanctioned_names().

    Returns:
        True if the normalized name is in the SDN list.
    """
    return _normalize(entity_name) in sanctioned_set
