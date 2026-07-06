import pyodbc
import sqlite3
import re
import math
import logging
from datetime import datetime
from pathlib import Path

# ──────────────────────────── CONFIG ────────────────────────────

MSSQL_SERVER = r"."  # "." = local, or "SERVER\INSTANCE"
MSSQL_DATABASE = "Sepidar01-change-angel"

SCRIPT_DIR = Path(__file__).parent
LOCAL_DB_PATH = SCRIPT_DIR / "decant_local.db"
LOG_PATH = SCRIPT_DIR / "decant_updater.log"

MARGINS = {
    3: 1.20,
    5: 1.15,
    10: 1.10,
    20: 1.05,
}
DEFAULT_MARGIN = 1.00

# ──────────────────────────── LOGGING ───────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("decant")

# ──────────────────────────── HELPERS ───────────────────────────


def extract_volume(title):
    if not title:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*ml", title, re.IGNORECASE)
    return float(m.group(1)) if m else None


def round_price(raw):
    return math.ceil(math.floor(raw / 100_000) / 5) * 500_000


def calc_decant_price(main_price, main_vol, decant_vol):
    price_per_ml = main_price / main_vol
    margin = MARGINS.get(int(decant_vol), DEFAULT_MARGIN)
    raw = price_per_ml * decant_vol * margin
    return round_price(raw)


# ──────────────────────────── MSSQL ─────────────────────────────


def mssql_connect():
    conn_str = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={MSSQL_SERVER};"
        f"DATABASE={MSSQL_DATABASE};"
        f"Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)


def fetch_main_products(conn):
    rows = conn.cursor().execute("""
        SELECT DISTINCT
            m.[Code], m.[Title], sp.[DefaultPrice]
        FROM [POS].[Item] m
        JOIN [POS].[ItemSalePrice] sp ON sp.[ItemRef] = m.[ItemID]
        WHERE EXISTS (
            SELECT 1 FROM [POS].[Item] d WHERE d.[Description] = m.[Code]
        )
    """).fetchall()

    products = []
    for code, title, price in rows:
        vol = extract_volume(title)
        if vol and vol > 0:
            products.append({
                "code": code.strip(),
                "title": title,
                "price": float(price),
                "volume_ml": vol,
            })
    return products


def fetch_decants(conn, main_code):
    rows = conn.cursor().execute("""
        SELECT i.[ItemID], i.[Code], i.[Title], sp.[DefaultPrice]
        FROM [POS].[Item] i
        JOIN [POS].[ItemSalePrice] sp ON sp.[ItemRef] = i.[ItemID]
        WHERE i.[Description] = ?
    """, main_code).fetchall()

    decants = []
    for item_id, code, title, price in rows:
        vol = extract_volume(title)
        if vol and vol > 0:
            decants.append({
                "item_id": item_id,
                "code": code,
                "title": title,
                "current_price": float(price),
                "volume_ml": vol,
            })
    return decants


def update_decant_in_db(conn, item_id, new_price):
    conn.cursor().execute("""
        UPDATE [POS].[ItemSalePrice]
        SET [DefaultPrice] = ?
        WHERE [ItemRef] = ?
    """, new_price, item_id)


# ──────────────────────────── LOCAL DB ──────────────────────────


def init_local_db():
    conn = sqlite3.connect(str(LOCAL_DB_PATH))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS price_snapshot (
            item_code   TEXT PRIMARY KEY,
            title       TEXT,
            volume_ml   REAL,
            price       REAL,
            checked_at  TEXT
        );
        CREATE TABLE IF NOT EXISTS update_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date        TEXT,
            item_code       TEXT,
            old_price       REAL,
            new_price       REAL,
            decants_updated INTEGER
        );
    """)
    return conn


def load_old_prices(local):
    rows = local.execute("SELECT item_code, price FROM price_snapshot").fetchall()
    return {code: price for code, price in rows}


def save_snapshot(local, products):
    now = datetime.now().isoformat()
    local.execute("DELETE FROM price_snapshot")
    local.executemany(
        "INSERT INTO price_snapshot VALUES (?,?,?,?,?)",
        [(p["code"], p["title"], p["volume_ml"], p["price"], now) for p in products],
    )
    local.commit()


def log_change(local, code, old_price, new_price, count):
    local.execute(
        "INSERT INTO update_log (run_date, item_code, old_price, new_price, decants_updated) VALUES (?,?,?,?,?)",
        (datetime.now().isoformat(), code, old_price, new_price, count),
    )
    local.commit()


# ──────────────────────────── MAIN ──────────────────────────────


def run():
    log.info("=" * 60)
    log.info("Decant price updater started")

    mssql = mssql_connect()
    local = init_local_db()

    current_products = fetch_main_products(mssql)
    log.info(f"Found {len(current_products)} main products with decants")

    old_prices = load_old_prices(local)
    is_first_run = len(old_prices) == 0

    if is_first_run:
        log.info("First run — calculating all decant prices")

    changed = []
    for product in current_products:
        old = old_prices.get(product["code"])
        if is_first_run or old is None or old != product["price"]:
            changed.append((product, old))

    if not changed:
        log.info("No price changes detected. Nothing to do.")
        save_snapshot(local, current_products)
        mssql.close()
        local.close()
        return

    log.info(f"{len(changed)} product(s) need decant updates")

    total_decants_updated = 0

    for product, old_price in changed:
        decants = fetch_decants(mssql, product["code"])
        updated_count = 0

        for decant in decants:
            new_price = calc_decant_price(
                product["price"], product["volume_ml"], decant["volume_ml"]
            )
            if new_price != decant["current_price"]:
                update_decant_in_db(mssql, decant["item_id"], new_price)
                updated_count += 1
                log.info(
                    f"    {decant['code']} ({decant['title']}): "
                    f"{decant['current_price']:,.0f} -> {new_price:,.0f}  [UPDATED]"
                )
            else:
                log.info(
                    f"    {decant['code']} ({decant['title']}): "
                    f"{decant['current_price']:,.0f}  [NO CHANGE]"
                )

        log_change(local, product["code"], old_price or 0, product["price"], updated_count)
        total_decants_updated += updated_count

        old_str = f"{old_price:>15,.0f}" if old_price else "N/A"
        log.info(
            f"  Main [{product['code']}] {product['title']}  "
            f"{old_str} -> {product['price']:>15,.0f}  "
            f"({updated_count} decants updated)"
        )

    mssql.commit()
    save_snapshot(local, current_products)

    log.info("-" * 60)
    log.info(f"Summary: {len(changed)} main product(s) changed, "
             f"{total_decants_updated} decant price(s) updated")
    log.info("=" * 60)

    mssql.close()
    local.close()


if __name__ == "__main__":
    run()
