"""
ingestion/guidestar.py — Israeli nonprofit data scraper (Guidestar Israel).

Fetches basic financial information for Israeli nonprofits (amutot), including
foreign funding amounts. A nonprofit that receives a large share of its income
from foreign political sources is a Person of Interest in sanctions/subversion
investigations.

Note: Guidestar Israel has no public API. This module uses HTTP scraping.
      Be respectful of their servers — use the built-in delay.
"""

import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config import REQUEST_DELAY_SECONDS, REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.guidestar.org.il"
_SEARCH_URL = f"{_BASE_URL}/organizations"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; SanctionsNetworkAnalyzer/1.0; "
        "+https://github.com/your-repo)"
    )
}


@dataclass
class NonprofitProfile:
    """Key financial fields for an Israeli nonprofit (amuta)."""
    name: str
    registration_number: str
    total_income: Optional[float]          # ILS
    foreign_political_funding: Optional[float]  # ILS — declared foreign gov. donations
    foreign_funding_ratio: Optional[float]      # 0.0–1.0
    top_donors: list[str]


def search_nonprofit(name: str) -> list[dict]:
    """
    Search Guidestar Israel for a nonprofit by name.

    Args:
        name: Full or partial name of the nonprofit.

    Returns:
        List of dicts with 'name' and 'registration_number' keys.
    """
    params = {"q": name}
    resp = requests.get(
        _SEARCH_URL,
        params=params,
        headers=_HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    results = []

    # Guidestar renders result rows as <tr> elements with a data-id attribute
    for row in soup.select("tr[data-id]"):
        reg_num = row.get("data-id", "")
        name_cell = row.select_one("td.org-name")
        if name_cell:
            results.append({
                "name": name_cell.get_text(strip=True),
                "registration_number": reg_num,
            })

    return results


def get_nonprofit_profile(registration_number: str) -> Optional[NonprofitProfile]:
    """
    Fetch financial details for a nonprofit by its registration number.

    Args:
        registration_number: Israeli nonprofit registration number (e.g. "580123456").

    Returns:
        NonprofitProfile or None if the page could not be parsed.
    """
    url = f"{_BASE_URL}/organizations/{registration_number}"
    resp = requests.get(url, headers=_HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)

    soup = BeautifulSoup(resp.text, "lxml")

    def _extract_amount(label: str) -> Optional[float]:
        """Find a labeled financial figure and parse it as a float."""
        el = soup.find(string=re.compile(label, re.IGNORECASE))
        if el:
            sibling = el.find_next(string=re.compile(r"[\d,]+"))
            if sibling:
                try:
                    return float(sibling.replace(",", ""))
                except ValueError:
                    pass
        return None

    total = _extract_amount("total income|סה\"כ הכנסות")
    foreign = _extract_amount("foreign political|מדינה זרה")
    ratio = (foreign / total) if (total and foreign and total > 0) else None

    name_el = soup.select_one("h1.org-title, .organization-name")
    name = name_el.get_text(strip=True) if name_el else registration_number

    return NonprofitProfile(
        name=name,
        registration_number=registration_number,
        total_income=total,
        foreign_political_funding=foreign,
        foreign_funding_ratio=ratio,
        top_donors=[],   # extend: parse donors table if needed
    )


def find_high_foreign_funding(
    names: list[str],
    threshold: float = 0.20,
) -> list[NonprofitProfile]:
    """
    Return nonprofits whose foreign political funding exceeds a given ratio.

    Args:
        names:      List of nonprofit names to look up.
        threshold:  Minimum foreign_funding_ratio to flag (default: 20 %).

    Returns:
        List of NonprofitProfile objects that exceed the threshold.
    """
    flagged = []
    for name in names:
        results = search_nonprofit(name)
        if not results:
            logger.warning("No Guidestar result for: %s", name)
            continue

        reg_num = results[0]["registration_number"]
        profile = get_nonprofit_profile(reg_num)
        if profile and profile.foreign_funding_ratio is not None:
            if profile.foreign_funding_ratio >= threshold:
                logger.info(
                    "Flagged: %s — %.0f%% foreign political funding",
                    profile.name, profile.foreign_funding_ratio * 100,
                )
                flagged.append(profile)

        time.sleep(REQUEST_DELAY_SECONDS)

    return flagged
