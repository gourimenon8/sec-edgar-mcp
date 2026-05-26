"""
Tool: get_financials
Fetches structured financial data for a company from SEC XBRL filings.
Supports income statement, balance sheet, and cash flow metrics.
"""

from typing import Optional
from ..edgar_client import fetch_company_concept, fetch_submissions


# Curated map of financial concepts to XBRL tags
FINANCIAL_CONCEPTS = {
    # Income Statement
    "revenue": ("us-gaap", "Revenues"),
    "net_income": ("us-gaap", "NetIncomeLoss"),
    "gross_profit": ("us-gaap", "GrossProfit"),
    "operating_income": ("us-gaap", "OperatingIncomeLoss"),
    "eps_basic": ("us-gaap", "EarningsPerShareBasic"),
    "eps_diluted": ("us-gaap", "EarningsPerShareDiluted"),
    "r_and_d": ("us-gaap", "ResearchAndDevelopmentExpense"),
    # Balance Sheet
    "total_assets": ("us-gaap", "Assets"),
    "total_liabilities": ("us-gaap", "Liabilities"),
    "cash": ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
    "stockholders_equity": ("us-gaap", "StockholdersEquity"),
    "long_term_debt": ("us-gaap", "LongTermDebt"),
    "current_assets": ("us-gaap", "AssetsCurrent"),
    "current_liabilities": ("us-gaap", "LiabilitiesCurrent"),
    # Cash Flow
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
    "cash_flow": [
        "operating_cash_flow", "capex",
    ],
    "all": list(FINANCIAL_CONCEPTS.keys()),
}


def _filter_by_period(units: list[dict], period_type: str, limit: int) -> list[dict]:
    """Filter XBRL unit entries by period type (annual=10-K, quarterly=10-Q)."""
    if period_type == "annual":
        # Annual facts have 'frame' like CY2023 or have start/end ~1 year apart
        filtered = [
            u for u in units
            if u.get("form") == "10-K"
        ]
    elif period_type == "quarterly":
        filtered = [
            u for u in units
            if u.get("form") == "10-Q"
        ]
    else:
        filtered = units

    # Sort descending by end date
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
        metrics:     Which metrics to fetch — 'income_statement', 'balance_sheet',
                     'cash_flow', 'all', or a comma-separated list of specific metrics
                     from: revenue, net_income, gross_profit, operating_income,
                     eps_basic, eps_diluted, r_and_d, total_assets, total_liabilities,
                     cash, stockholders_equity, long_term_debt, current_assets,
                     current_liabilities, operating_cash_flow, capex
        period_type: 'quarterly' (10-Q) or 'annual' (10-K)
        limit:       Number of most recent periods to return per metric (max 12)

    Returns:
        dict mapping each metric to its time series of reported values
    """
    limit = min(limit, 12)

    # Resolve requested metrics
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

            # Most financial metrics are in USD; EPS is in USD/shares
            raw_units = units_map.get("USD", units_map.get("USD/shares", []))

            filtered = _filter_by_period(raw_units, period_type, limit)
            results[metric_name] = [
                {
                    "period_end": u.get("end"),
                    "period_start": u.get("start"),
                    "value": u.get("val"),
                    "form": u.get("form"),
                    "filed": u.get("filed"),
                    "accession": u.get("accn"),
                }
                for u in filtered
            ]
        except Exception as e:
            errors[metric_name] = str(e)

    output = {
        "cik": cik,
        "metrics": metrics,
        "period_type": period_type,
        "data": results,
    }
    if errors:
        output["errors"] = errors
        output["note"] = "Some metrics could not be fetched. This company may not report them via XBRL."

    # Compute free_cash_flow = operating_cash_flow - capex (not a native XBRL tag)
    if "operating_cash_flow" in results and "capex" in results:
        fcf_series = []
        ocf_by_period = {e["period_end"]: e["value"] for e in results["operating_cash_flow"]}
        for capex_entry in results["capex"]:
            period = capex_entry["period_end"]
            ocf = ocf_by_period.get(period)
            if ocf is not None and capex_entry["value"] is not None:
                fcf_series.append({
                    "period_end": period,
                    "value": ocf - capex_entry["value"],
                    "form": capex_entry["form"],
                    "filed": capex_entry["filed"],
                    "note": "computed: operating_cash_flow - capex"
                })
        results["free_cash_flow"] = fcf_series

    return output
