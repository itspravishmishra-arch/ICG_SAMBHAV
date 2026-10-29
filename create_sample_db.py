"""Create a small online-shop database for testing the chatbot.

Works with SQLite (default, no setup) or any database SQLAlchemy supports,
for example a free hosted Postgres:

    python create_sample_db.py                                  # makes sample_shop.db
    python create_sample_db.py --database-url "postgresql+psycopg2://user:pass@host/db"

Tables: categories, customers, products, orders, order_items, reviews.
The data is fake and generated with a fixed random seed, so it is the same every time.
"""

from __future__ import annotations

import argparse
import random
from datetime import date, timedelta

from sqlalchemy import create_engine, inspect, text

# Drop order matters: tables that point at others come first.
TABLES = ["reviews", "order_items", "orders", "products", "customers", "categories"]

DDL = [
    """CREATE TABLE categories (
        category_id INTEGER PRIMARY KEY,
        name VARCHAR(60) NOT NULL UNIQUE
    )""",
    """CREATE TABLE customers (
        customer_id INTEGER PRIMARY KEY,
        full_name VARCHAR(100) NOT NULL,
        email VARCHAR(120) NOT NULL UNIQUE,
        city VARCHAR(60),
        country VARCHAR(60),
        signup_date DATE NOT NULL
    )""",
    """CREATE TABLE products (
        product_id INTEGER PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        category_id INTEGER NOT NULL REFERENCES categories (category_id),
        unit_price NUMERIC(10, 2) NOT NULL,
        stock_quantity INTEGER NOT NULL
    )""",
    """CREATE TABLE orders (
        order_id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES customers (customer_id),
        order_date DATE NOT NULL,
        status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'shipped', 'delivered', 'cancelled'))
    )""",
    """CREATE TABLE order_items (
        order_item_id INTEGER PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES orders (order_id),
        product_id INTEGER NOT NULL REFERENCES products (product_id),
        quantity INTEGER NOT NULL,
        unit_price NUMERIC(10, 2) NOT NULL
    )""",
    """CREATE TABLE reviews (
        review_id INTEGER PRIMARY KEY,
        product_id INTEGER NOT NULL REFERENCES products (product_id),
        customer_id INTEGER NOT NULL REFERENCES customers (customer_id),
        rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
        comment VARCHAR(255),
        created_at DATE NOT NULL
    )""",
]

CATEGORIES = ["Electronics", "Books", "Home & Kitchen", "Sports", "Toys"]

PRODUCTS = [  # (name, category index, price)
    ("Wireless Earbuds", 0, 59.99), ("Smartphone Stand", 0, 14.50), ("USB-C Charger", 0, 24.00),
    ("Bluetooth Speaker", 0, 39.90), ("Mechanical Keyboard", 0, 89.00),
    ("Python Cookbook", 1, 34.95), ("Data Science Handbook", 1, 42.00), ("Mystery Novel", 1, 12.99),
    ("Science Fiction Anthology", 1, 16.50), ("World Atlas", 1, 28.00),
    ("Chef's Knife", 2, 45.00), ("Cast Iron Pan", 2, 32.50), ("Coffee Grinder", 2, 27.80),
    ("Glass Storage Set", 2, 21.99), ("Electric Kettle", 2, 36.00),
    ("Yoga Mat", 3, 19.99), ("Dumbbell Pair", 3, 49.00), ("Running Belt", 3, 15.75),
    ("Football", 3, 22.40), ("Water Bottle", 3, 11.25),
    ("Building Blocks Set", 4, 29.99), ("Puzzle 1000 Pieces", 4, 18.60), ("Remote Control Car", 4, 44.50),
    ("Board Game Classic", 4, 31.00),
]

FIRST = ["Aarav", "Priya", "Rohan", "Ananya", "Vikram", "Sneha", "Arjun", "Meera", "Kabir", "Isha",
         "Liam", "Emma", "Noah", "Olivia", "Lucas", "Mia", "Ethan", "Sofia", "Mateo", "Chloe"]
LAST = ["Sharma", "Verma", "Gupta", "Iyer", "Reddy", "Singh", "Patel", "Nair",
        "Smith", "Brown", "Garcia", "Muller", "Rossi", "Tanaka", "Silva", "Cohen"]
PLACES = [("Mumbai", "India"), ("Delhi", "India"), ("Bengaluru", "India"), ("Kanpur", "India"),
          ("London", "United Kingdom"), ("Manchester", "United Kingdom"),
          ("New York", "United States"), ("Austin", "United States"),
          ("Berlin", "Germany"), ("Toronto", "Canada")]
COMMENTS = ["Great value", "Works as described", "Arrived late but fine", "Not what I expected",
            "Would buy again", "Broke after a month", "Excellent quality", None, None]


def build_rows(seed: int = 42) -> dict[str, list[dict]]:
    rng = random.Random(seed)
    last_day = date(2026, 10, 20)

    categories = [{"category_id": i + 1, "name": n} for i, n in enumerate(CATEGORIES)]

    customers = []
    for i in range(1, 61):
        city, country = rng.choice(PLACES)
        first, last = rng.choice(FIRST), rng.choice(LAST)
        customers.append({
            "customer_id": i,
            "full_name": f"{first} {last}",
            "email": f"{first}.{last}{i}@example.com".lower(),
            "city": city,
            "country": country,
            "signup_date": (date(2024, 1, 1) + timedelta(days=rng.randint(0, 540))).isoformat(),
        })

    products = [
        {"product_id": i + 1, "name": name, "category_id": cat + 1,
         "unit_price": price, "stock_quantity": rng.randint(0, 200)}
        for i, (name, cat, price) in enumerate(PRODUCTS)
    ]
    price_of = {p["product_id"]: p["unit_price"] for p in products}

    orders, items = [], []
    for order_id in range(1, 401):
        customer = rng.choice(customers)
        signup = date.fromisoformat(customer["signup_date"])
        span = max((last_day - signup).days, 1)
        order_date = signup + timedelta(days=rng.randint(0, span))
        age_days = (last_day - order_date).days
        if age_days < 5:
            status = rng.choice(["pending", "shipped"])
        elif age_days < 15:
            status = rng.choice(["shipped", "delivered", "cancelled"])
        else:
            status = rng.choices(["delivered", "cancelled"], weights=[9, 1])[0]
        orders.append({"order_id": order_id, "customer_id": customer["customer_id"],
                       "order_date": order_date.isoformat(), "status": status})
        for product_id in rng.sample(range(1, len(products) + 1), rng.randint(1, 4)):
            items.append({"order_item_id": len(items) + 1, "order_id": order_id,
                          "product_id": product_id, "quantity": rng.randint(1, 3),
                          "unit_price": price_of[product_id]})

    reviews = []
    for review_id in range(1, 151):
        customer = rng.choice(customers)
        reviews.append({
            "review_id": review_id,
            "product_id": rng.randint(1, len(products)),
            "customer_id": customer["customer_id"],
            "rating": rng.choices([1, 2, 3, 4, 5], weights=[1, 1, 2, 4, 5])[0],
            "comment": rng.choice(COMMENTS),
            "created_at": (date.fromisoformat(customer["signup_date"])
                           + timedelta(days=rng.randint(10, 400))).isoformat(),
        })

    return {"categories": categories, "customers": customers, "products": products,
            "orders": orders, "order_items": items, "reviews": reviews}


def create_database(database_url: str, force: bool = False) -> dict[str, int]:
    """Create the tables and fill them. Returns {table: row_count}."""
    engine = create_engine(database_url)
    existing = set(inspect(engine).get_table_names()) & set(TABLES)
    if existing and not force:
        raise SystemExit(
            f"These tables already exist: {', '.join(sorted(existing))}.\n"
            "Use --force to delete and recreate them (this erases their data)."
        )

    rows = build_rows()
    with engine.begin() as conn:
        for table in TABLES:
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        for statement in DDL:
            conn.execute(text(statement))
        for table in reversed(TABLES):  # parents before children
            data = rows[table]
            columns = list(data[0].keys())
            sql = (f"INSERT INTO {table} ({', '.join(columns)}) "
                   f"VALUES ({', '.join(':' + c for c in columns)})")
            conn.execute(text(sql), data)
    return {table: len(rows[table]) for table in TABLES}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a sample shop database.")
    parser.add_argument("--database-url", default="sqlite:///sample_shop.db",
                        help="SQLAlchemy URL (default: sqlite:///sample_shop.db)")
    parser.add_argument("--force", action="store_true",
                        help="Drop and recreate the sample tables if they already exist")
    args = parser.parse_args()

    counts = create_database(args.database_url, force=args.force)
    print(f"Created sample database at {args.database_url}")
    for table, count in counts.items():
        print(f"  {table}: {count} rows")


if __name__ == "__main__":
    main()
