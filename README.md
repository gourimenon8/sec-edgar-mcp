# SEC EDGAR MCP Server

A custom **Model Context Protocol (MCP)** server that connects AI clients (Claude Desktop, Cursor, custom apps) to live SEC EDGAR financial data — no API key required.

Ask Claude questions like *"How has Apple's free cash flow trended over the last 6 quarters?"* and get answers sourced directly from SEC filings in real time.

---

## What is MCP?

The **Model Context Protocol** is an open standard (by Anthropic) that lets AI models call external tools in a structured, consistent way. This server implements that protocol on top of the SEC's public EDGAR APIs.

```
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│   MCP Client     │ ──────► │  This MCP Server │ ──────► │   SEC EDGAR API  │
│ (Claude Desktop) │  stdio  │  (your machine)  │  HTTPS  │  (data.sec.gov)  │
└──────────────────┘         └──────────────────┘         └──────────────────┘
```

---

## Tools

| Tool | Description |
|---|---|
| `search_company` | Resolve a ticker or company name to its SEC CIK identifier |
| `get_filing` | Fetch recent filings by form type (10-K, 10-Q, 8-K, DEF 14A, S-1, 20-F) |
| `get_financials` | Pull XBRL-structured financial data — income statement, balance sheet, cash flow |
| `compare_filings` | Side-by-side comparison of two periods with absolute and % deltas |

### Supported Financial Metrics

| Group | Metrics |
|---|---|
| `income_statement` | revenue, gross_profit, operating_income, net_income, eps_basic, eps_diluted, r_and_d |
| `balance_sheet` | total_assets, current_assets, cash, total_liabilities, current_liabilities, long_term_debt, stockholders_equity |
| `cash_flow` | operating_cash_flow, capex |

---

## Example Queries

Once connected to Claude Desktop, you can ask:

> *"What's Apple's CIK number?"*
> → Claude calls `search_company("AAPL")`

> *"Show me Microsoft's last 4 quarterly income statements"*
> → Claude calls `search_company("MSFT")` → `get_financials(cik, "income_statement", "quarterly", 4)`

> *"How did Tesla's balance sheet change from Q3 2023 to Q3 2024?"*
> → Claude calls `compare_filings(cik, "2023-09", "2024-09", "balance_sheet")`

> *"Pull Meta's most recent 10-K filing"*
> → Claude calls `search_company("META")` → `get_filing(cik, "10-K", 1)`

---

## Architecture

```
sec-edgar-mcp/
├── src/
│   └── sec_edgar_mcp/
│       ├── server.py          # FastMCP server — tool registration and entry point
│       ├── edgar_client.py    # Async HTTP client for SEC EDGAR endpoints
│       └── tools/
│           ├── search_company.py   # Ticker/name → CIK resolution
│           ├── get_filing.py       # Filing metadata retrieval
│           ├── get_financials.py   # XBRL financial data extraction
│           └── compare_filings.py  # Period-over-period comparison engine
├── tests/
│   └── test_tools.py          # Async tests against live EDGAR API
├── pyproject.toml
└── requirements.txt
```

**Key design decisions:**
- **FastMCP** for minimal boilerplate — tool registration via `@mcp.tool()` decorators
- **Async throughout** — all EDGAR calls use `httpx.AsyncClient` for non-blocking I/O
- **No auth required** — the SEC EDGAR API is fully public; the server only requires a `User-Agent` header per SEC policy
- **Graceful degradation** — tools return structured error dicts (not exceptions) so the LLM can reason about failures and retry with adjusted parameters

---

## Installation

**Requirements:** Python 3.11+

```bash
git clone https://github.com/yourhandle/sec-edgar-mcp.git
cd sec-edgar-mcp
pip install -e .
```

Or install dependencies directly:
```bash
pip install -r requirements.txt
```

---

## Usage

### Run the server (stdio mode — for MCP clients)

```bash
python -m sec_edgar_mcp
```

### Connect to Claude Desktop

Add this block to your `claude_desktop_config.json`:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "sec-edgar": {
      "command": "python",
      "args": ["-m", "sec_edgar_mcp"],
      "cwd": "/absolute/path/to/sec-edgar-mcp"
    }
  }
}
```

Restart Claude Desktop. You should see the SEC EDGAR tools appear in the tools panel.

### Connect to Cursor

In Cursor settings → MCP Servers, add:

```json
{
  "sec-edgar": {
    "command": "python",
    "args": ["-m", "sec_edgar_mcp"],
    "cwd": "/absolute/path/to/sec-edgar-mcp"
  }
}
```

---

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

Tests make live calls to `data.sec.gov`. To skip in CI:

```bash
SKIP_LIVE_TESTS=1 pytest tests/ -v
```

---

## SEC EDGAR API Notes

- All data comes from the **SEC's public EDGAR APIs** (`data.sec.gov`, `efts.sec.gov`)
- No API key is required — the SEC mandates only a valid `User-Agent` header
- Financial metrics are sourced from **XBRL-tagged filings** — if a company doesn't use XBRL tagging (rare for US public companies after 2009), some metrics may be unavailable
- The SEC rate-limits at ~10 requests/second; this server stays well within that with sequential async calls

---

## Tech Stack

- [`mcp`](https://github.com/anthropics/python-sdk) — Anthropic's Python MCP SDK (FastMCP)
- [`httpx`](https://www.python-httpx.org/) — Async HTTP client
- [`pydantic`](https://docs.pydantic.dev/) — Tool input validation
- SEC EDGAR Public APIs — `data.sec.gov`, `efts.sec.gov`

---

## License

MIT
