"""
SEC EDGAR API client.
Handles all HTTP communication with the SEC public EDGAR endpoints.
"""

import os
import httpx
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

_user_agent = os.getenv("SEC_USER_AGENT", "sec-edgar-mcp your-email@example.com")

HEADERS = {
    "User-Agent": _user_agent,
    "Accept-Encoding": "gzip, deflate",
}

BASE_URL = "https://data.sec.gov"


async def get_json(url: str, params: Optional[dict] = None) -> dict:
    """Generic async GET request returning parsed JSON."""
    async with httpx.AsyncClient(headers=HEADERS, timeout=30.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def fetch_submissions(cik: str) -> dict:
    """Fetch all submission metadata for a company by CIK."""
    padded_cik = cik.zfill(10)
    url = f"{BASE_URL}/submissions/CIK{padded_cik}.json"
    return await get_json(url)


async def fetch_company_concept(cik: str, taxonomy: str, tag: str) -> dict:
    """Fetch a single XBRL concept across all filings."""
    padded_cik = cik.zfill(10)
    url = f"{BASE_URL}/api/xbrl/companyconcept/CIK{padded_cik}/{taxonomy}/{tag}.json"
    return await get_json(url)


async def search_company_by_name(name: str) -> list[dict]:
    """Search for companies by name using EDGAR full-text search."""
    url = "https://efts.sec.gov/LATEST/search-index"
    params = {"q": f'"{name}"', "dateRange": "custom", "forms": "10-K"}
    async with httpx.AsyncClient(headers=HEADERS, timeout=30.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
    hits = data.get("hits", {}).get("hits", [])
    seen = {}
    for hit in hits:
        src = hit.get("_source", {})
        entity = src.get("entity_name", "")
        cik = src.get("file_num", "") or src.get("entity_id", "")
        if entity and entity not in seen:
            seen[entity] = {"name": entity, "cik": cik}
    return list(seen.values())[:10]


async def get_cik_from_ticker(ticker: str) -> Optional[str]:
    """Resolve a stock ticker to a CIK using SEC company_tickers.json."""
    url = "https://www.sec.gov/files/company_tickers.json"
    data = await get_json(url)
    ticker_upper = ticker.upper()
    for _, company in data.items():
        if company.get("ticker", "").upper() == ticker_upper:
            return str(company["cik_str"])
    return None
