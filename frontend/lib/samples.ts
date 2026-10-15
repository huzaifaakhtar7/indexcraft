import type { DbType } from "./types";

export interface Sample {
  label: string;
  query: string;
}

const common = (yearFilter: string, dayFilter: string): Sample[] => [
  { label: "Full table scan", query: "SELECT * FROM orders WHERE customer_id = 500" },
  {
    label: "Filter + sort",
    query:
      "SELECT * FROM orders WHERE status = 'shipped' AND order_date >= '2025-01-01' ORDER BY order_date DESC LIMIT 50",
  },
  { label: "Function on column", query: `SELECT * FROM orders WHERE ${yearFilter}` },
  { label: "Single day", query: `SELECT * FROM orders WHERE ${dayFilter}` },
  { label: "Leading wildcard", query: "SELECT * FROM customers WHERE name LIKE '%ali'" },
  { label: "2M-row table", query: "SELECT * FROM order_items WHERE product_id = 42" },
  {
    label: "Join",
    query:
      "SELECT o.order_id, o.order_date, c.name FROM orders o JOIN customers c ON c.customer_id = o.customer_id WHERE c.city = 'Karachi'",
  },
];

export const SAMPLES: Record<DbType, Sample[]> = {
  mysql: common("YEAR(order_date) = 2025", "DATE(order_date) = '2025-03-15'"),
  postgres: common("EXTRACT(YEAR FROM order_date) = 2025", "date(order_date) = '2025-03-15'"),
  sqlite: common("strftime('%Y', order_date) = '2025'", "date(order_date) = '2025-03-15'"),
};
