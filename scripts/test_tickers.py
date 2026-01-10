import yfinance as yf
import pandas as pd

# The dictionary of user ticker (or name) to the expected Yahoo Finance ticker
tickers_to_test = {
    "NVDA": "NVDA", "AAPL": "AAPL", "GOOG": "GOOG", "MSFT": "MSFT", "AMZN": "AMZN",
    "Taiwan Semi": "2330.TW", "META": "META", "Saudi Aramco": "2222.SR", "TSLA": "TSLA",
    "AVGO": "AVGO", "Berkshire": "BRK-A", "WMT": "WMT", "LLY": "LLY", "Samsung": "005930.KS",
    "JPM": "JPM", "XOM": "XOM", "V": "V", "Tencent": "0700.HK", "JNJ": "JNJ",
    "ASML": "ASML", "SK hynix": "000660.KS", "MU": "MU", "MA": "MA", "COST": "COST",
    "ORCL": "ORCL", "ABBV": "ABBV", "Roche": "ROG.SW", "PG": "PG", "BAC": "BAC",
    "HD": "HD", "CVX": "CVX", "GE": "GE", "NFLX": "NFLX", "CAT": "CAT",
    "ICBC": "601398.SS", "KO": "KO", "AMD": "AMD", "PLTR": "PLTR", "LVMH": "MC.PA",
    "HSBC": "HSBA.L", "Agri Bank China": "601288.SS", "AstraZeneca": "AZN.L",
    "Novartis": "NOVN.SW", "BABA": "BABA", "Toyota": "7203.T", "CSCO": "CSCO",
    "LRCX": "LRCX", "AMAT": "AMAT", "MRK": "MRK", "PM": "PM", "PetroChina": "601857.SS",
    "MS": "MS", "GS": "GS", "China Construction Bank": "601939.SS", "Kweichow Moutai": "600519.SS",
    "Nestle": "NESN.SW", "WFC": "WFC", "RTX": "RTX", "UNH": "UNH", "Hermes": "RMS.PA",
    "L'Oreal": "OR.PA", "CATL": "300750.SZ", "Royal Bank of Canada": "RY.TO",
    "Intl Holding Co": "IHC.AD", "MCD": "MCD", "GEV": "GEV", "TMUS": "TMUS", "LIN": "LIN",
    "Shell": "SHEL.L", "AXP": "AXP", "PEP": "PEP", "Bank of China": "601988.SS",
    "INTC": "INTC", "IBM": "IBM", "Siemens": "SIE.DE", "SAP": "SAP.DE",
    "China Mobile": "600941.SS", "Commonwealth Bank": "CBA.AX", "Inditex": "ITX.MC",
    "Reliance": "RELIANCE.NS", "VZ": "VZ", "AMGN": "AMGN", "BHP": "BHP.AX", "C": "C",
    "Mitsubishi UFJ": "8306.T", "ABT": "ABT", "KLAC": "KLAC", "TMO": "TMO",
    "Deutsche Telekom": "DTE.DE", "Banco Santander": "SAN.MC", "TXN": "TXN",
    "T": "T", "NEE": "NEE", "DIS": "DIS", "CRM": "CRM", "APH": "APH",
    "BA": "BA", "ISRG": "ISRG", "GILD": "GILD", "SCCO": "SCCO"
}

# Fetch the last 1 day of data just to see if they're recognized
symbols = list(tickers_to_test.values())

try:
    df = yf.download(symbols, period="1d", group_by="ticker", threads=True)
    
    # Check which ones are empty or failed
    failed = []
    
    # If downloading a single ticker, the structure is different
    if "Close" in df.columns and len(symbols) == 1:
        if df.empty:
            failed.append(symbols[0])
    else:
        for ticker in symbols:
            # check if ticker is in columns (multi-index)
            # normally it's ('Close', 'AAPL') or in group_by="ticker" it's ('AAPL', 'Close')
            if ticker in df.columns.levels[0]:
                if df[ticker].dropna(how='all').empty:
                    failed.append(ticker)
            else:
                failed.append(ticker)

    print("Failed to fetch data for:", failed)
    
except Exception as e:
    print("Error:", e)
