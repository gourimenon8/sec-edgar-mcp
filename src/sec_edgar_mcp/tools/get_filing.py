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
        cik:       Company CIK
        form_type: 10-K, 10-Q, 8-K, DEF 14A, S-1, 20-F
        limit:     Number of filings to return (max 20)
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
            "error": f"No {form_type} filings found.",
        }

    return {
        "company": company_name,
        "cik": cik,
        "form_type": form_type,
        "total_returned": len(filings),
        "filings": filings,
    }
