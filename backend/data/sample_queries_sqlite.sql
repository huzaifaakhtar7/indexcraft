SELECT * FROM orders WHERE customer_id = 500;

SELECT * FROM orders WHERE status = 'shipped' AND order_date >= '2025-01-01' ORDER BY order_date DESC LIMIT 50;

SELECT * FROM orders WHERE strftime('%Y', order_date) = '2025';

SELECT * FROM orders WHERE date(order_date) = '2025-03-15';

SELECT * FROM customers WHERE name LIKE '%ali';

SELECT * FROM order_items WHERE product_id = 42;

SELECT o.order_id, o.order_date, c.name FROM orders o JOIN customers c ON c.customer_id = o.customer_id WHERE c.city = 'Karachi';
