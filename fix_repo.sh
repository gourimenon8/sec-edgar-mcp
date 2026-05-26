#!/bin/bash
# Run this from your sec-edgar-mcp project root
# It rewrites all files with correct formatting

echo "Fixing all files..."

# ── requirements.txt ──────────────────────────────────────────────────────────
cat > requirements.txt << 'EOF'
mcp[cli]>=1.0.0
httpx>=0.27.0
pydantic>=2.0.0
python-dotenv>=1.0.0
EOF

# ── .env.example ──────────────────────────────────────────────────────────────
cat > .env.example << 'EOF'
# Required: SEC EDGAR User-Agent header
# Format: "appname your-email@example.com"
# See: https://www.sec.gov/os/accessing-edgar-data
SEC_USER_AGENT=sec-edgar-mcp your-email@example.com
EOF

# ── pyproject.toml ────────────────────────────────────────────────────────────
cat > pyproject.toml << 'EOF'
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "sec-edgar-mcp"
version = "0.1.0"
description = "MCP server for querying live SEC EDGAR financial data"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
keywords = ["mcp", "sec", "edgar", "finance", "llm", "claude"]

dependencies = [
    "mcp[cli]>=1.0.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
]

[project.scripts]
sec-edgar-mcp = "sec_edgar_mcp.server:main"

[tool.hatch.build.targets.wheel]
packages = ["src/sec_edgar_mcp"]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]
EOF

# ── src/sec_edgar_mcp/__init__.py ─────────────────────────────────────────────
cat > src/sec_edgar_mcp/__init__.py << 'EOF'
"""SEC EDGAR MCP Server — query live SEC data from any MCP-compatible AI client."""
EOF

# ── src/sec_edgar_mcp/__main__.py ─────────────────────────────────────────────
cat > src/sec_edgar_mcp/__main__.py << 'EOF'
from .server import main

if __name__ == "__main__":
    main()
EOF

# ── src/sec_edgar_mcp/edgar_client.py ────────────────────────────────────────
cat > src/sec_edgar_mcp/edgar_client.py << 'EOF'
"""
SEC EDGAR API client.
Handles all HTTP communication with the SEC's public EDGAR endpoints.
"""

import os
import httpx
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# SEC requires a User-Agent header in the format "appname email@example.com"
# Set SEC_USER_AGENT in your .env file — see .env.example
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
    """Resolve a stock ticker to a CIK using SEC's company_tickers.json."""
    url = "https://www.sec.gov/files/company_tickers.json"
    data = await get_json(url)
    ticker_upper = ticker.upper()
    for _, company in data.items():
        if company.get("ticker", "").upper() == ticker_upper:
            return str(company["cik_str"])
    return None
EOF

# ── src/sec_edgar_mcp/server.py ───────────────────────────────────────────────
cat > src/sec_edgar_mcp/server.py << 'EOF'
"""
SEC EDGAR MCP Server
Exposes four tools over the Model Context Protocol so any MCP-compatible
client (Claude Desktop, Cursor, custom apps) can query live SEC EDGAR data.
"""

from mcp.server.fastmcp import FastMCP
from .tools import search_company, get_filing, get_financials, compare_filings

mcp = FastMCP("sec-edgar-mcp")


@mcp.tool(
    name="search_company",
    description=(
        "Resolve a company name or stock ticker to its SEC CIK identifier. "
        "Use ticker symbols for precise lookups (e.g. 'AAPL', 'MSFT'). "
        "Returns the CIK you need to pass to all other tools."
    ),
)
async def search_company_tool(query: str) -> dict:
    """Args: query — company name or ticker symbol."""
    return await search_company(query)


@mcp.tool(
    name="get_filing",
    description=(
        "Fetch recent SEC filings for a company. Supports 10-K, 10-Q, 8-K, "
        "DEF 14A, S-1, and 20-F. Returns filing dates, accession numbers, "
        "and direct document URLs."
    ),
)
async def get_filing_tool(cik: str, form_type: str = "10-K", limit: int = 5) -> dict:
    """Args: cik, form_type (10-K/10-Q/8-K/DEF 14A/S-1/20-F), limit (max 20)."""
    return await get_filing(cik=cik, form_type=form_type, limit=limit)


@mcp.tool(
    name="get_financials",
    description=(
        "Retrieve structured financial data from XBRL-tagged SEC filings. "
        "Covers income statement, balance sheet, and cash flow. "
        "Free cash flow is computed automatically as operating_cash_flow minus capex."
    ),
)
async def get_financials_tool(
    cik: str,
    metrics: str = "income_statement",
    period_type: str = "quarterly",
    limit: int = 8,
) -> dict:
    """Args: cik, metrics (income_statement/balance_sheet/cash_flow/all), period_type, limit."""
    return await get_financials(cik=cik, metrics=metrics, period_type=period_type, limit=limit)


@mcp.tool(
    name="compare_filings",
    description=(
        "Compare financial metrics between two filing periods. "
        "Returns absolute and percentage changes plus a ranked list "
        "of the top 5 changes by magnitude."
    ),
)
async def compare_filings_tool(
    cik: str,
    period_a: str,
    period_b: str,
    metrics: str = "income_statement",
    period_type: str = "quarterly",
) -> dict:
    """Args: cik, period_a (YYYY-MM), period_b (YYYY-MM), metrics, period_type."""
    return await compare_filings(
        cik=cik,
        period_a=period_a,
        period_b=period_b,
        metrics=metrics,
        period_type=period_type,
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
EOF

# ── src/sec_edgar_mcp/tools/__init__.py ───────────────────────────────────────
cat > src/sec_edgar_mcp/tools/__init__.py << 'EOF'
from .search_company import search_company
from .get_filing import get_filing
from .get_financials import get_financials
from .compare_filings import compare_filings

__all__ = ["search_company", "get_filing", "get_financials", "compare_filings"]
EOF

# ── src/sec_edgar_mcp/tools/search_company.py ────────────────────────────────
cat > src/sec_edgar_mcp/tools/search_company.py << 'EOF'
"""
Tool: search_company
Resolves a company name or ticker to its SEC CIK identifier.
"""

from ..edgar_client import search_company_by_name, get_cik_from_ticker


async def search_company(query: str) -> dict:
    """
    Search for a company by name or ticker and return its CIK and metadata.

    Args:
        query: Company name (e.g., 'Apple Inc') or ticker symbol (e.g., 'AAPL')
    """
    cik = await get_cik_from_ticker(query)
    if cik:
        return {
            "resolved_via": "ticker",
            "ticker": query.upper(),
            "cik": cik,
            "note": f"CIK resolved from ticker '{query.upper()}'. Use this CIK in other tools.",
        }

    results = await search_company_by_name(query)
    if not results:
        return {
            "error": f"No companies found matching '{query}'.",
            "suggestion": "Try a more specific name or use the ticker symbol directly.",
        }

    return {
        "resolved_via": "name_search",
        "query": query,
        "matches": results,
        "note": "Multiple matches found. Use the CIK of your intended company in other tools.",
    }
EOF

# ── src/sec_edgar_mcp/tools/get_filing.py ────────────────────────────────────
cat > src/sec_edgar_mcp/tools/get_filing.py << 'EOF'
"""
Tool: get_filing
Fetches recent SEC filings for a company by CIK and form type.
"""

from ..edgar_client import fetch_submissions

SUPPORTED_FORMS = {"10-K", "10-Q", "8-K", "DEF 14A", "S-1", "20-F"}


async def get_filing(cik: str, form_type: str = "10-K", limit: int = 5) -> dict:
    """
    Retrieve recent filings of a given form type for a company.

    Args:
        cik:       Company CIK (get this from search_company)
        form_type: SEC form type — 10-K, 10-Q, 8-K, DEF 14A, S-1, 20-F
        limit:     Number of most recent filings to return (max 20)
    """
    if form_type not in SUPPORTED_FORMS:
        return {
            "error": f"Unsupported form type '{form_type}'.",
            "supported_forms": sorted(SUPPORTED_FORMS),
        }

    limit = min(limit, 20)
    submissions = await fetch_submissions(cik)
    company_name = submissions.get("name", "Unknown")
    recent = submissions.get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    descriptions = recent.get("primaryDocument", [])

    filings = []
    for form, accession, date, doc in zip(forms, accessions, dates, descriptions):
        if form == form_type:
            accession_clean = accession.replace("-", "")
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}"
                f"/{accession_clean}/{doc}"
            )
            filings.append({
                "form_type": form,
                "filing_date": date,
                "accession_number": accession,
                "primary_document": doc,
                "filing_url": filing_url,
            })
            if len(filings) >= limit:
                break

    if not filings:
        return {
            "company": company_name,
            "cik": cik,
            "form_type": form_type,
            "error": f"No {form_type} filings found for this company.",
        }

    return {
        "company": company_name,
        "cik": cik,
        "form_type": form_type,
        "total_returned": len(filings),
        "filings": filings,
    }
EOF

# ── src/sec_edgar_mcp/tools/get_financials.py ────────────────────────────────
cat > src/sec_edgar_mcp/tools/get_financials.py << 'EOF'
"""
Tool: get_financials
Fetches structured financial data for a company from SEC XBRL filings.
"""

from ..edgar_client import fetch_company_concept

FINANCIAL_CONCEPTS = {
    "revenue": ("us-gaap", "Revenues"),
    "net_income": ("us-gaap", "NetIncomeLoss"),
    "gross_profit": ("us-gaap", "GrossProfit"),
    "operating_income": ("us-gaap", "OperatingIncomeLoss"),
    "eps_basic": ("us-gaap", "EarningsPerShareBasic"),
    "eps_diluted": ("us-gaap", "EarningsPerShareDiluted"),
    "r_and_d": ("us-gaap", "ResearchAndDevelopmentExpense"),
    "total_assets": ("us-gaap", "Assets"),
    "total_liabilities": ("us-gaap", "Liabilities"),
    "cash": ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
    "stockholders_equity": ("us-gaap", "StockholdersEquity"),
    "long_term_debt": ("us-gaap", "LongTermDebt"),
    "current_assets": ("us-gaap", "AssetsCurrent"),
    "current_liabilities": ("us-gaap", "LiabilitiesCurrent"),
    # Note: free_cash_flow is computed below (OCF - capex), not a native XBRL tag
    "operating_cash_flow": ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
    "capex": ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
}

METRIC_GROUPS = {
    "income_statement": [
        "revenue", "gross_profit", "operating_income",
        "net_income", "eps_basic", "eps_diluted", "r_and_d",
    ],
    "balance_sheet": [
        "total_assets", "current_assets", "cash",
        "total_liabilities", "current_liabilities",
        "long_term_debt", "stockholders_equity",
    ],
    "cash_flow": ["operating_cash_flow", "capex"],
    "all": list(FINANCIAL_CONCEPTS.keys()),
}


def _filter_by_period(units: list[dict], period_type: str, limit: int) -> list[dict]:
    if period_type == "annual":
        filtered = [u for u in units if u.get("form") == "10-K"]
    elif period_type == "quarterly":
        filtered = [u for u in units if u.get("form") == "10-Q"]
    else:
        filtered = units
    filtered.sort(key=lambda x: x.get("end", ""), reverse=True)
    return filtered[:limit]


async def get_financials(
    cik: str,
    metrics: str = "income_statement",
    period_type: str = "quarterly",
    limit: int = 8,
) -> dict:
    """
    Retrieve structured financial data for a company from XBRL-tagged SEC filings.

    Args:
        cik:         Company CIK (from search_company)
        metrics:     'income_statement' | 'balance_sheet' | 'cash_flow' | 'all'
                     or comma-separated metric names
        period_type: 'quarterly' or 'annual'
        limit:       Number of periods to return per metric (max 12)
    """
    limit = min(limit, 12)

    if metrics in METRIC_GROUPS:
        requested = METRIC_GROUPS[metrics]
    else:
        requested = [m.strip() for m in metrics.split(",")]
        invalid = [m for m in requested if m not in FINANCIAL_CONCEPTS]
        if invalid:
            return {
                "error": f"Unknown metric(s): {invalid}",
                "available_metrics": list(FINANCIAL_CONCEPTS.keys()),
                "available_groups": list(METRIC_GROUPS.keys()),
            }

    results = {}
    errors = {}

    for metric_name in requested:
        taxonomy, tag = FINANCIAL_CONCEPTS[metric_name]
        try:
            data = await fetch_company_concept(cik, taxonomy, tag)
            units_map = data.get("units", {})
            raw_units = units_map.get("USD", units_map.get("USD/shares", []))
            filtered = _filter_by_period(raw_units, period_type, limit)
            results[metric_name] = [
                {
                    "period_end": u.get("end"),
                    "period_start": u.get("start"),
                    "value": u.get("val"),
                    "form": u.get("form"),
                    "filed": u.get("filed"),
                }
                for u in filtered
            ]
        except Exception as e:
            errors[metric_name] = str(e)

    # Compute free_cash_flow = operating_cash_flow - capex
    if "operating_cash_flow" in results and "capex" in results:
        ocf_by_period = {
            e["period_end"]: e["value"]
            for e in results["operating_cash_flow"]
            if e["value"] is not None
        }
        fcf_series = []
        for entry in results["capex"]:
            period = entry["period_end"]
            ocf = ocf_by_period.get(period)
            if ocf is not None and entry["value"] is not None:
                fcf_series.append({
                    "period_end": period,
                    "value": ocf - entry["value"],
                    "form": entry["form"],
                    "filed": entry["filed"],
                    "note": "computed: operating_cash_flow - capex",
                })
        results["free_cash_flow"] = fcf_series

    output = {
        "cik": cik,
        "metrics": metrics,
        "period_type": period_type,
        "data": results,
    }
    if errors:
        output["errors"] = errors
        output["note"] = "Some metrics unavailable — company may not report them via XBRL."

    return output
EOF

# ── src/sec_edgar_mcp/tools/compare_filings.py ───────────────────────────────
cat > src/sec_edgar_mcp/tools/compare_filings.py << 'EOF'
"""
Tool: compare_filings
Compares financial metrics across two periods for the same company.
"""

from .get_financials import get_financials


def _find_period(data_series: list[dict], period_end: str) -> dict | None:
    for entry in data_series:
        if entry.get("period_end", "").startswith(period_end[:7]):
            return entry
    return None


def _compute_change(val_a: float, val_b: float) -> dict:
    absolute = val_b - val_a
    pct = round((absolute / abs(val_a)) * 100, 2) if val_a != 0 else None
    return {
        "period_a_value": val_a,
        "period_b_value": val_b,
        "absolute_change": round(absolute, 4),
        "percent_change": pct,
        "direction": "increase" if absolute > 0 else ("decrease" if absolute < 0 else "unchanged"),
    }


async def compare_filings(
    cik: str,
    period_a: str,
    period_b: str,
    metrics: str = "income_statement",
    period_type: str = "quarterly",
) -> dict:
    """
    Compare financial metrics between two filing periods for the same company.

    Args:
        cik:         Company CIK (from search_company)
        period_a:    Earlier period end date — YYYY-MM or YYYY-MM-DD
        period_b:    Later period end date   — YYYY-MM or YYYY-MM-DD
        metrics:     Same options as get_financials
        period_type: 'quarterly' or 'annual'
    """
    financial_data = await get_financials(
        cik=cik, metrics=metrics, period_type=period_type, limit=12
    )

    if "error" in financial_data:
        return financial_data

    raw_data = financial_data.get("data", {})
    comparison = {}
    missing_periods = {}

    for metric_name, series in raw_data.items():
        entry_a = _find_period(series, period_a)
        entry_b = _find_period(series, period_b)

        if entry_a is None or entry_b is None:
            missing_periods[metric_name] = {
                "period_a_found": entry_a is not None,
                "period_b_found": entry_b is not None,
                "available_periods": [e.get("period_end") for e in series],
            }
            continue

        val_a = entry_a.get("value")
        val_b = entry_b.get("value")

        if val_a is None or val_b is None:
            missing_periods[metric_name] = {"reason": "Null value in one or both periods"}
            continue

        change = _compute_change(float(val_a), float(val_b))
        comparison[metric_name] = {
            "period_a": {"end_date": entry_a.get("period_end"), "value": val_a},
            "period_b": {"end_date": entry_b.get("period_end"), "value": val_b},
            **change,
        }

    notable = sorted(
        [(k, v) for k, v in comparison.items() if v.get("percent_change") is not None],
        key=lambda x: abs(x[1]["percent_change"]),
        reverse=True,
    )[:5]

    output = {
        "cik": cik,
        "period_a": period_a,
        "period_b": period_b,
        "metrics_compared": len(comparison),
        "comparison": comparison,
        "top_5_changes_by_magnitude": [
            {"metric": k, "percent_change": v["percent_change"], "direction": v["direction"]}
            for k, v in notable
        ],
    }

    if missing_periods:
        output["missing_or_unavailable"] = missing_periods

    return output
EOF

# ── test_run.py ───────────────────────────────────────────────────────────────
cat > test_run.py << 'EOF'
import asyncio
import sys
sys.path.insert(0, '.')
from src.sec_edgar_mcp.tools import search_company, get_financials

async def main():
    print('Testing search_company...')
    result = await search_company('AAPL')
    print('CIK:', result['cik'])

    print('\nTesting get_financials...')
    fin = await get_financials(cik=result['cik'], metrics='income_statement', period_type='quarterly', limit=4)
    for entry in fin['data']['revenue']:
        print(f'  {entry["period_end"]}: ${entry["value"]:,.0f}')

asyncio.run(main())
EOF

# ── tests/test_tools.py ───────────────────────────────────────────────────────
mkdir -p tests
cat > tests/test_tools.py << 'EOF'
"""
Tests for SEC EDGAR MCP tools.
Run with: pytest tests/ -v
Set SKIP_LIVE_TESTS=1 to skip network calls in CI.
"""

import os
import pytest

SKIP_LIVE = os.getenv("SKIP_LIVE_TESTS", "0") == "1"
skip_if_no_network = pytest.mark.skipif(SKIP_LIVE, reason="Live network tests disabled")

APPLE_TICKER = "AAPL"
APPLE_CIK = "320193"


@skip_if_no_network
@pytest.mark.asyncio
async def test_search_company_by_ticker():
    from src.sec_edgar_mcp.tools import search_company
    result = await search_company(APPLE_TICKER)
    assert result["cik"] == APPLE_CIK
    assert result["resolved_via"] == "ticker"


@skip_if_no_network
@pytest.mark.asyncio
async def test_get_filing_10k():
    from src.sec_edgar_mcp.tools import get_filing
    result = await get_filing(cik=APPLE_CIK, form_type="10-K", limit=3)
    assert result["form_type"] == "10-K"
    assert len(result["filings"]) <= 3


@pytest.mark.asyncio
async def test_get_filing_unsupported_form():
    from src.sec_edgar_mcp.tools import get_filing
    result = await get_filing(cik=APPLE_CIK, form_type="FAKE-99")
    assert "error" in result


@skip_if_no_network
@pytest.mark.asyncio
async def test_get_financials_income_statement():
    from src.sec_edgar_mcp.tools import get_financials
    result = await get_financials(cik=APPLE_CIK, metrics="income_statement", period_type="quarterly", limit=4)
    assert "revenue" in result["data"]
    assert len(result["data"]["revenue"]) >= 1


@pytest.mark.asyncio
async def test_get_financials_invalid_metric():
    from src.sec_edgar_mcp.tools import get_financials
    result = await get_financials(cik=APPLE_CIK, metrics="not_a_real_metric")
    assert "error" in result


@skip_if_no_network
@pytest.mark.asyncio
async def test_compare_filings_quarterly():
    from src.sec_edgar_mcp.tools import compare_filings
    result = await compare_filings(
        cik=APPLE_CIK,
        period_a="2023-09",
        period_b="2024-09",
        metrics="income_statement",
        period_type="quarterly",
    )
    assert "comparison" in result
    assert "top_5_changes_by_magnitude" in result
EOF

echo ""
echo "✅ All files rewritten successfully."
echo ""
echo "Next steps:"
echo "  pip install -r requirements.txt"
echo "  python test_run.py"
