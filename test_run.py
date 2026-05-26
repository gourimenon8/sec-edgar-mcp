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
