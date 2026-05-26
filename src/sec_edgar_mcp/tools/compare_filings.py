"""
Tool: compare_filings
Compares financial metrics across two periods for the same company.
Highlights absolute and percentage changes — the core of what analysts do manually.
"""

from typing import Optional
from .get_financials import get_financials, FINANCIAL_CONCEPTS, METRIC_GROUPS


def _find_period(data_series: list[dict], period_end: str) -> Optional[dict]:
    """Find a specific period entry by its end date."""
    for entry in data_series:
        if entry.get("period_end", "").startswith(period_end[:7]):  # match YYYY-MM
            return entry
    return None


def _compute_change(val_a: float, val_b: float) -> dict:
    """Compute absolute and percentage change from period_a to period_b."""
    absolute = val_b - val_a
    if val_a != 0:
        pct = round((absolute / abs(val_a)) * 100, 2)
    else:
        pct = None

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
        period_a:    Earlier period end date in YYYY-MM or YYYY-MM-DD format
                     (e.g., "2023-09", "2023-09-30")
        period_b:    Later period end date in YYYY-MM or YYYY-MM-DD format
                     (e.g., "2024-09", "2024-09-30")
        metrics:     Which metrics to compare — same options as get_financials:
                     'income_statement', 'balance_sheet', 'cash_flow', 'all',
                     or comma-separated metric names
        period_type: 'quarterly' (10-Q) or 'annual' (10-K)

    Returns:
        dict with side-by-side comparison and computed changes for each metric
    """
    # Pull enough history to cover both periods
    financial_data = await get_financials(
        cik=cik,
        metrics=metrics,
        period_type=period_type,
        limit=12,
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
            "period_a": {
                "end_date": entry_a.get("period_end"),
                "value": val_a,
                "filed": entry_a.get("filed"),
            },
            "period_b": {
                "end_date": entry_b.get("period_end"),
                "value": val_b,
                "filed": entry_b.get("filed"),
            },
            **change,
        }

    # Build summary of most notable changes
    notable = sorted(
        [
            (k, v)
            for k, v in comparison.items()
            if v.get("percent_change") is not None
        ],
        key=lambda x: abs(x[1]["percent_change"]),
        reverse=True,
    )[:5]

    output = {
        "cik": cik,
        "period_a": period_a,
        "period_b": period_b,
        "period_type": period_type,
        "metrics_compared": len(comparison),
        "comparison": comparison,
        "top_5_changes_by_magnitude": [
            {
                "metric": k,
                "percent_change": v["percent_change"],
                "direction": v["direction"],
            }
            for k, v in notable
        ],
    }

    if missing_periods:
        output["missing_or_unavailable"] = missing_periods

    return output
