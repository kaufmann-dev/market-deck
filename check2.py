import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

tickers = ['RU=F', 'TIN=F', 'LN=F', 'COB=F', 'CPO=F', 'PO=F', 'NCF=F', 'COAL=F', 'MTF=F', 'CU=F', 'ETH=F', 'CME=F', 'LME=F']
for t in tickers:
    try:
        url = f'https://query2.finance.yahoo.com/v8/finance/chart/{t}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req, context=ctx)
        d = json.loads(response.read())
        if d['chart']['result']:
            meta = d['chart']['result'][0]['meta']
            print(f"{t}: FOUND - " + meta.get('instrumentType', '') + " - " + meta.get('exchangeName', ''))
        else:
            print(f"{t}: NOT FOUND")
    except Exception as e:
        if "404" in str(e):
            print(f"{t}: NOT FOUND (404)")
        else:
            print(f"{t}: ERROR - {str(e)}")
