"""
ingestion/opencorporates.py — OpenCorporates API client.

Fetches company profiles and their officers (directors, shareholders, etc.).
Each officer is a potential link to other companies in the network.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional

import requests

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import OPENCORP_BASE, OPENCORP_TOKEN, REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


@dataclass
class Officer:
    """A person or entity holding a role in a company."""
    name: str
    role: str
    company_number: str
    jurisdiction: str
    inactive: bool = False


@dataclass
class CompanyProfile:
    """Enriched company record returned by the OpenCorporates API."""
    name: str
    jurisdiction: str
    company_number: str
    status: Optional[str]
    registered_address: Optional[str]
    incorporation_date: Optional[str]
    officers: list[Officer] = field(default_factory=list)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _params(extra: dict | None = None) -> dict:
    """Build query-string parameters, injecting the API token when available."""
    base = {"format": "json"}
    if OPENCORP_TOKEN:
        base["api_token"] = OPENCORP_TOKEN
    if extra:
        base.update(extra)
    return base


def _get(url: str, params: dict | None = None) -> dict:
    """GET wrapper with timeout and basic error logging."""
    resp = requests.get(
        url,
        params=_params(params),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return resp.json()


# ── Public API ────────────────────────────────────────────────────────────────

def search_company(name: str, jurisdiction: str = "") -> list[dict]:
    """
    Search OpenCorporates for a company by name.

    Args:
        name: Company name to search for.
        jurisdiction: Optional ISO jurisdiction code (e.g. "us_de", "gb", "ru").

    Returns:
        List of raw company dicts from the API (up to 5 results).
    """
    params = {"q": name, "per_page": 5}
    if jurisdiction:
        params["jurisdiction_code"] = jurisdiction

    data = _get(f"{OPENCORP_BASE}/companies/search", params)
    return data["results"]["companies"]


def get_officers(jurisdiction: str, company_number: str) -> list[Officer]:
    """
    Fetch all officers (directors, secretaries, etc.) for a company.

    Args:
        jurisdiction: Jurisdiction code of the company.
        company_number: Company registration number.

    Returns:
        List of Officer objects.
    """
    url = f"{OPENCORP_BASE}/companies/{jurisdiction}/{company_number}/officers"
    data = _get(url)

    officers = []
    for item in data["results"]["officers"]:
        o = item["officer"]
        officers.append(Officer(
            name=o.get("name", "").strip(),
            role=o.get("position", "unknown").strip(),
            company_number=company_number,
            jurisdiction=jurisdiction,
            inactive=o.get("inactive", False),
        ))
    return officers


def build_profile(company_name: str, jurisdiction: str = "") -> Optional[CompanyProfile]:
    """
    Search for a company and return an enriched CompanyProfile with its officers.

    Args:
        company_name: Human-readable company name.
        jurisdiction: Optional jurisdiction filter.

    Returns:
        CompanyProfile or None if no match was found.
    """
    results = search_company(company_name, jurisdiction)
    if not results:
        logger.warning("No OpenCorporates result for: %s", company_name)
        return None

    best = results[0]["company"]
    jur = best["jurisdiction_code"]
    num = best["company_number"]

    time.sleep(REQUEST_DELAY_SECONDS)
    officers = get_officers(jur, num)

    addr = best.get("registered_address") or {}
    address_str = addr.get("street_address") or addr.get("locality") or None

    return CompanyProfile(
        name=best["name"],
        jurisdiction=jur,
        company_number=num,
        status=best.get("current_status"),
        registered_address=address_str,
        incorporation_date=best.get("incorporation_date"),
        officers=officers,
    )


def bulk_build_profiles(
    targets: list[tuple[str, str]],
    delay: float = REQUEST_DELAY_SECONDS,
) -> list[CompanyProfile]:
    """
    Build profiles for a list of (company_name, jurisdiction) pairs.

    Args:
        targets: List of (name, jurisdiction_code) tuples.
        delay:   Seconds to wait between requests (respects rate limits).

    Returns:
        List of successfully fetched CompanyProfile objects.
    """
    profiles: list[CompanyProfile] = []
    for name, jur in targets:
        logger.info("Fetching profile: %s (%s)", name, jur or "any")
        profile = build_profile(name, jur)
        if profile:
            logger.info(
                "  -> %s | %d officers | status: %s",
                profile.name, len(profile.officers), profile.status,
            )
            profiles.append(profile)
        time.sleep(delay)
    return profiles
