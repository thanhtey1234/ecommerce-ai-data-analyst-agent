# Stage 5 — Business Analyst Report
Generated from verified results of Stages 1–4 (profiling, DQ design, EDA, SQL). All metrics computed from the raw CSVs (read-only); money in VND; revenue basis = net_amount over valid item lines (31,114), total = 28,141,523.

Legend: **[FACT]** measured directly · **[HYP]** hypothesis/inference · 💭 = pattern typical of synthetic data, treat strategy conclusions with caution.

## Executive Summary
The business is a ~28.1M VND/year operation with 20,000 orders, 5,000 customers and an extraordinarily loyal base (92.5% repeat rate, 4.09 orders/customer). Growth is flat (±14% monthly spread, no seasonality). The two largest quantified risks are **retention** (35.9% of buyers inactive >90 days = 28.0% of historical revenue) and **checkout leakage** (7.7% of revenue at risk from failed payments, 5.9% lost to cancellations, 4.2% to returns ≈ 17.8% combined gross drag). Marketing spend is not buying value: 51.8% of orders carry a coupon with zero AOV lift. ⚠️ Two data caveats gate all conclusions: (1) shipping/transaction-fee and refund columns are on an implausible scale (fees ≈ 37× revenue) and are excluded from all profitability math pending investigation; (2) several patterns (uniform AOV across channels/regions, uniform payment-failure rates, flat trend) are atypical of real e-commerce and suggest synthetic generation — recommendations are framed to be re-validated once data provenance is confirmed.

## Findings (with full analysis chain)

### F1. Revenue is flat — no growth engine [FACT]
- Metric: monthly revenue 2.216M (Jun) → 2.527M (May); 12-month range ~14%; no Nov/Dec spike.
- Why it matters: at ~0% organic growth, every KPI improvement must come from execution, not market tailwind.
- Likely cause 💭[HYP]: synthetic uniform generation, OR genuine market saturation/ad-budget cap.
- Action: shift focus to base monetization (retention, AOV) before acquisition spend. Validate with: real ad-spend and traffic data.

### F2. Retention is the biggest quantified lever [FACT]
- Metric: 1,757 of 4,892 purchasers (35.9%) haven't ordered in 90+ days → historically worth 7.87M (28.0% of revenue); 640 (13.1%) dormant >180 days (2.09M, 7.4%); 108 registered customers never purchased.
- Why it matters: with 92.5% aggregate repeat rate, losing ~36% of the base to dormancy while everyone else repeats suggests a hard cutoff in engagement, not gradual churn.
- Likely cause [HYP]: no re-engagement program; possible data-generation cutoff effect. 💭
- Action (R1): 90-day win-back flow (email/ZNS voucher) targeted at the 1,757; reactivate 10% → ~0.8M/yr. Validate with: contact/consent data, campaign history, churn timing distribution.

### F3. Checkout leakage: payments, cancellations, returns ≈ 17.8% gross drag [FACT]
- Metric: Failed payments 1,551 → 2.15M revenue at risk (7.7%); Cancelled 1,200 orders → 1.67M (5.9%); Returned 1,312 lines → 1.18M (4.2%).
- Why it matters: combined ~5.0M (17.8%) never converts; each point recovered is pure top-line.
- Likely cause [HYP]: payment-gateway reliability (uniform 7.2–8.3% failure by method — suspiciously uniform 💭), unmanaged cart abandonment, sizing/quality issues in returns.
- Action (R2): payment-retry + fallback routing; measure failure→recovery. Impact [HYP]: recovering 30% of failures ≈ 0.65M (+2.3%).

### F4. Coupons cost 4.4% of revenue with zero measured lift [FACT]
- Metric: 10,357 coupon orders (51.8%); discounts given 1.24M (4.4% of revenue); AOV with coupon 1,403 vs without 1,413.
- Why it matters: ~1.2M/yr of margin spent with no detectable basket-size or frequency benefit in this data.
- Likely cause [HYP]: coupons applied indiscriminately (51.8% attach rate is very high); attribution absent.
- Action (R3): A/B gate coupons to targeted segments; require lift measurement. Impact [HYP]: halving unattributed discount cost ≈ 0.6M margin (+2.1%). Validate with: pre/post experiment data, coupon source (none exists today).

### F5. Segmentation labels don't reflect value [FACT]
- Metric: revenue per customer — VIP 5,952 vs Loyal 5,746 / Regular 5,757 / New 5,717 (≤4% spread).
- Why it matters: "VIP" isn't operationally meaningful; segment-targeted offers can't be prioritized by value.
- Likely cause 💭[HYP]: segment assigned at random/birth, not derived from behavior.
- Action (R4): rebuild segments from RFM (recency, frequency, monetary) computed from orders; re-map campaigns. Validate with: segment-definition metadata from source system.

### F6. Category mix is broad but shallow; canonical mapping changes conclusions [FACT]
- Metric (canonical): Thời trang 5.85M (20.8%) + Gia dụng 4.83M (17.2%) = 38.0% of revenue; ratings 4.03–4.09 and return rates 4.0–4.4% nearly uniform across categories (Điện thoại worst returns 4.9%); top product = only 2.0% of revenue.
- Why it matters: no category is a quality problem and no hero SKU exists — revenue risk is spread across 300 products. **Correction to Stage 3:** the "Mẹ & Bé lowest-rated/highest-returns" signal was an artifact of raw 16-label grouping; it disappears after canonicalization. This is why the category map approval mattered.
- Likely cause 💭[HYP]: uniform synthetic distribution.
- Action (R5): after data-provenance confirmation, invest in assortment depth in top-2 categories rather than spread; KPI per category tracked monthly.

### F7. Channel mix: Mobile App leads volume, Website leads AOV, Tiki is marginal [FACT]
- Metric: Mobile App 4,730 orders / 6.62M; Website highest AOV 1,448; Tiki 1,332 orders / 1.89M (6.7%); AOV spread across channels only 1,364–1,448.
- Why it matters: near-identical AOV suggests channel doesn't change basket size — investment should follow volume & cost, not AOV dreams.
- Likely cause 💭[HYP]: uniform generation; in reality marketplace fees differ (unavailable in data).
- Action: consolidate Tiki effort unless marketplace-fee data shows otherwise. Validate with: commission/fee schedules per channel.

### F8. Geographic concentration [FACT]
- Metric: TP.HCM 7.94M (28.2%); top-3 regions ≈ 66%; regional AOV flat (1,389–1,456).
- Action: keep logistics capacity weighted to HCM/HN; no region-specific pricing lever visible in data.

### F9. Data trust issues gate everything [FACT]
- Metric: fees 1.03B vs revenue 28.1M (37×); shipping fee exceeds order value in 98% of orders; refunds total 13× revenue; every refund > its order value.
- Why it matters: no margin, CAC, or unit-economics statement is currently possible.
- Action (P0, precedes all): resolve fee/refund scale; then re-issue margin analysis.

## Top 5 Recommendations (prioritized by impact × difficulty)

| # | Recommendation | Priority | Basis | Expected impact [HYP unless noted] |
|---|---|---|---|---|
| R0 | Resolve fee/refund scale anomaly; re-issue margin & unit economics | **P0 — blocker** | F9, 1.03B fees vs 28.1M revenue | Unblocks all profitability decisions |
| R1 | 90-day win-back program for 1,757 dormant buyers (28% of revenue exposure) | **P1 — high impact, low difficulty** | F2 | ~0.8M/yr if 10% reactivate |
| R2 | Payment-failure recovery (auto-retry, fallback method, COD confirmation flow) | **P1 — high impact, medium difficulty** | F3, 2.15M at risk | +0.65M (+2.3%) if 30% recovered |
| R3 | Coupon governance: cut untargeted coupons, A/B with lift measurement | **P2 — margin, low difficulty** | F4, 1.24M discounts, zero lift | +0.6M margin if waste halved |
| R4 | Rebuild customer segments on RFM; retarget by value not label | **P2 — medium difficulty** | F5, F1 | Better ROI of all campaigns; enables R1/R3 targeting |
| R5 | (Conditional) Assortment focus in Thời trang + Gia dụng once data provenance confirmed | **P3 — conditional** | F6 | Directional; needs demand-side data |

## Metrics to monitor after implementation
1. **90-day active rate** (share of purchasers ordering in trailing 90d) — baseline 64.1%
2. **Payment success rate** — baseline 92.2% (15,005/20,000... Paid share 75.0%; failure 7.8%)
3. **Realized-revenue rate** = Delivered revenue ÷ total order revenue — baseline 77.2%
4. **Coupon ROI** (incremental revenue ÷ discount cost) — baseline undefined (no experiments)
5. **Revenue per active customer** — baseline 5,746 (per purchaser)
6. **Return rate** — baseline 4.2% of item lines (1.18M)
7. **Monthly revenue & MoM growth** — baseline ~2.34M avg, ~0% growth
8. **Cancellation rate** — baseline 6.0%

## Data needed to validate recommendations
- Ad-spend & traffic by channel/source (CAC, ROAS) — absent today
- Marketplace commission schedules per channel (Tiki vs Website true economics)
- Coupon redemption metadata (source, eligibility, experiment arms)
- Correct-unit fee/refund data or confirmation of synthetic generation
- Consent/contact channels for win-back campaigns
