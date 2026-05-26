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
