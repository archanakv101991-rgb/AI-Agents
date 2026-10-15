"""SQLite helpers: build a sample database and run SQL read-only."""

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "sample.db"

SCHEMA = """
CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT NOT NULL,
    signup_date TEXT NOT NULL
);
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL
);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    order_date TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL
);
"""

COUNTRIES = ["USA", "UK", "India", "Germany", "Canada", "Australia"]
PRODUCTS = [
    ("Wireless Mouse", "Electronics", 25.0),
    ("Mechanical Keyboard", "Electronics", 89.0),
    ("27in Monitor", "Electronics", 240.0),
    ("USB-C Hub", "Electronics", 45.0),
    ("Standing Desk", "Furniture", 420.0),
    ("Ergonomic Chair", "Furniture", 310.0),
    ("Desk Lamp", "Furniture", 38.0),
    ("Notebook Pack", "Stationery", 12.0),
    ("Gel Pens (10)", "Stationery", 9.0),
    ("Whiteboard Markers", "Stationery", 15.0),
]


def build_sample_db(path: Path = DB_PATH, seed: int = 42) -> Path:
    """(Re)create the sample store database with deterministic random data."""
    rng = random.Random(seed)
    if path.exists():
        path.unlink()

    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)

    start = date(2025, 1, 1)
    customers = []
    for i in range(1, 121):
        signup = start + timedelta(days=rng.randint(0, 500))
        customers.append((i, f"Customer {i}", rng.choice(COUNTRIES), signup.isoformat()))
    conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", customers)

    products = [(i, name, cat, price) for i, (name, cat, price) in enumerate(PRODUCTS, 1)]
    conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", products)

    item_id = 1
    for order_id in range(1, 801):
        order_date = start + timedelta(days=rng.randint(0, 640))
        status = rng.choices(["delivered", "shipped", "cancelled"], weights=[85, 10, 5])[0]
        customer_id = rng.randint(1, 120)
        conn.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?)",
            (order_id, customer_id, order_date.isoformat(), status),
        )
        for _ in range(rng.randint(1, 4)):
            product_id, _, _, price = rng.choice(products)
            qty = rng.randint(1, 3)
            conn.execute(
                "INSERT INTO order_items VALUES (?, ?, ?, ?, ?)",
                (item_id, order_id, product_id, qty, price),
            )
            item_id += 1

    conn.commit()
    conn.close()
    return path


def run_query(sql: str, db_path: Path = DB_PATH, max_rows: int = 200) -> tuple[list[str], list[tuple]]:
    """Run a SELECT/WITH query against the database in read-only mode.

    Returns (column_names, rows). Rows are capped at max_rows.
    """
    if not sql.lstrip().lower().startswith(("select", "with")):
        raise ValueError("Only SELECT queries are allowed.")

    # mode=ro makes SQLite refuse any write, even if the SQL were malicious.
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description or []]
        rows = cursor.fetchmany(max_rows)
        return columns, rows
    finally:
        conn.close()


if __name__ == "__main__":
    print(f"Built sample database at {build_sample_db()}")
