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
    result = await get_financials(
        cik=APPLE_CIK, metrics="income_statement",
        period_type="quarterly", limit=4,
    )
    assert "revenue" in result["data"]


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
        cik=APPLE_CIK, period_a="2023-09", period_b="2024-09",
        metrics="income_statement", period_type="quarterly",
    )
    assert "comparison" in result
    assert "top_5_changes_by_magnitude" in result
