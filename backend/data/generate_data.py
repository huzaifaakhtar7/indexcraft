import os
import random
import time
from datetime import date, timedelta

import mysql.connector

HOST = os.getenv("DB_HOST", "localhost")
USER = os.getenv("DB_USER", "root")
PASSWORD = os.getenv("DB_PASSWORD", "root")
DATABASE = "shop"

N_CATEGORIES = 50
N_PRODUCTS = 1_000
N_CUSTOMERS = 100_000
N_ORDERS = 1_000_000
ITEMS_PER_ORDER = 2
BATCH = 10_000

random.seed(42)

FIRST = ["Ali", "Ahmed", "Usman", "Bilal", "Hassan", "Zain", "Hamza", "Fatima",
         "Ayesha", "Sana", "Hira", "Maryam", "Omar", "Saad", "Rabia", "Noor",
         "John", "Sara", "David", "Emma"]
LAST = ["Khan", "Ali", "Ahmed", "Malik", "Sheikh", "Butt", "Qureshi", "Siddiqui",
        "Raza", "Hussain", "Iqbal", "Chaudhry", "Smith", "Brown"]
CITIES = ["Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad", "Multan",
          "Peshawar", "Quetta", "Hyderabad", "Sialkot", "Gujranwala", "Sukkur"]
STATUSES = ["pending", "paid", "shipped", "delivered", "cancelled"]
START = date(2022, 1, 1)


def insert_batches(cur, conn, table, sql, total, make_row):
    t0 = time.time()
    for first in range(1, total + 1, BATCH):
        last = min(first + BATCH - 1, total)
        rows = [make_row(i) for i in range(first, last + 1)]
        cur.executemany(sql, rows)
        conn.commit()
        print(f"  {table}: {last:,} / {total:,}", end="\r")
    print(f"  {table}: {total:,} rows done in {time.time() - t0:.1f}s      ")


def main():
    conn = mysql.connector.connect(host=HOST, user=USER,
                                   password=PASSWORD, database=DATABASE)
    cur = conn.cursor()

    print("Clearing old data...")
    for t in ["order_items", "orders", "products", "categories", "customers"]:
        cur.execute(f"TRUNCATE TABLE {t}")
    conn.commit()

    prices = {p: round(random.uniform(100, 20_000), 2)
              for p in range(1, N_PRODUCTS + 1)}

    print("Inserting data...")
    insert_batches(cur, conn, "categories",
                   "INSERT INTO categories VALUES (%s, %s)",
                   N_CATEGORIES,
                   lambda i: (i, f"Category {i}"))

    insert_batches(cur, conn, "products",
                   "INSERT INTO products VALUES (%s, %s, %s, %s)",
                   N_PRODUCTS,
                   lambda i: (i, random.randint(1, N_CATEGORIES),
                              f"Product {i}", prices[i]))

    def customer(i):
        f, l = random.choice(FIRST), random.choice(LAST)
        return (i, f"{f} {l}", f"{f.lower()}.{l.lower()}{i}@example.com",
                random.choice(CITIES),
                START - timedelta(days=random.randint(0, 1000)))

    insert_batches(cur, conn, "customers",
                   "INSERT INTO customers VALUES (%s, %s, %s, %s, %s)",
                   N_CUSTOMERS, customer)

    insert_batches(cur, conn, "orders",
                   "INSERT INTO orders VALUES (%s, %s, %s, %s, %s)",
                   N_ORDERS,
                   lambda i: (i, random.randint(1, N_CUSTOMERS),
                              random.choice(STATUSES),
                              round(random.uniform(500, 50_000), 2),
                              START + timedelta(days=random.randint(0, 1460))))

    def item(i):
        pid = random.randint(1, N_PRODUCTS)
        order_id = (i - 1) // ITEMS_PER_ORDER + 1
        return (i, order_id, pid, random.randint(1, 5), prices[pid])

    insert_batches(cur, conn, "order_items",
                   "INSERT INTO order_items VALUES (%s, %s, %s, %s, %s)",
                   N_ORDERS * ITEMS_PER_ORDER, item)

    print("\nRow counts:")
    for t in ["customers", "categories", "products", "orders", "order_items"]:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"  {t:12s} {cur.fetchone()[0]:>10,}")

    cur.close()
    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
