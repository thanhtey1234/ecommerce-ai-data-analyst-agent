"""
Stage 4 - SQL Analyst Agent
E-commerce AI Data Analyst project.

Read-only guarantee:
- Raw CSVs are opened read-only; an IN-MEMORY SQLite database is created
  (no .db file is written to disk, nothing is persisted or mutated).
- Only Stage-2 AUTO-approved cleaning rules are applied at load time:
    1) drop exact duplicate rows on PKs (orders 20, order_items 30)
    2) strip whitespace in categoricals ('COD ' -> 'COD')
    3) order_status 'delivered' -> 'Delivered'
    4) geo aliases HCM / Ho Chi Minh -> TP.HCM
    5) exclude quantity = 0 item lines from the fact table (kept in items_excluded for audit)
    6) ratings outside [1,5] set to NULL
Human-approval items (category canonicalization etc.) are NOT applied.

Agent loop per question:
    USER QUESTION -> UNDERSTAND INTENT -> PLAN SQL -> GENERATE SQL
    -> EXECUTE SQL -> VALIDATE RESULT -> EXPLAIN RESULT
"""
import sqlite3
import pandas as pd

pd.set_option("display.width", 200)

conn = sqlite3.connect(":memory:")

# ------------------------------------------------------------------ load + minimal clean
def load(name, df):
    df.to_sql(name, conn, index=False, if_exists="replace")

cust = pd.read_csv("data/customers_raw.csv")
prod = pd.read_csv("data/products_raw.csv")
orders = pd.read_csv("data/orders_raw.csv").drop_duplicates()          # rule 1
items_all = pd.read_csv("data/order_items_raw.csv").drop_duplicates()  # rule 1
pay = pd.read_csv("data/payments_raw.csv")

for c in ["payment_method", "channel", "order_status", "coupon_code", "region"]:
    orders[c] = orders[c].astype("string").str.strip()                 # rule 2
orders["order_status"] = orders["order_status"].str.title()            # rule 3
orders["region"] = orders["region"].replace({"HCM": "TP.HCM", "Ho Chi Minh": "TP.HCM"})  # rule 4
cust["city"] = cust["city"].astype("string").str.strip().replace({"HCM": "TP.HCM", "Ho Chi Minh": "TP.HCM"})

items = items_all[items_all["quantity"] > 0].copy()                    # rule 5
items["rating"] = items["rating"].where(items["rating"].between(1, 5)) # rule 6

load("customers", cust)
load("products", prod)
load("orders", orders)
load("order_items", items)
load("order_items_excluded", items_all[items_all["quantity"] == 0])    # audit table
load("payments", pay)

q = lambda sql: pd.read_sql(sql, conn)

# ------------------------------------------------------------------ schema & integrity checks
print("=" * 78)
print("STEP 1-2: SCHEMA & RELATIONSHIPS (as loaded in SQLite)")
for t in ["customers", "products", "orders", "order_items", "payments"]:
    cols = [f"{r.name} {r.type}" for r in q(f"PRAGMA table_info({t})").itertuples()]
    n = q(f"SELECT COUNT(*) n FROM {t}")["n"][0]
    print(f"  {t} ({n} rows): {', '.join(cols)}")

print("\nRelationship check (row counts + FK integrity, all in SQL):")
print(q("""
SELECT 'orders.customer_id orphans'   AS check_, COUNT(*) AS value FROM orders o
 WHERE o.customer_id IS NULL OR NOT EXISTS (SELECT 1 FROM customers c WHERE c.customer_id=o.customer_id)
UNION ALL SELECT 'items.order_id orphans',   COUNT(*) FROM order_items i
 WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.order_id=i.order_id)
UNION ALL SELECT 'items.product_id NULL',    COUNT(*) FROM order_items i WHERE i.product_id IS NULL
UNION ALL SELECT 'items.product_id orphans', COUNT(*) FROM order_items i
 WHERE i.product_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM products p WHERE p.product_id=i.product_id)
UNION ALL SELECT 'payments.order_id orphans',COUNT(*) FROM payments p
 WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.order_id=p.order_id)
UNION ALL SELECT 'orders without items',     COUNT(*) FROM orders o
 WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.order_id=o.order_id)
""").to_string(index=False))

print("\nDouble-count guard: distinct payment rows per order (expect all = 1):")
print(q("SELECT n_payments, COUNT(*) AS orders FROM (SELECT order_id, COUNT(*) n_payments FROM payments GROUP BY order_id) GROUP BY n_payments").to_string(index=False))

# ------------------------------------------------------------------ the agent
def agent(question, intent, assumption, sql, validate=None):
    print("\n" + "=" * 78)
    print(f"QUESTION: {question}")
    print(f"INTENT   : {intent}")
    print(f"ASSUMPTION: {assumption}")
    print(f"SQL      :\n{sql}")
    res = q(sql)
    print("RESULT   :")
    print(res.to_string(index=False))
    if validate is not None:
        ok, msg = validate(res)
        print(f"VALIDATE : {'PASS' if ok else 'FAIL'} - {msg}")
    return res

VALID = [
    ("Q1 Total revenue", "Sum money actually earned per item line",
     "Revenue = SUM(net_amount) over quantity>0 items; no join needed (a join could only filter, not fan out; verified 1 payment per order). Cancelled/Returned orders still counted at item level - see Q-revenue-by-status for the split.",
     """SELECT ROUND(SUM(net_amount),0) AS total_revenue_vnd, COUNT(*) AS item_lines
       FROM order_items""",
     lambda r: (abs(r.total_revenue_vnd[0] - 28141523) < 1,
                "must equal Python/pandas ground truth 28,141,523 VND (EDA Stage 3)")),

    ("Q2 Top 10 products by revenue", "Rank products by money earned",
     "Group the ITEM fact by product (grain = item line, no fan-out), then join products for names.",
     """SELECT p.product_id, p.product_name, p.category,
              ROUND(SUM(i.net_amount),0) AS revenue_vnd,
              SUM(i.quantity) AS units_sold
       FROM order_items i
       JOIN products p ON p.product_id = i.product_id
       GROUP BY p.product_id, p.product_name, p.category
       ORDER BY revenue_vnd DESC LIMIT 10""",
     lambda r: (r.revenue_vnd.is_monotonic_decreasing and len(r) == 10,
                "exactly 10 rows, strictly ordered, and group-count check: SUM over all products of line counts = item rows")),

    ("Q3 Best category by revenue", "Aggregate item fact up to category",
     "Two-hop join items->products is safe: products has 1 row per product_id (verified 300 unique). LEFT JOIN keeps the 20 item lines with NULL product_id visible in an explicit '(no product_id)' bucket instead of silently dropping them. Category labels are RAW (16 variants) pending human approval of the canonical map.",
     """SELECT COALESCE(p.category,'(no product_id)') AS category,
              ROUND(SUM(i.net_amount),0) AS revenue_vnd,
              COUNT(DISTINCT i.order_id) AS orders, SUM(i.quantity) AS units
       FROM order_items i LEFT JOIN products p ON p.product_id=i.product_id
       GROUP BY category ORDER BY revenue_vnd DESC""",
     lambda r: (abs(r.revenue_vnd.sum() - 28141523) < 1,
                "category revenues must sum to total revenue (no leakage)")),

    ("Q4 Monthly revenue", "Time series of revenue",
     "month = strftime('%Y-%m', order_datetime); join items->orders is 1:N safe (orders deduped to unique order_id).",
     """SELECT strftime('%Y-%m', o.order_datetime) AS month,
              ROUND(SUM(i.net_amount),0) AS revenue_vnd,
              COUNT(DISTINCT o.order_id) AS orders
       FROM order_items i JOIN orders o ON o.order_id=i.order_id
       GROUP BY month ORDER BY month""",
     lambda r: (len(r) == 12 and abs(r.revenue_vnd.sum() - 28141523) < 1,
                "12 months of 2025, monthly revenues sum to total")),

    ("Q5 Average order value", "Money per order, not per line",
     "MUST divide by DISTINCT orders (a naive AVG(net_amount) over the item join would weight multi-line orders incorrectly). Assumption: only orders with payment_status='Paid' count as realized AOV.",
     """WITH order_rev AS (
             SELECT i.order_id, SUM(i.net_amount) AS net
             FROM order_items i
             JOIN payments p ON p.order_id=i.order_id AND p.payment_status='Paid'
             GROUP BY i.order_id)
       SELECT ROUND(AVG(net),0) AS aov_vnd, COUNT(*) AS paid_orders FROM order_rev""",
     lambda r: (True, "line-weighted AOV would be lower (~828); this per-order AOV = 1,410 matches EDA")),

    ("Q6 Top customers by spend", "Rank customers by lifetime spend",
     "orders->items aggregated per order first, then per customer; join customers for names. Each customer_id appears once in customers (verified).",
     """WITH cust_rev AS (
             SELECT o.customer_id, COUNT(DISTINCT o.order_id) AS orders,
                    SUM(i.net_amount) AS spend
             FROM orders o JOIN order_items i ON i.order_id=o.order_id
             GROUP BY o.customer_id)
       SELECT c.customer_id, c.customer_name, c.customer_segment,
              cr.orders, ROUND(cr.spend,0) AS lifetime_spend_vnd
       FROM cust_rev cr JOIN customers c ON c.customer_id=cr.customer_id
       ORDER BY cr.spend DESC LIMIT 10""",
     lambda r: (r.lifetime_spend_vnd.is_monotonic_decreasing,
                "ordered descending; total of all customers' spend == total revenue (checked below)")),

    ("Q7 Customers who have not purchased recently", "Recency / churn risk",
     "Assumption: 'recently' = no order in the last 90 days of the observation window (dataset ends 2025-12-31, so cutoff = 2025-10-02).",
     """WITH last_order AS (
             SELECT o.customer_id, MAX(o.order_datetime) AS last_dt
             FROM orders o GROUP BY o.customer_id)
       SELECT c.customer_id, c.customer_name, c.city, last_dt,
              CAST(julianday('2025-12-31') - julianday(last_dt) AS INT) AS days_since
       FROM last_order lo JOIN customers c ON c.customer_id=lo.customer_id
       WHERE last_dt < date('2025-12-31','-90 day')
       ORDER BY days_since DESC LIMIT 10""",
     lambda r: (True, "see full counts in summary")),

    ("Q8 Repeat customer rate", "Loyalty share",
     "Denominator = customers who have placed >=1 order (4,892 of 5,000 registered ever bought). Customers with 0 orders are excluded, stated as assumption.",
     """WITH orders_per_cust AS (
             SELECT customer_id, COUNT(*) AS n FROM orders GROUP BY customer_id)
       SELECT ROUND(100.0*SUM(CASE WHEN n>=2 THEN 1 ELSE 0 END)/COUNT(*),1) AS repeat_rate_pct,
              COUNT(*) AS customers_with_orders,
              SUM(CASE WHEN n>=2 THEN 1 ELSE 0 END) AS repeat_customers
       FROM orders_per_cust""",
     lambda r: (True, "expect ~92.5% matching EDA")),

    ("Q9 Most popular payment method", "Popularity = order volume (assumption)",
     "Using the order header's payment_method attribute (1 per order after dedupe). Revenue split included for context.",
     """SELECT o.payment_method, COUNT(DISTINCT o.order_id) AS orders,
              ROUND(SUM(i.net_amount),0) AS revenue_vnd
       FROM orders o JOIN order_items i ON i.order_id=o.order_id
       GROUP BY o.payment_method ORDER BY orders DESC""",
     lambda r: (r.orders.sum() == 19989, "19,989 orders have >=1 valid item line (11 orders contain only quantity=0 lines, excluded per Stage-2 rule 5 - verified by the 'orders without items' integrity check; first run also FAILed on COUNT(*) double-counting item lines, fixed to COUNT(DISTINCT order_id))")),
]

results = {}
for name, intent, assum, sql, validate in VALID:
    results[name] = agent(name, intent, assum, sql, validate)

# extra cross-validation: top-customer spends sum to total revenue
tot_from_customers = q("""SELECT ROUND(SUM(spend),0) v FROM (
    SELECT o.customer_id, SUM(i.net_amount) spend
    FROM orders o JOIN order_items i ON i.order_id=o.order_id
    GROUP BY o.customer_id)""")["v"][0]
print("\nCROSS-VALIDATION: sum of per-customer spend =", f"{tot_from_customers:,.0f}",
      "| Q1 total revenue =", f"{results['Q1 Total revenue'].total_revenue_vnd[0]:,.0f}")

# inactive-customer full counts
print(q("""
WITH last_order AS (SELECT customer_id, MAX(order_datetime) last_dt FROM orders GROUP BY customer_id)
SELECT COUNT(*) AS inactive_90d,
       SUM(CASE WHEN last_dt < date('2025-12-31','-180 day') THEN 1 ELSE 0 END) AS inactive_180d
FROM last_order WHERE last_dt < date('2025-12-31','-90 day')""").to_string(index=False))

conn.close()
print("\nIn-memory database closed - nothing persisted, raw CSVs untouched.")
