"""
Tests for SEC EDGAR MCP tools.

These tests use real EDGAR API calls against known stable companies.
Run with: pytest tests/ -v

Note: Tests make live network requests to api.sec.gov.
      Set SKIP_LIVE_TESTS=1 to skip them in CI environments with no outbound access.
"""

import os
import pytest
import pytest_asyncio

SKIP_LIVE = os.getenv("SKIP_LIVE_TESTS", "0") == "1"
skip_if_no_network = pytest.mark.skipif(SKIP_LIVE, reason="Live network tests disabled")

# Apple is stable, well-known, and consistently files XBRL — good test subject
APPLE_TICKER = "AAPL"
APPLE_CIK = "320193"


# ── search_company ─────────────────────────────────────────────────────────────

@skip_if_no_network
@pytest.mark.asyncio
async def test_search_company_by_ticker():
    from src.sec_edgar_mcp.tools import search_company
    result = await search_company(APPLE_TICKER)
    assert "cik" in result
    assert result["cik"] == APPLE_CIK
    assert result["resolved_via"] == "ticker"


@skip_if_no_network
@pytest.mark.asyncio
async def test_search_company_unknown():
    from src.sec_edgar_mcp.tools import search_company
    result = await search_company("ZZZZNOTREAL999")
    assert "error" in result or "matches" in result


# ── get_filing ─────────────────────────────────────────────────────────────────

@skip_if_no_network
@pytest.mark.asyncio
async def test_get_filing_10k():
    from src.sec_edgar_mcp.tools import get_filing
    result = await get_filing(cik=APPLE_CIK, form_type="10-K", limit=3)
    assert result["form_type"] == "10-K"
    assert len(result["filings"]) <= 3
    assert all(f["form_type"] == "10-K" for f in result["filings"])


@skip_if_no_network
@pytest.mark.asyncio
async def test_get_filing_10q():
    from src.sec_edgar_mcp.tools import get_filing
    result = await get_filing(cik=APPLE_CIK, form_type="10-Q", limit=4)
    assert result["form_type"] == "10-Q"
    assert len(result["filings"]) >= 1


@pytest.mark.asyncio
async def test_get_filing_unsupported_form():
    from src.sec_edgar_mcp.tools import get_filing
    result = await get_filing(cik=APPLE_CIK, form_type="FAKE-99")
    assert "error" in result
    assert "supported_forms" in result


# ── get_financials ─────────────────────────────────────────────────────────────

@skip_if_no_network
@pytest.mark.asyncio
async def test_get_financials_income_statement():
    from src.sec_edgar_mcp.tools import get_financials
    result = await get_financials(
        cik=APPLE_CIK,
        metrics="income_statement",
        period_type="quarterly",
        limit=4,
    )
    assert "data" in result
    assert "revenue" in result["data"]
    assert len(result["data"]["revenue"]) >= 1


@skip_if_no_network
@pytest.mark.asyncio
async def test_get_financials_balance_sheet():
    from src.sec_edgar_mcp.tools import get_financials
    result = await get_financials(
        cik=APPLE_CIK,
        metrics="balance_sheet",
        period_type="annual",
        limit=3,
    )
    assert "total_assets" in result["data"]


@skip_if_no_network
@pytest.mark.asyncio
async def test_get_financials_specific_metrics():
    from src.sec_edgar_mcp.tools import get_financials
    result = await get_financials(
        cik=APPLE_CIK,
        metrics="revenue,net_income,cash",
        period_type="quarterly",
        limit=4,
    )
    for key in ["revenue", "net_income", "cash"]:
        assert key in result["data"]


@pytest.mark.asyncio
async def test_get_financials_invalid_metric():
    from src.sec_edgar_mcp.tools import get_financials
    result = await get_financials(cik=APPLE_CIK, metrics="not_a_real_metric")
    assert "error" in result


# ── compare_filings ────────────────────────────────────────────────────────────

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
    if "revenue" in result["comparison"]:
        rev = result["comparison"]["revenue"]
        assert "percent_change" in rev
        assert "direction" in rev


@skip_if_no_network
@pytest.mark.asyncio
async def test_compare_filings_returns_direction():
    from src.sec_edgar_mcp.tools import compare_filings
    result = await compare_filings(
        cik=APPLE_CIK,
        period_a="2022-09",
        period_b="2023-09",
        metrics="revenue,net_income",
        period_type="quarterly",
    )
    for metric, data in result.get("comparison", {}).items():
        assert data["direction"] in ("increase", "decrease", "unchanged")
