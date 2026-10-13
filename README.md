# IndexCraft

Measured Index Design Assistant. Finds slow SQL queries, suggests the right indexes, and proves the speed-up by testing on a safe copy of the database.

## Databases

- `shop`: 5 test tables (customers, categories, products, orders, order_items) with 1,000,000 orders
- `indexcraft_meta`: 5 history tables (analysis_runs, problems, suggestions, test_results, reports)

## Setup

1. Run `backend/data/schema_shop.sql` and `backend/data/schema_meta.sql` in MySQL Workbench.
2. Install packages and load test data:

```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
set DB_PASSWORD=your_mysql_password
python data/generate_data.py
```

## Run

Backend:

```
cd backend
venv\Scripts\activate
uvicorn main:app --reload
```

Open http://localhost:8000/docs

Frontend:

```
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

## Tech stack

Python (FastAPI), Next.js, MySQL
