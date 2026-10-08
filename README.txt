E-COMMERCE RAW DATASET – DATA ANALYST / AI AGENT PRACTICE

Bối cảnh:
Doanh nghiệp thương mại điện tử giả lập tại Việt Nam, bán hàng qua Website,
Mobile App và các marketplace.

Các file:
- customers_raw.csv      : thông tin khách hàng
- products_raw.csv       : sản phẩm / seller
- orders_raw.csv         : đơn hàng
- order_items_raw.csv    : chi tiết từng sản phẩm trong đơn
- payments_raw.csv       : giao dịch thanh toán

Quan hệ:
customers.customer_id  1:N orders.customer_id
orders.order_id        1:N order_items.order_id
products.product_id    1:N order_items.product_id
orders.order_id        1:N payments.order_id

Đây là dữ liệu RAW có chủ ý chứa lỗi:
- missing values
- duplicate records
- tên category không nhất quán
- date có nhiều format
- trailing spaces
- quantity = 0
- rating ngoài miền hợp lệ
- một số khóa ngoại bị thiếu
- status khác nhau về capitalization

Bài toán phù hợp:
- Data quality / profiling
- Sales & GMV
- Revenue, discount, margin
- AOV
- Product/category performance
- Channel performance
- Customer segmentation
- Repeat purchase / retention
- Return & refund analysis
- Payment failure
- Delivery performance
- Cohort analysis
- AI Data Analyst Agent