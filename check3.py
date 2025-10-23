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
        d = json.loads(res.read())
        if d.get('quotes'):
            print(f"{q}: " + d['quotes'][0].get('shortname', ''))
    except Exception as e:
        pass

search('RU=F')
search('COB=F')
search('CPO=F')
search('MTF=F')
search('CU=F')
search('ETH=F')
