"""
Stage 6 - Golden-question regression suite
E-commerce AI Data Analyst project.

The questions the agent must NEVER get wrong, with exact expected values from
Stages 3-5. Run after any change to agent_core.py.
"""
import sqlite3
import agent_core as ac

conn = ac.get_connection()

GOLDEN = [
    ("What is total revenue?", "total_revenue", 28141523),
    ("What is the average order value?", "aov", 1410),
    ("What are the top 10 products by revenue?", "top_products", 552442),      # top1 revenue
    ("Which category generates the most revenue?", "category_revenue", 4695503),  # raw-label Thời trang
    ("What is the monthly revenue?", "monthly_revenue", 28141523),
    ("What is the repeat customer rate?", "repeat_rate", 92.5),
    ("Who are the top customers?", "top_customers", 23770),                    # top1 lifetime spend
    ("Which customers have not purchased recently?", "inactive_customers", None),
    ("Which payment method is most popular?", "popular_payment", 5598),        # COD orders
    ("Show me revenue by order status", "revenue_by_status", 21727455),        # Delivered
    ("top 5 products", "top_products", 552442),                                # param extraction
    ("customers inactive for 180 days", "inactive_customers", None),           # param extraction
]

# which column of each template's result should equal the expected value
CHECK_COL = {
    "top_products": "revenue_vnd",
    "top_customers": "lifetime_spend_vnd",
    "category_revenue": "revenue_vnd",
    "revenue_by_status": "revenue_vnd",
    "monthly_revenue": "revenue_vnd",
    "repeat_rate": "repeat_rate_pct",
    "popular_payment": "orders",
    "aov": "aov_vnd",
    "total_revenue": "total_revenue_vnd",
}

passed = failed = 0
for question, want_tpl, want_val in GOLDEN:
    s = ac.ask(conn, question)
    ok_tpl = s.get("template", {}).get("name") == want_tpl if isinstance(s.get("template"), dict) else False
    ok_status = s.get("status") == "ok"
    ok_val = True
    detail = ""
    if want_val is not None and "result" in s:
        df = s["result"]
        if want_tpl == "monthly_revenue":
            ok_val = abs(df.revenue_vnd.sum() - want_val) < 1
        elif want_tpl in ("top_products", "top_customers"):
            ok_val = len(df) <= 10 and abs(df[CHECK_COL[want_tpl]].iloc[0] - want_val) < 1
        elif want_tpl == "inactive_customers":
            ok_val = True  # no fixed value; row-level validation happens in agent
        else:
            ok_val = abs(df[CHECK_COL[want_tpl]].iloc[0] - want_val) < 1
        detail = f"expected {want_val}"
    ok = ok_tpl and ok_status and ok_val
    passed += ok
    failed += not ok
    print(("PASS" if ok else "FAIL"), "|", question, "->", s.get("template", {}).get("name") if isinstance(s.get("template"), dict) else s.get("status"), detail)

# guardrail negative tests
print("\nGuardrail tests:")
for bad_sql, why in [
    ("DELETE FROM orders", "G1 write"),
    ("SELECT * FROM sqlite_master", "G2 whitelist"),
    ("SELECT o.payment_method, COUNT(*) FROM orders o JOIN order_items i ON i.order_id=o.order_id", "G4 double count"),
]:
    ok, reason = ac.guardrail_check(bad_sql)
    print(("PASS" if not ok else "FAIL"), "| blocked:", why, "|", reason)

print(f"\nRegression: {passed}/{len(GOLDEN)} golden questions passed, {failed} failed")
conn.close()
