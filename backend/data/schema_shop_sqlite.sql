DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
  customer_id INTEGER PRIMARY KEY,
  name        TEXT,
  email       TEXT,
  city        TEXT,
  signup_date TEXT
);

CREATE TABLE categories (
  category_id INTEGER PRIMARY KEY,
  name        TEXT
);

CREATE TABLE products (
  product_id  INTEGER PRIMARY KEY,
  category_id INTEGER,
  name        TEXT,
  price       REAL
);

CREATE TABLE orders (
  order_id     INTEGER PRIMARY KEY,
  customer_id  INTEGER,
  status       TEXT,
  total_amount REAL,
  order_date   TEXT
);

CREATE TABLE order_items (
  item_id    INTEGER PRIMARY KEY,
  order_id   INTEGER,
  product_id INTEGER,
  quantity   INTEGER,
  unit_price REAL
);
