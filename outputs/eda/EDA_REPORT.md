# Stage 3 - EDA Report (generated 2026-10-08 23:47)

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
Total Revenue (net, VND)       28,141,523
Total Orders (dedup)               20,000
Total Customers                     5,000
AOV (paid orders, VND)              1,410
Total Products Sold (units)        43,676
Avg Item Rating (1-5)                4.04
Return Rate (item lines)             4.2%
Payment Failure Rate                 7.8%
```

## Revenue by Category (B VND)
```
category
Thời trang    0.0
Gia dụng      0.0
Mỹ phẩm       0.0
Phụ kiện      0.0
Điện thoại    0.0
Laptop        0.0
Thể thao      0.0
Mẹ & Bé       0.0
Thoi trang    0.0
gia dụng      0.0
thời trang    0.0
thể thao      0.0
phụ kiện      0.0
mỹ phẩm       0.0
mẹ & bé       0.0
laptop        0.0
```

## Monthly Revenue (B VND)
```
month
2025-01    0.0
2025-02    0.0
2025-03    0.0
2025-04    0.0
2025-05    0.0
2025-06    0.0
2025-07    0.0
2025-08    0.0
2025-09    0.0
2025-10    0.0
2025-11    0.0
2025-12    0.0
Freq: M
```

## Category performance
```
              revenue  units  orders
category                            
Thời trang  4695503.0   7924    5212
Gia dụng    4194933.0   6298    4159
Mỹ phẩm     4043440.0   5749    3848
Phụ kiện    3485350.0   5541    3760
Điện thoại  3431788.0   4555    3073
Laptop      3038914.0   4905    3304
Thể thao    1766640.0   2829    1933
Mẹ & Bé     1131546.0   2282    1586
Thoi trang   932696.0   1419     993
gia dụng     638183.0    730     512
thời trang   225487.0    582     411
thể thao     146508.0    174     117
phụ kiện     135515.0    281     198
mỹ phẩm       89634.0    139     106
mẹ & bé       87471.0    116      91
laptop        74514.0    124      87
```

## Segment performance
```
                  customers  orders     revenue  rev_per_cust
customer_segment                                             
Regular                2159    8873  12429062.0   5756.860584
New                    1422    5728   8129451.0   5716.913502
Loyal                  1069    4370   6142567.0   5746.086997
VIP                     242    1018   1440443.0   5952.243802
```

## Region performance
```
              revenue  orders     aov
region                               
TP.HCM      7941871.0    5717  1389.0
Hà Nội      5486850.0    3859  1422.0
Khác        5128205.0    3676  1395.0
Đà Nẵng     2171142.0    1559  1393.0
Đồng Nai    2095179.0    1455  1440.0
Bình Dương  2014871.0    1435  1404.0
Hải Phòng   1769637.0    1215  1456.0
Cần Thơ     1533768.0    1073  1429.0
```

## Payment failure rate by method (%)
```
payment_method
E-wallet         8.3
VNPay            8.0
Credit Card      7.8
COD              7.3
Bank Transfer    7.2
```

## Top 10 products
```
            net_amount product_name    category
product_id                                     
P1224         552442.0  Product_225  Điện thoại
P1217         452795.0  Product_218  Điện thoại
P1259         413786.0  Product_260     Mỹ phẩm
P1033         378673.0   Product_34    Gia dụng
P1037         363289.0   Product_38    Gia dụng
P1230         320103.0  Product_231     Mỹ phẩm
P1026         286966.0   Product_27     Mỹ phẩm
P1186         282970.0  Product_187    Gia dụng
P1188         268097.0  Product_189  Thời trang
P1124         261930.0  Product_125    gia dụng
```

## Charts
1. 01_revenue_over_time.png
2. 02_revenue_by_category.png
3. 03_top10_products.png
4. 04_orders_by_status.png
5. 05_payment_methods.png
6. 06_revenue_by_region.png
7. 07_revenue_by_segment.png
