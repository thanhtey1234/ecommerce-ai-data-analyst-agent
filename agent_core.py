"""
Stage 6 - Production AI Data Analyst Agent (core)
E-commerce AI Data Analyst project.

Single reusable core shared by the golden-question regression suite (golden_questions.py)
and the CLI (cli_agent.py).

Design decisions (confirmed with user): deterministic NL intent parsing +
validated SQL templates (no LLM). The template registry below is the exact
interface an LLM planner would implement later.

Agent loop:
    USER QUESTION -> UNDERSTAND INTENT -> PLAN (template + params)
    -> GENERATE SQL -> GUARDRAIL CHECK -> EXECUTE -> VALIDATE -> EXPLAIN RESULT

Guardrails (codified from Stage 4 lessons):
    G1 SELECT-only statements (no INSERT/UPDATE/DELETE/DROP/ATTACH/PRAGMA...)
    G2 table whitelist (5 tables + quarantine table)
    G3 result row limit
    G4 anti-double-count rule: COUNT(*) on a joined items query is rejected at
       template level (templates use COUNT(DISTINCT order_id) where needed)
    G5 raw CSVs are read-only; DB is in-memory; nothing persisted
"""
import re
import sqlite3
import pandas as pd

ROW_LIMIT = 200

# ------------------------------------------------------------------ shared clean loader
# Single source of truth for the Stage-2 AUTO-approved cleaning rules
# (previously duplicated in eda.py and sql_agent.py).
CLEAN_RULES = [
    "drop exact duplicate rows on PKs (orders -20, order_items -30)",
    "strip whitespace in order categoricals ('COD ' -> 'COD')",
    "order_status 'delivered' -> 'Delivered'",
    "geo aliases HCM / Ho Chi Minh -> TP.HCM",
    "exclude quantity=0 item lines from fact (kept in order_items_excluded for audit)",
    "ratings outside [1,5] set to NULL",
]


def get_connection():
    """In-memory SQLite with the cleaned star schema. Raw CSVs are never touched."""
    conn = sqlite3.connect(":memory:")
    cust = pd.read_csv("data/customers_raw.csv")
    prod = pd.read_csv("data/products_raw.csv")
    orders = pd.read_csv("data/orders_raw.csv").drop_duplicates()
    items_all = pd.read_csv("data/order_items_raw.csv").drop_duplicates()
    pay = pd.read_csv("data/payments_raw.csv")

    for c in ["payment_method", "channel", "order_status", "coupon_code", "region"]:
        orders[c] = orders[c].astype("string").str.strip()
    orders["order_status"] = orders["order_status"].str.title()
    orders["region"] = orders["region"].replace({"HCM": "TP.HCM", "Ho Chi Minh": "TP.HCM"})
    cust["city"] = cust["city"].astype("string").str.strip().replace({"HCM": "TP.HCM", "Ho Chi Minh": "TP.HCM"})

    items = items_all[items_all["quantity"] > 0].copy()
    items["rating"] = items["rating"].where(items["rating"].between(1, 5))

    for name, df in [("customers", cust), ("products", prod), ("orders", orders),
                     ("order_items", items), ("payments", pay),
                     ("order_items_excluded", items_all[items_all["quantity"] == 0])]:
        df.to_sql(name, conn, index=False, if_exists="replace")
    return conn


# ------------------------------------------------------------------ SQL templates
# Each template: intent keywords, parameter extractors, SQL builder, validator,
# explanation. This registry IS the planner interface.
TEMPLATES = [
    dict(
        name="total_revenue",
        keywords=[r"total revenue", r"revenue in total", r"how much revenue"],
        params=[],
        sql="SELECT ROUND(SUM(net_amount),0) AS total_revenue_vnd, COUNT(*) AS item_lines FROM order_items",
        validate=lambda df: abs(df.total_revenue_vnd[0] - 28141523) < 1,
        validate_msg="equals pandas ground truth 28,141,523 VND (Stage 3/4)",
        explain="Revenue = SUM(net_amount) over valid item lines (quantity>0). No join needed; "
                "joins can only filter, and 1-payment-per-order was verified in Stage 4.",
    ),
    dict(
        name="aov",
        keywords=[r"average order value", r"\baov\b", r"average basket"],
        params=[],
        sql="""WITH order_rev AS (
                 SELECT i.order_id, SUM(i.net_amount) AS net
                 FROM order_items i
                 JOIN payments p ON p.order_id=i.order_id AND p.payment_status='Paid'
                 GROUP BY i.order_id)
               SELECT ROUND(AVG(net),0) AS aov_vnd, COUNT(*) AS paid_orders FROM order_rev""",
        validate=lambda df: abs(df.aov_vnd[0] - 1410) < 1 and df.paid_orders[0] == 14997,
        validate_msg="equals Stage 4 ground truth (1,410 VND over 14,997 paid orders)",
        explain="Orders aggregated to one row each BEFORE averaging (AVG over the raw item join would "
                "line-weight multi-line orders: ~828, wrong). Only payment_status='Paid' counts (assumption).",
    ),
    dict(
        name="top_products",
        keywords=[r"top (?:10 )?products", r"best.?selling products", r"best products", r"top \d+ products"],
        params=[("n", r"top (\d+)", 10)],
        sql_fn=lambda n: f"""SELECT p.product_id, p.product_name, p.category,
                   ROUND(SUM(i.net_amount),0) AS revenue_vnd, SUM(i.quantity) AS units_sold
               FROM order_items i JOIN products p ON p.product_id=i.product_id
               GROUP BY p.product_id ORDER BY revenue_vnd DESC LIMIT {int(n)}""",
        validate=lambda df: df.revenue_vnd.is_monotonic_decreasing and len(df) <= ROW_LIMIT,
        validate_msg="strictly ordered by revenue, no fan-out (products joined 1:1 after grouping)",
        explain="Group the item fact by product FIRST, then join the dimension for names - the safe "
                "order to avoid double counting.",
    ),
    dict(
        name="category_revenue",
        keywords=[r"revenue by category", r"best category", r"which category", r"category generates"],
        params=[],
        sql="""SELECT COALESCE(p.category,'(no product_id)') AS category,
                 ROUND(SUM(i.net_amount),0) AS revenue_vnd, COUNT(DISTINCT i.order_id) AS orders
               FROM order_items i LEFT JOIN products p ON p.product_id=i.product_id
               GROUP BY category ORDER BY revenue_vnd DESC""",
        validate=lambda df: abs(df.revenue_vnd.sum() - 28141523) < 1,
        validate_msg="categories sum to total revenue (no leakage; LEFT JOIN keeps 20 NULL-product lines)",
        explain="LEFT JOIN products so the 20 item lines with missing product_id appear in an explicit "
                "bucket instead of being silently dropped (bug caught and fixed in Stage 4).",
    ),
    dict(
        name="monthly_revenue",
        keywords=[r"monthly revenue", r"revenue (?:by|per) month", r"revenue trend"],
        params=[],
        sql="""SELECT strftime('%Y-%m', o.order_datetime) AS month,
                 ROUND(SUM(i.net_amount),0) AS revenue_vnd, COUNT(DISTINCT o.order_id) AS orders
               FROM order_items i JOIN orders o ON o.order_id=i.order_id
               GROUP BY month ORDER BY month""",
        validate=lambda df: len(df) == 12 and abs(df.revenue_vnd.sum() - 28141523) < 1,
        validate_msg="12 months, sum equals total revenue",
        explain="Items joined to deduped orders (unique order_id) -> no fan-out.",
    ),
    dict(
        name="repeat_rate",
        keywords=[r"repeat (?:customer|purchase) rate", r"repeat rate"],
        params=[],
        sql="""WITH opc AS (SELECT customer_id, COUNT(*) n FROM orders GROUP BY customer_id)
               SELECT ROUND(100.0*SUM(CASE WHEN n>=2 THEN 1 ELSE 0 END)/COUNT(*),1) AS repeat_rate_pct,
                      COUNT(*) AS customers_with_orders
               FROM opc""",
        validate=lambda df: abs(df.repeat_rate_pct[0] - 92.5) < 0.05,
        validate_msg="equals Stage 3/4 ground truth (92.5%)",
        explain="Share of customers-with-orders having >=2 orders. Customers who registered but never "
                "ordered are excluded (assumption, stated in every answer).",
    ),
    dict(
        name="top_customers",
        keywords=[r"top customers", r"best customers", r"top (?:\d+ )?customers by"],
        params=[("n", r"top (\d+)", 10)],
        sql_fn=lambda n: f"""WITH cr AS (
                   SELECT o.customer_id, COUNT(DISTINCT o.order_id) AS orders, SUM(i.net_amount) AS spend
                   FROM orders o JOIN order_items i ON i.order_id=o.order_id GROUP BY o.customer_id)
               SELECT c.customer_id, c.customer_name, c.customer_segment, cr.orders,
                      ROUND(cr.spend,0) AS lifetime_spend_vnd
               FROM cr JOIN customers c ON c.customer_id=cr.customer_id
               ORDER BY cr.spend DESC LIMIT {int(n)}""",
        validate=lambda df: df.lifetime_spend_vnd.is_monotonic_decreasing,
        validate_msg="ordered by lifetime spend; per-customer aggregation avoids order-line fan-out",
        explain="Aggregate items per order/customer, then rank. customer_id is unique in customers (verified).",
    ),
    dict(
        name="inactive_customers",
        keywords=[r"not purchased recently", r"inactive (?:for )?\d* ?days?", r"inactive customers", r"haven'?t (?:purchased|ordered)", r"churn"],
        params=[("days", r"(\d+)\s*days?", 90)],
        sql_fn=lambda days: f"""WITH lo AS (
                   SELECT customer_id, MAX(order_datetime) AS last_dt FROM orders GROUP BY customer_id)
               SELECT c.customer_id, c.customer_name, c.city, lo.last_dt,
                      CAST(julianday('2025-12-31') - julianday(lo.last_dt) AS INT) AS days_since
               FROM lo JOIN customers c ON c.customer_id=lo.customer_id
               WHERE lo.last_dt < date('2025-12-31','-{int(days)} day')
               ORDER BY days_since DESC LIMIT {ROW_LIMIT}""",
        validate=lambda df: (df.days_since.astype(float) >= 90).all(),
        validate_msg="every returned customer exceeded the inactivity threshold",
        explain="'Recently' = within the last N days of the observation window (dataset ends 2025-12-31).",
    ),
    dict(
        name="popular_payment",
        keywords=[r"payment method", r"most popular payment", r"popular payment"],
        params=[],
        sql="""SELECT o.payment_method, COUNT(DISTINCT o.order_id) AS orders,
                 ROUND(SUM(i.net_amount),0) AS revenue_vnd
               FROM orders o JOIN order_items i ON i.order_id=o.order_id
               GROUP BY o.payment_method ORDER BY orders DESC""",
        validate=lambda df: df.orders.sum() == 19989,
        validate_msg="19,989 = orders with >=1 valid item line (11 orders contain only qty=0 lines)",
        explain="COUNT(DISTINCT order_id), NOT COUNT(*) - the Stage 4 lesson: counting over the items join "
                "would return 31,114 item lines, not orders.",
    ),
    dict(
        name="revenue_by_status",
        keywords=[r"revenue by (?:order )?status", r"cancel(?:led|lation) rate", r"order status"],
        params=[],
        sql="""SELECT o.order_status, COUNT(DISTINCT o.order_id) AS orders,
                 ROUND(SUM(i.net_amount),0) AS revenue_vnd
               FROM orders o JOIN order_items i ON i.order_id=o.order_id
               GROUP BY o.order_status ORDER BY revenue_vnd DESC""",
        validate=lambda df: abs(df.revenue_vnd.sum() - 28141523) < 1,
        validate_msg="status split sums to total revenue",
        explain="Status is a header attribute; items aggregated per order keep the order grain intact.",
    ),
]


# ------------------------------------------------------------------ guardrails
FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex)\b", re.I)
ALLOWED_TABLES = {"customers", "products", "orders", "order_items", "payments", "order_items_excluded"}


def guardrail_check(sql):
    """Returns (ok, reason). Raises nothing; caller reports to the user."""
    if not re.search(r"\bselect\b", sql, re.I):
        return False, "G1: only SELECT statements are allowed"
    if FORBIDDEN.search(sql):
        return False, "G1: write/DDL keywords are forbidden"
    # CTE aliases (WITH name AS ...) must not be treated as tables
    cte_names = {m.lower() for m in re.findall(r"\bwith\s+([a-z_]+)\s+as\s*\(", sql, re.I)}
    tables = {t.lower() for t in re.findall(r"\b(?:from|join)\s+([a-z_]+)", sql, re.I)} - cte_names
    bad = tables - ALLOWED_TABLES
    if bad:
        return False, f"G2: table(s) not allowed: {bad}"
    # G4: the exact Stage-4 bug pattern - COUNT(*) over an orders<->order_items join
    # counts item LINES, not orders (31,114 instead of 19,989 in the Stage-4 run).
    if re.search(r"\bcount\s*\(\s*\*\s*\)", sql, re.I) and re.search(r"\bjoin\s+order_items\b", sql, re.I):
        return False, "G4: COUNT(*) over an orders JOIN order_items query counts item lines, not orders - use COUNT(DISTINCT order_id)"
    return True, "all guardrails passed (G1 select-only, G2 table whitelist, G4 anti-double-count)"


# ------------------------------------------------------------------ intent parsing
def understand(question):
    """UNDERSTAND INTENT + PLAN: match question text to a template; extract params."""
    ql = question.lower()
    best, best_score = None, 0
    for t in TEMPLATES:
        score = sum(1 for kw in t["keywords"] if re.search(kw, ql))
        if score > best_score:
            best, best_score = t, score
    if best is None:
        return None
    params = {}
    for pname, pat, default in best.get("params", []):
        m = re.search(pat, ql)
        params[pname] = int(m.group(1)) if m else default
    return best, params


def generate_sql(tpl, params):
    return tpl["sql"] if "sql" in tpl else tpl["sql_fn"](**params)


# ------------------------------------------------------------------ agent loop
def ask(conn, question, verbose=True):
    """Full agent loop. Returns dict with all intermediate steps for UI/tests."""
    steps = {"question": question, "status": None}
    plan = understand(question)
    if plan is None:
        steps["status"] = "unmatched"
        steps["explain"] = ("No validated template matches this question. The deterministic agent only "
                            "answers questions covered by its template registry (see TEMPLATES). "
                            "An LLM planner would extend coverage; guardrails would still apply.")
        return steps
    tpl, params = plan
    steps["intent"], steps["template"], steps["params"] = tpl["name"], tpl, params
    steps["sql"] = generate_sql(tpl, params)

    ok, reason = guardrail_check(steps["sql"])
    steps["guardrail"] = (ok, reason)
    if not ok:
        steps["status"] = "blocked"
        steps["explain"] = reason
        return steps

    df = pd.read_sql(steps["sql"], conn)
    steps["result"] = df.head(ROW_LIMIT)
    try:
        ok = tpl["validate"](steps["result"])
        steps["validation"] = (bool(ok), tpl["validate_msg"])
        steps["status"] = "ok" if ok else "validation_failed"
    except Exception as e:  # validator crashed = validation failed, never silently pass
        steps["validation"] = (False, f"validator error: {e}")
        steps["status"] = "validation_failed"
    steps["explain"] = tpl["explain"] + f" [params: {params}]" if params else tpl["explain"]
    return steps


def print_answer(s):
    print("=" * 78)
    print("QUESTION :", s["question"])
    print("INTENT   :", s.get("intent", "-"))
    print("GUARDRAIL:", s.get("guardrail", ("?",))[1] if "guardrail" in s else "-")
    if s.get("status") in ("ok", "validation_failed"):
        print("SQL      :", s["sql"].strip())
        print("RESULT   :")
        print(s["result"].to_string(index=False))
        ok, msg = s["validation"]
        print("VALIDATE :", "PASS -" if ok else "FAIL -", msg)
    print("EXPLAIN  :", s["explain"])
