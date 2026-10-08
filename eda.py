"""
Stage 3 - Exploratory Data Analysis (EDA)
E-commerce AI Data Analyst project.

Rules respected:
- Raw CSVs in data/ are opened READ-ONLY. Nothing in data/ is modified.
- All outputs (charts, KPI tables, report) go to outputs/eda/.
- Cleaning rules come from the Stage 2 design (minimal, deterministic):
    * drop exact duplicate PK rows (orders: 20, order_items: 30)
    * strip whitespace in categoricals ('COD ' -> 'COD')
    * order_status lower -> Title ('delivered' -> 'Delivered')
    * exclude quantity == 0 rows from revenue (40 rows, quarantined logic)
    * rating > 5 treated as invalid (NULL) for rating KPIs (20 rows)
    * geo aliases mapped: HCM / Ho Chi Minh -> TP.HCM (both in city & region)
  Only Stage-2 🤖 auto-approvable rules are applied; nothing else is mutated.
"""
import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mt

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 50)

OUT = "outputs/eda"
os.makedirs(OUT, exist_ok=True)

VND = mt.FuncFormatter(lambda x, _: f"{x/1e9:.1f}B" if abs(x) >= 1e9 else (f"{x/1e6:.1f}M" if abs(x) >= 1e6 else f"{x/1e3:.0f}K"))

# ---------------------------------------------------------------- load
cust = pd.read_csv("data/customers_raw.csv")
prod = pd.read_csv("data/products_raw.csv")
orders = pd.read_csv("data/orders_raw.csv")
items = pd.read_csv("data/order_items_raw.csv")
pay = pd.read_csv("data/payments_raw.csv")

# ---------------------------------------------------------------- minimal cleaning (Stage-2 auto rules)
orders = orders.drop_duplicates()                      # 20 exact dup rows
items = items.drop_duplicates()                        # 30 exact dup rows
for c in ["payment_method", "channel", "order_status", "coupon_code", "region"]:
    orders[c] = orders[c].astype("string").str.strip()
orders["order_status"] = orders["order_status"].str.title()
GEO_MAP = {"HCM": "TP.HCM", "Ho Chi Minh": "TP.HCM"}
orders["region"] = orders["region"].replace(GEO_MAP)
cust["city"] = cust["city"].astype("string").str.strip().replace(GEO_MAP)

items = items[items["quantity"] > 0].copy()            # 40 zero-qty rows excluded
items["rating"] = items["rating"].where(items["rating"].between(1, 5))

orders["order_datetime"] = pd.to_datetime(orders["order_datetime"])
pay["payment_datetime"] = pd.to_datetime(pay["payment_datetime"])
cust["signup_date"] = pd.to_datetime(cust["signup_date"])

# ---------------------------------------------------------------- KPIs
# Logic:
#  Total Revenue      = sum(net_amount) over quantity>0 items (net = gross - discount)
#  Total Orders       = unique order_id in orders (after dedupe)
#  Total Customers    = unique customer_id in customers
#  AOV                = Total Revenue / paying orders (orders with >=1 item and payment Paid)
#  Products Sold      = sum(quantity)
#  Avg Rating         = mean of item ratings in [1,5] (NaN-safe)
rev_total = items["net_amount"].sum()
orders_with_items = orders[orders["order_id"].isin(items["order_id"])]
paid_orders = pay.loc[pay["payment_status"] == "Paid", "order_id"]
paid_orders = pd.Series(sorted(set(paid_orders) & set(items["order_id"])))
aov = items[items["order_id"].isin(paid_orders)]["net_amount"].sum() / len(paid_orders)

kpis = {
    "Total Revenue (net, VND)": f"{rev_total:,.0f}",
    "Total Orders (dedup)": f"{len(orders):,}",
    "Total Customers": f"{cust['customer_id'].nunique():,}",
    "AOV (paid orders, VND)": f"{aov:,.0f}",
    "Total Products Sold (units)": f"{items['quantity'].sum():,}",
    "Avg Item Rating (1-5)": f"{items['rating'].mean():.2f}",
    "Return Rate (item lines)": f"{items['return_flag'].mean()*100:.1f}%",
    "Payment Failure Rate": f"{(pay['payment_status']=='Failed').mean()*100:.1f}%",
}
kpi_df = pd.Series(kpis, name="value")
print("\n===== KPI SUMMARY ====="); print(kpi_df)

# revenue by category
cat = (items.merge(prod[["product_id", "category"]], on="product_id", how="left")
             .groupby("category")["net_amount"].sum().sort_values(ascending=False))
print("\n===== Revenue by Category ====="); print((cat/1e9).round(2).to_string())

# revenue by payment method (join order -> payment)
rev_pay = (pay.merge(orders[["order_id", "payment_method"]], on="order_id")
              .merge(items.groupby("order_id")["net_amount"].sum(), on="order_id")
              .groupby("payment_method")["net_amount"].sum().sort_values(ascending=False))
print("\n===== Revenue by Payment Method ====="); print((rev_pay/1e9).round(2).to_string())

# revenue by order status
rev_status = (items.merge(orders[["order_id", "order_status"]], on="order_id")
                   .groupby("order_status")["net_amount"].sum().sort_values(ascending=False))
print("\n===== Revenue by Order Status ====="); print((rev_status/1e9).round(2).to_string())

# monthly trend
orders["month"] = orders["order_datetime"].dt.to_period("M")
monthly = (items.merge(orders[["order_id", "month"]], on="order_id")
                .groupby("month")["net_amount"].sum())
print("\n===== Monthly Revenue (VND) ====="); print((monthly/1e9).round(2).to_string())

# best sellers
top_prod = (items.groupby("product_id")["net_amount"].sum()
                 .sort_values(ascending=False).head(10)
                 .to_frame("net_amount")
                 .join(prod.set_index("product_id")[["product_name", "category"]]))
print("\n===== Top 10 Products by Revenue ====="); print(top_prod.to_string())

top_cat_qty = (items.merge(prod[["product_id", "category"]], on="product_id")
                    .groupby("category").agg(revenue=("net_amount", "sum"),
                                             units=("quantity", "sum"),
                                             orders=("order_id", "nunique"))
                    .sort_values("revenue", ascending=False))
print("\n===== Category performance ====="); print(top_cat_qty.to_string())

# customer behaviour
cust_orders = orders.merge(items.groupby("order_id")["net_amount"].sum(), on="order_id")
per_cust = cust_orders.groupby("customer_id").agg(orders=("order_id", "nunique"),
                                                  spend=("net_amount", "sum"))
repeat = (per_cust["orders"] > 1).mean()
seg = (cust_orders.merge(cust[["customer_id", "customer_segment"]], on="customer_id")
                  .groupby("customer_segment")
                  .agg(customers=("customer_id", "nunique"),
                       orders=("order_id", "nunique"),
                       revenue=("net_amount", "sum")))
seg["rev_per_cust"] = seg["revenue"] / seg["customers"]
print("\n===== Customer behaviour =====")
print(f"repeat-purchase rate: {repeat*100:.1f}%  | orders/customer mean: {per_cust['orders'].mean():.2f} | median spend: {per_cust['spend'].median():,.0f}")
print(seg.sort_values("revenue", ascending=False).to_string())

# payments
pmix = pay["payment_status"].value_counts()
pay_fail = (pay.merge(orders[["order_id", "payment_method"]], on="order_id")
               .groupby("payment_method")["payment_status"]
               .apply(lambda s: (s == "Failed").mean() * 100).sort_values(ascending=False))
print("\n===== Payment failure rate by method (%) ====="); print(pay_fail.round(1).to_string())

# geography
geo = (orders.merge(items.groupby("order_id")["net_amount"].sum(), on="order_id")
             .groupby("region").agg(revenue=("net_amount", "sum"),
                                    orders=("order_id", "nunique")))
geo["aov"] = geo["revenue"] / geo["orders"]
print("\n===== Revenue by Region ====="); print((geo.sort_values("revenue", ascending=False) / 1).to_string())

# ---------------------------------------------------------------- charts
plt.rcParams.update({"figure.autolayout": True, "axes.spines.top": False, "axes.spines.right": False})

def save(fig, name):
    fig.savefig(f"{OUT}/{name}", dpi=150)
    plt.close(fig)
    print("chart saved:", name)

# 1 revenue over time
fig, ax = plt.subplots(figsize=(10, 4))
(monthly / 1e9).plot(ax=ax, marker="o", color="#2563eb")
ax.set_title("Monthly Net Revenue 2025 (VND billions)")
ax.set_ylabel("Revenue (B VND)"); ax.set_xlabel("")
ax.yaxis.set_major_formatter(mt.FuncFormatter(lambda x, _: f"{x:.1f}"))
save(fig, "01_revenue_over_time.png")

# 2 revenue by category
fig, ax = plt.subplots(figsize=(8, 4.5))
(cat / 1e9).sort_values().plot.barh(ax=ax, color="#059669")
ax.set_title("Net Revenue by Category (B VND)")
ax.xaxis.set_major_formatter(VND)
save(fig, "02_revenue_by_category.png")

# 3 top 10 products
fig, ax = plt.subplots(figsize=(9, 4.5))
tp = (top_prod["net_amount"] / 1e6).sort_values()
ax.barh([f"{p} ({c})" for p, c in zip(tp.index, top_prod.loc[tp.index, 'category'])], tp.values, color="#7c3aed")
ax.set_title("Top 10 Products by Net Revenue (M VND)")
save(fig, "03_top10_products.png")

# 4 orders by status
fig, ax = plt.subplots(figsize=(7, 4))
orders["order_status"].value_counts().plot.bar(ax=ax, color="#d97706")
ax.set_title("Orders by Status (dedup, cleaned)")
for i, v in enumerate(orders["order_status"].value_counts().values):
    ax.text(i, v, f"{v:,}", ha="center", va="bottom", fontsize=8)
save(fig, "04_orders_by_status.png")

# 5 payment methods
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
pay["payment_status"].value_counts().plot.pie(autopct="%1.1f%%", ax=axes[0], title="Payment status mix")
rev = (pay.merge(orders[["order_id", "payment_method"]], on="order_id")
          .merge(items.groupby("order_id")["net_amount"].sum(), on="order_id")
          .groupby("payment_method")["net_amount"].sum().sort_values())
axes[1].barh(rev.index, rev.values / 1e9, color="#0891b2")
axes[1].set_title("Net Revenue by Payment Method (B VND)")
save(fig, "05_payment_methods.png")

# 6 geography (bonus)
fig, ax = plt.subplots(figsize=(8, 4.5))
(geo.sort_values("revenue")["revenue"] / 1e9).plot.barh(ax=ax, color="#dc2626")
ax.set_title("Net Revenue by Region (B VND)")
save(fig, "06_revenue_by_region.png")

# 7 customer segments (bonus)
fig, ax = plt.subplots(figsize=(7, 4))
(seg.sort_values("revenue")["revenue"] / 1e9).plot.barh(ax=ax, color="#4f46e5")
ax.set_title("Net Revenue by Customer Segment (B VND)")
save(fig, "07_revenue_by_segment.png")

# ---------------------------------------------------------------- save tables + report
kpi_df.to_csv(f"{OUT}/kpi_summary.csv")
cat.to_frame("net_revenue").to_csv(f"{OUT}/revenue_by_category.csv")
top_prod.to_csv(f"{OUT}/top10_products.csv")
top_cat_qty.to_csv(f"{OUT}/category_performance.csv")
seg.to_csv(f"{OUT}/segment_performance.csv")
geo.to_csv(f"{OUT}/region_performance.csv")
monthly.to_frame("net_revenue").to_csv(f"{OUT}/monthly_revenue.csv")
pay_fail.to_frame("fail_rate_pct").to_csv(f"{OUT}/payment_failure_by_method.csv")

with open(f"{OUT}/EDA_REPORT.md", "w", encoding="utf-8") as f:
    f.write(f"""# Stage 3 - EDA Report (generated {pd.Timestamp.now():%Y-%m-%d %H:%M})

## Cleaning applied (Stage-2 auto-approved rules only)
- Dropped exact duplicate rows: orders 20, order_items 30
- Stripped whitespace in order categoricals ('COD ' -> 'COD')
- order_status 'delivered' -> 'Delivered'
- Geo aliases HCM / Ho Chi Minh -> TP.HCM
- Excluded 40 quantity=0 item lines from revenue
- Treated 20 ratings=6 as invalid (NULL)
No raw file was modified.

## KPI Summary
```
{kpi_df.to_string()}
```

## Revenue by Category (B VND)
```
{(cat/1e9).round(2).to_string()}
```

## Monthly Revenue (B VND)
```
{(monthly/1e9).round(2).to_string()}
```

## Category performance
```
{top_cat_qty.to_string()}
```

## Segment performance
```
{seg.sort_values('revenue', ascending=False).to_string()}
```

## Region performance
```
{geo.sort_values('revenue', ascending=False).round(0).to_string()}
```

## Payment failure rate by method (%)
```
{pay_fail.round(1).to_string()}
```

## Top 10 products
```
{top_prod.to_string()}
```

## Charts
1. 01_revenue_over_time.png
2. 02_revenue_by_category.png
3. 03_top10_products.png
4. 04_orders_by_status.png
5. 05_payment_methods.png
6. 06_revenue_by_region.png
7. 07_revenue_by_segment.png
""")
print("\nAll EDA artifacts written to", OUT)
