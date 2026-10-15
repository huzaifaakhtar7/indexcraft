DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
  customer_id INT PRIMARY KEY,
  name        VARCHAR(100),
  email       VARCHAR(120),
  city        VARCHAR(60),
  signup_date DATE
);

CREATE TABLE categories (
  category_id INT PRIMARY KEY,
  name        VARCHAR(60)
);

CREATE TABLE products (
  product_id  INT PRIMARY KEY,
  category_id INT,
  name        VARCHAR(100),
  price       NUMERIC(10,2)
);

CREATE TABLE orders (
  order_id     INT PRIMARY KEY,
  customer_id  INT,
  status       VARCHAR(20),
  total_amount NUMERIC(10,2),
  order_date   DATE
);

CREATE TABLE order_items (
  item_id    INT PRIMARY KEY,
  order_id   INT,
  product_id INT,
  quantity   INT,
  unit_price NUMERIC(10,2)
);
