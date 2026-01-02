import urllib.request
import json
import urllib.parse
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def search(q):
    try:
        url = f'https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(q)}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, context=ctx)
        data = json.loads(res.read())
        if data.get('quotes'):
            print(f"SEARCH {q}:")
            for i in data['quotes'][:3]:
                print(f"  {i.get('symbol')} - {i.get('shortname')}")
        else:
            print(f"SEARCH {q}: No results")
    except Exception as e:
        print(f"SEARCH ERROR {q}: {e}")

search('Tin Futures')
search('Nickel Futures')
search('Palm Oil Futures')
search('Rubber Futures')
search('Ethanol Futures')
search('Cobalt Futures')
search('CB=F')
