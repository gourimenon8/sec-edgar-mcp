"""
SEC EDGAR MCP Server
Exposes four tools over MCP so any MCP-compatible client
can query live SEC EDGAR data.
"""

from mcp.server.fastmcp import FastMCP
from .tools import search_company, get_filing, get_financials, compare_filings

mcp = FastMCP("sec-edgar-mcp")


@mcp.tool(
    name="search_company",
    description="Resolve a company name or ticker to its SEC CIK identifier.",
)
async def search_company_tool(query: str) -> dict:
    """Args: query - company name or ticker symbol."""
    return await search_company(query)


@mcp.tool(
    name="get_filing",
    description="Fetch recent SEC filings. Supports 10-K, 10-Q, 8-K, DEF 14A, S-1, 20-F.",
)
async def get_filing_tool(cik: str, form_type: str = "10-K", limit: int = 5) -> dict:
    """Args: cik, form_type, limit (max 20)."""
    return await get_filing(cik=cik, form_type=form_type, limit=limit)


@mcp.tool(
    name="get_financials",
    description=(
        "Retrieve structured financial data from XBRL-tagged SEC filings. "
        "Covers income statement, balance sheet, and cash flow. "
        "Free cash flow is computed as operating_cash_flow minus capex."
    ),
)
async def get_financials_tool(
    cik: str,
    metrics: str = "income_statement",
    period_type: str = "quarterly",
    limit: int = 8,
) -> dict:
    """Args: cik, metrics, period_type, limit."""
    return await get_financials(cik=cik, metrics=metrics, period_type=period_type, limit=limit)


@mcp.tool(
    name="compare_filings",
    description="Compare financial metrics between two filing periods with absolute and % changes.",
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
        cik=cik, period_a=period_a, period_b=period_b,
        metrics=metrics, period_type=period_type,
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
