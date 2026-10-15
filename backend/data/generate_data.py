import argparse
import csv
import io
import os
import random
import sqlite3
import sys
import time
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
SQLITE_PATH = DATA_DIR / "shop.db"

N_CATEGORIES = 50
N_PRODUCTS = 1_000
N_CUSTOMERS = 100_000
N_ORDERS = 1_000_000
ITEMS_PER_ORDER = 2
BATCH = 10_000
SEED = 42

FIRST = ["Ali", "Ahmed", "Usman", "Bilal", "Hassan", "Zain", "Hamza", "Fatima",
         "Ayesha", "Sana", "Hira", "Maryam", "Omar", "Saad", "Rabia", "Noor",
         "John", "Sara", "David", "Emma"]
LAST = ["Khan", "Ali", "Ahmed", "Malik", "Sheikh", "Butt", "Qureshi", "Siddiqui",
        "Raza", "Hussain", "Iqbal", "Chaudhry", "Smith", "Brown"]
CITIES = ["Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad", "Multan",
          "Peshawar", "Quetta", "Hyderabad", "Sialkot", "Gujranwala", "Sukkur"]
STATUSES = ["pending", "paid", "shipped", "delivered", "cancelled"]
START = date(2022, 1, 1)

TABLES = {
    "categories": ["category_id", "name"],
    "products": ["product_id", "category_id", "name", "price"],
    "customers": ["customer_id", "name", "email", "city", "signup_date"],
    "orders": ["order_id", "customer_id", "status", "total_amount", "order_date"],
    "order_items": ["item_id", "order_id", "product_id", "quantity", "unit_price"],
}


def sizes(scale: float) -> dict:
    customers = max(int(N_CUSTOMERS * scale), 100)
    orders = max(int(N_ORDERS * scale), 1_000)
    return {
        "categories": N_CATEGORIES,
        "products": N_PRODUCTS,
        "customers": customers,
        "orders": orders,
        "order_items": orders * ITEMS_PER_ORDER,
    }


def generate(scale: float = 1.0, seed: int = SEED):
    rng = random.Random(seed)
    n = sizes(scale)
    prices = {p: round(rng.uniform(100, 20_000), 2) for p in range(1, N_PRODUCTS + 1)}

    def customer(i):
        f, l = rng.choice(FIRST), rng.choice(LAST)
        return (i, f"{f} {l}", f"{f.lower()}.{l.lower()}{i}@example.com", rng.choice(CITIES),
                (START - timedelta(days=rng.randint(0, 1000))).isoformat())

    def item(i):
        pid = rng.randint(1, N_PRODUCTS)
        return (i, (i - 1) // ITEMS_PER_ORDER + 1, pid, rng.randint(1, 5), prices[pid])

    makers = {
        "categories": lambda i: (i, f"Category {i}"),
        "products": lambda i: (i, rng.randint(1, N_CATEGORIES), f"Product {i}", prices[i]),
        "customers": customer,
        "orders": lambda i: (i, rng.randint(1, n["customers"]), rng.choice(STATUSES),
                             round(rng.uniform(500, 50_000), 2),
                             (START + timedelta(days=rng.randint(0, 1460))).isoformat()),
        "order_items": item,
    }
    for table in TABLES:
        total = n[table]
        for first in range(1, total + 1, BATCH):
            last = min(first + BATCH - 1, total)
            yield table, last, total, [makers[table](i) for i in range(first, last + 1)]


def schema_statements(path: Path) -> list:
    text = path.read_text(encoding="utf-8")
    skip = ("drop database", "create database", "use ")
    return [s.strip() for s in text.split(";")
            if s.strip() and not s.strip().lower().startswith(skip)]


class MySQLTarget:
    label = "MySQL"

    def __init__(self, database: str):
        import mysql.connector
        self.database = database
        self.conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "root"),
        )
        self.cur = self.conn.cursor()
        self.cur.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`")
        self.cur.execute(f"USE `{database}`")
        for t in reversed(list(TABLES)):
            self.cur.execute(f"DROP TABLE IF EXISTS `{t}`")
        for sql in schema_statements(DATA_DIR / "schema_shop.sql"):
            self.cur.execute(sql)

    def insert(self, table, rows):
        marks = ", ".join(["%s"] * len(TABLES[table]))
        self.cur.executemany(f"INSERT INTO `{table}` VALUES ({marks})", rows)
        self.conn.commit()

    def finish(self):
        for t in TABLES:
            self.cur.execute(f"ANALYZE TABLE `{t}`")
            self.cur.fetchall()

    def count(self, table) -> int:
        self.cur.execute(f"SELECT COUNT(*) FROM `{table}`")
        return self.cur.fetchone()[0]

    def close(self):
        self.cur.close()
        self.conn.close()


class PostgresTarget:
    label = "PostgreSQL"

    def __init__(self, database: str):
        import psycopg2
        password = os.getenv("PG_PASSWORD")
        if not password:
            raise SystemExit("Set the PG_PASSWORD environment variable to load PostgreSQL")
        params = dict(host=os.getenv("PG_HOST", "localhost"), port=int(os.getenv("PG_PORT", 5432)),
                      user=os.getenv("PG_USER", "postgres"), password=password)
        admin = psycopg2.connect(dbname="postgres", **params)
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{database}"')
        admin.close()
        self.database = database
        self.conn = psycopg2.connect(dbname=database, **params)
        self.conn.autocommit = True
        self.cur = self.conn.cursor()
        for sql in schema_statements(DATA_DIR / "schema_shop_postgres.sql"):
            self.cur.execute(sql)

    def insert(self, table, rows):
        buf = io.StringIO()
        csv.writer(buf).writerows(rows)
        buf.seek(0)
        self.cur.copy_expert(f"COPY {table} ({', '.join(TABLES[table])}) FROM STDIN WITH (FORMAT csv)", buf)

    def finish(self):
        for t in TABLES:
            self.cur.execute(f"ANALYZE {t}")

    def count(self, table) -> int:
        self.cur.execute(f"SELECT COUNT(*) FROM {table}")
        return self.cur.fetchone()[0]

    def close(self):
        self.cur.close()
        self.conn.close()


class SQLiteTarget:
    label = "SQLite"

    def __init__(self, path: Path):
        self.path = Path(path)
        self.database = str(self.path)
        for suffix in ("", "-journal", "-wal", "-shm"):
            Path(f"{self.path}{suffix}").unlink(missing_ok=True)
        self.conn = sqlite3.connect(self.path, isolation_level=None)
        self.conn.execute("PRAGMA journal_mode = OFF")
        self.conn.execute("PRAGMA synchronous = OFF")
        for sql in schema_statements(DATA_DIR / "schema_shop_sqlite.sql"):
            self.conn.execute(sql)

    def insert(self, table, rows):
        marks = ", ".join(["?"] * len(TABLES[table]))
        self.conn.execute("BEGIN")
        self.conn.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)
        self.conn.execute("COMMIT")

    def finish(self):
        self.conn.execute("ANALYZE")
        self.conn.execute("PRAGMA journal_mode = DELETE")

    def count(self, table) -> int:
        return self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def close(self):
        self.conn.close()


def open_targets(names: list, args) -> list:
    targets = []
    for name in names:
        if name == "mysql":
            targets.append(MySQLTarget(args.mysql_db))
        elif name == "postgres":
            targets.append(PostgresTarget(args.pg_db))
        elif name == "sqlite":
            targets.append(SQLiteTarget(args.sqlite_path))
    return targets


def load(names: list, args) -> list:
    targets = open_targets(names, args)
    print(f"Loading into: {', '.join(f'{t.label} ({t.database})' for t in targets)}")
    started = {}
    try:
        for table, last, total, rows in generate(args.scale):
            started.setdefault(table, time.time())
            for t in targets:
                t.insert(table, rows)
            print(f"  {table}: {last:,} / {total:,}", end="\r")
            if last == total:
                print(f"  {table}: {total:,} rows done in {time.time() - started[table]:.1f}s      ")
        print("Refreshing statistics (ANALYZE)...")
        for t in targets:
            t.finish()
        print("\nRow counts:")
        print("  " + f"{'table':12s}" + "".join(f"{t.label:>14s}" for t in targets))
        for table in TABLES:
            print("  " + f"{table:12s}" + "".join(f"{t.count(table):>14,}" for t in targets))
    finally:
        for t in targets:
            t.close()
    return targets


def main(argv=None):
    parser = argparse.ArgumentParser(description="Load the IndexCraft shop test data")
    parser.add_argument("--db", nargs="+", default=["mysql"],
                        choices=["mysql", "postgres", "sqlite", "all"],
                        help="target databases (default: mysql)")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="1.0 = 1,000,000 orders, 0.1 = 100,000 orders")
    parser.add_argument("--mysql-db", default=os.getenv("DB_NAME", "shop"))
    parser.add_argument("--pg-db", default=os.getenv("PG_DATABASE", "shop"))
    parser.add_argument("--sqlite-path", default=str(SQLITE_PATH))
    args = parser.parse_args(argv)
    if args.scale <= 0:
        parser.error("--scale must be greater than 0")
    names = ["mysql", "postgres", "sqlite"] if "all" in args.db else list(dict.fromkeys(args.db))
    started = time.time()
    load(names, args)
    print(f"\nDone in {time.time() - started:.0f}s.")


if __name__ == "__main__":
    sys.exit(main())
