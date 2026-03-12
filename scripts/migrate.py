"""
migrate.py – One-time migration from lists.json + colors.json → SQLite data.db
"""
import json, sqlite3, os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(ROOT_DIR, "data.db")
LISTS_PATH = os.path.join(ROOT_DIR, "data", "lists.json")
COLORS_PATH = os.path.join(ROOT_DIR, "data", "colors.json")

def normalize_category(category):
    cleaned = " ".join(str(category or "").split())
    return (cleaned or "Other").upper()

def normalize_tag(tag):
    cleaned = " ".join(str(tag or "").split())
    return cleaned.upper()

def migrate():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("Removed existing data.db")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE watchlists (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            slug        TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            short_name  TEXT NOT NULL,
            category    TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            tag         TEXT NOT NULL DEFAULT '',
            currency    TEXT NOT NULL DEFAULT 'USD',
            show_type   INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE tickers (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            watchlist_id  INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
            symbol        TEXT NOT NULL,
            name          TEXT NOT NULL,
            tag           TEXT NOT NULL DEFAULT '',
            currency      TEXT NOT NULL DEFAULT 'USD',
            sort_order    INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE tag_colors (
            tag    TEXT PRIMARY KEY,
            bg     TEXT NOT NULL,
            text   TEXT NOT NULL,
            border TEXT NOT NULL
        );
    """)

    c.execute("INSERT INTO settings VALUES (?, ?)", ("GLOBAL_BASE_CURRENCY", "EUR"))

    with open(LISTS_PATH, "r", encoding="utf-8") as f:
        lists_data = json.load(f)

    for slug, data in lists_data.items():
        c.execute("""
            INSERT INTO watchlists (slug, name, short_name, category, description, tag, currency, show_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            slug,
            data.get("name", slug),
            data.get("shortName", slug),
            normalize_category(data.get("category", "Other")),
            data.get("description", ""),
            data.get("tag", ""),
            data.get("currency", "USD"),
            data.get("showType", 1)  # Default for old config
        ))
        wl_id = c.lastrowid
        for i, item in enumerate(data.get("items", [])):
            c.execute("""
                INSERT INTO tickers (watchlist_id, symbol, name, tag, currency, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (wl_id, item.get("ticker",""), item.get("name",""), item.get("tag",""), item.get("currency","USD"), i))

    print(f"Migrated {len(lists_data)} watchlists")

    with open(COLORS_PATH, "r", encoding="utf-8") as f:
        colors = json.load(f)
    for tag, vals in colors.items():
        c.execute("INSERT INTO tag_colors (tag, bg, text, border) VALUES (?, ?, ?, ?)",
                  (normalize_tag(tag), vals["bg"], vals["text"], vals["border"]))
    print(f"Migrated {len(colors)} tag colors")

    conn.commit()
    conn.close()
    print(f"Migration complete -> {DB_PATH}")

if __name__ == "__main__":
    migrate()
