import sqlite3
import os

db_path = r"C:\Users\serbi\Documents\software_projects\MarketDeck\data.db"
conn = sqlite3.connect(db_path)
cur = conn.execute("UPDATE watchlists SET category = 'ETFs' WHERE name LIKE '%Cap / Value ETFs%'")
conn.commit()
print("Rows updated:", cur.rowcount)
conn.close()
