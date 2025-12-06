import sqlite3

db_path = r"C:\Users\serbi\Documents\software_projects\MarketDeck\data.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Get watchlist
row = conn.execute("SELECT id, slug FROM watchlists WHERE name LIKE '%Cap / Value%'").fetchone()
if not row:
    print("Watchlist not found.")
    exit(1)

wl_id = row['id']
print(f"Watchlist found: {wl_id} - {row['slug']}")

# Update description
desc = "Tracks US equities across various market capitalizations (large, mid, small) and investment styles (growth, value)."
conn.execute("UPDATE watchlists SET description = ? WHERE id = ?", (desc, wl_id))

# Tickers to add
tickers = {
    "VBK": "Vanguard Small-Cap Growth ETF",
    "VBR": "Vanguard Small-Cap Value ETF",
    "VOT": "Vanguard Mid-Cap Growth ETF",
    "VOE": "Vanguard Mid-Cap Value ETF",
    "VUG": "Vanguard Growth ETF",
    "VTV": "Vanguard Value ETF"
}

max_order_row = conn.execute("SELECT COALESCE(MAX(sort_order), -1) as m FROM tickers WHERE watchlist_id = ?", (wl_id,)).fetchone()
sort_order = max_order_row['m']

for ticker, name in tickers.items():
    sort_order += 1
    # Check if already exists
    existing = conn.execute("SELECT id FROM tickers WHERE watchlist_id = ? AND symbol = ?", (wl_id, ticker)).fetchone()
    if not existing:
        conn.execute("INSERT INTO tickers (watchlist_id, symbol, name, tag, currency, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
                     (wl_id, ticker, name, "US Eq", "USD", sort_order))
        print(f"Inserted {ticker} - {name}")
    else:
        print(f"Skipped {ticker}, already exists")

conn.commit()
conn.close()
print("Done")
