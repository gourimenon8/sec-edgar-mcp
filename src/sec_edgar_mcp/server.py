"""
SEC EDGAR MCP Server
====================
Exposes four tools over the Model Context Protocol (MCP) so any MCP-compatible
client (Claude Desktop, Cursor, custom apps) can query live SEC EDGAR data.

Tools:
  - search_company   : Resolve company name or ticker to CIK
  - get_filing       : Fetch recent filings by form type (10-K, 10-Q, 8-K, ...)
  - get_financials   : Pull structured XBRL financial data (income stmt, balance sheet, cash flow)
  - compare_filings  : Side-by-side comparison of two periods with computed deltas

Run locally:
  python -m sec_edgar_mcp

Or via the MCP CLI:
  mcp run src/sec_edgar_mcp/server.py
"""

from mcp.server.fastmcp import FastMCP
from .tools import search_company, get_filing, get_financials, compare_filings

# ── Server initialisation ──────────────────────────────────────────────────────
mcp = FastMCP("sec-edgar-mcp")


# ── Tool: search_company ───────────────────────────────────────────────────────
@mcp.tool(
    name="search_company",
    description=(
        "Resolve a company name or stock ticker to its SEC CIK identifier. "
        "Use ticker symbols for precise lookups (e.g. 'AAPL', 'MSFT'). "
        "Returns the CIK you need to pass to all other tools."
    ),
)
async def search_company_tool(query: str) -> dict:
    """
    Args:
        query: Company name (e.g. 'Apple Inc') or ticker (e.g. 'AAPL')
    """
    return await search_company(query)


# ── Tool: get_filing ───────────────────────────────────────────────────────────
@mcp.tool(
    name="get_filing",
    description=(
        "Fetch recent SEC filings for a company. Supports 10-K (annual reports), "
        "10-Q (quarterly reports), 8-K (material events), DEF 14A (proxy statements), "
        "S-1 (IPO registration), and 20-F (foreign private issuers). "
        "Returns filing dates, accession numbers, and direct document URLs."
    ),
)
async def get_filing_tool(
    cik: str,
    form_type: str = "10-K",
    limit: int = 5,
) -> dict:
    """
    Args:
        cik:       Company CIK from search_company
        form_type: One of: 10-K, 10-Q, 8-K, DEF 14A, S-1, 20-F
        limit:     How many recent filings to return (max 20)
    """
    return await get_filing(cik=cik, form_type=form_type, limit=limit)


# ── Tool: get_financials ───────────────────────────────────────────────────────
@mcp.tool(
    name="get_financials",
    description=(
        "Retrieve structured financial data for a company from XBRL-tagged SEC filings. "
        "Covers income statement (revenue, net income, EPS, R&D), balance sheet "
        "(assets, liabilities, cash, equity, debt), and cash flow (operating CF, capex). "
        "Returns a time series of reported values sorted by most recent period first."
    ),
)
async def get_financials_tool(
    cik: str,
    metrics: str = "income_statement",
    period_type: str = "quarterly",
    limit: int = 8,
) -> dict:
    """
    Args:
        cik:         Company CIK from search_company
        metrics:     'income_statement' | 'balance_sheet' | 'cash_flow' | 'all'
                     or comma-separated metric names like 'revenue,net_income,cash'
        period_type: 'quarterly' or 'annual'
        limit:       Number of periods to return per metric (max 12)
    """
    return await get_financials(
        cik=cik,
        metrics=metrics,
        period_type=period_type,
        limit=limit,
    )


# ── Tool: compare_filings ──────────────────────────────────────────────────────
@mcp.tool(
    name="compare_filings",
    description=(
        "Compare financial metrics between two filing periods for the same company. "
        "Returns absolute and percentage changes for each metric, plus a ranked list "
        "of the top 5 changes by magnitude. Ideal for spotting YoY or QoQ trends."
    ),
)
async def compare_filings_tool(
    cik: str,
    period_a: str,
    period_b: str,
    metrics: str = "income_statement",
    period_type: str = "quarterly",
) -> dict:
    """
    Args:
        cik:         Company CIK from search_company
        period_a:    Earlier period end date — YYYY-MM or YYYY-MM-DD (e.g. '2023-09')
        period_b:    Later period end date   — YYYY-MM or YYYY-MM-DD (e.g. '2024-09')
        metrics:     Same options as get_financials
        period_type: 'quarterly' or 'annual'
    """
    return await compare_filings(
        cik=cik,
        period_a=period_a,
        period_b=period_b,
        metrics=metrics,
        period_type=period_type,
    )


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    mcp.run()


if __name__ == "__main__":
    main()
