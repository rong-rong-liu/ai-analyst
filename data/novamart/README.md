# NovaMart Dataset

## What is NovaMart?

NovaMart is a **fictional mid-stage e-commerce marketplace** (think Amazon-like) that serves as the built-in practice dataset. It includes:

- **Multi-platform presence** -- web, iOS, and Android apps
- **NovaMart Plus** -- a paid delivery membership program (like Amazon Prime)
- **Multi-channel acquisition** -- organic, paid search, social, referral, email, and TikTok ads
- **Full-funnel behavioral data** -- from page views through checkout and purchase

The dataset covers **January through December 2024** and contains approximately 50,000 users with 6.5 million behavioral events. All data is synthetic but designed to behave like a real e-commerce product -- including realistic conversion funnels, seasonality, and segmentation patterns worth investigating.

---

## Schema Overview

The dataset has **13 tables**: 4 dimension tables, 8 fact/transactional tables, and 1 helper table.

### Dimension Tables

#### `users` -- ~50,000 rows
One row per registered user.

| Column | Type | Description |
|--------|------|-------------|
| user_id | INTEGER | Unique user identifier (primary key) |
| signup_date | DATE | Account creation date |
| signup_timestamp | TIMESTAMP | Exact account creation time |
| acquisition_channel | TEXT | How the user found NovaMart: `organic`, `paid_search`, `social`, `referral`, `email`, `tiktok_ads` |
| country | TEXT | User country: `US`, `UK`, `CA`, `DE`, `AU`, `other` |
| device_primary | TEXT | Primary device at signup: `web`, `ios`, `android` |
| age_bucket | TEXT | Age range: `18-24`, `25-34`, `35-44`, `45-54`, `55+` |
| gender | TEXT | `M`, `F`, `other`, `unknown` |

#### `products` -- 500 rows
One row per product SKU.

| Column | Type | Description |
|--------|------|-------------|
| product_id | INTEGER | Unique product identifier (primary key) |
| product_name | TEXT | Human-readable product name |
| category | TEXT | Product category: `electronics`, `home`, `clothing`, `beauty`, `sports`, `books` |
| subcategory | TEXT | More specific grouping within category (e.g., `headphones`, `skincare`, `fiction`) |
| price | DECIMAL | Retail price in USD ($5.99 - $499.99) |
| cost | DECIMAL | Unit cost (40-70% of price, varies by category) |
| is_plus_eligible | BOOLEAN | Whether the product qualifies for Plus free shipping |

#### `promotions` -- 5 rows
One row per promotion.

| Column | Type | Description |
|--------|------|-------------|
| promo_id | INTEGER | Unique promotion identifier (primary key) |
| promo_name | TEXT | Human-readable name (e.g., `Summer Sale`, `Black Friday`) |
| promo_type | TEXT | Type of promotion: `percentage_off` |
| discount_pct | DECIMAL | Discount percentage (0.10 - 0.25) |
| start_date | DATE | Promotion start date |
| end_date | DATE | Promotion end date |
| target_segment | TEXT | Who is eligible: `all`, `new_users` |

#### `experiments` -- 2 rows
One row per A/B test definition.

| Column | Type | Description |
|--------|------|-------------|
| experiment_id | INTEGER | Unique experiment identifier (primary key) |
| experiment_name | TEXT | Machine-readable name |
| hypothesis | TEXT | Testable hypothesis statement |
| primary_metric | TEXT | What the experiment measures |
| guardrail_metrics | TEXT | Comma-separated guardrail metrics |
| start_date | DATE | Experiment start date |
| end_date | DATE | Experiment end date |
| status | TEXT | Experiment status (`completed`) |

---

### Fact / Transactional Tables

#### `events` -- ~6.5 million rows
One row per behavioral event. This is the largest table.

| Column | Type | Description |
|--------|------|-------------|
| event_id | INTEGER | Unique event identifier (primary key) |
| user_id | INTEGER | References `users.user_id` |
| session_id | TEXT | Session grouping key (format: `s_{user_id}_{counter}`) |
| event_timestamp | TIMESTAMP | When the event occurred |
| event_date | DATE | Date of the event (for easy grouping) |
| event_type | TEXT | Type of event (see list below) |
| device | TEXT | Device used: `web`, `ios`, `android` |
| product_id | INTEGER | References `products.product_id` (NULL for non-product events) |
| page_url | TEXT | Page URL (for `page_view` events) |
| search_query | TEXT | Search query text (for `search` events) |
| app_version | TEXT | App version string (NULL for web events) |

**Event types:** `page_view`, `search`, `product_view`, `add_to_cart`, `remove_from_cart`, `checkout_started`, `payment_attempted`, `purchase_complete`, `save_for_later`, `app_open` (mobile only), `signup`, `login`

#### `sessions` -- ~1.4 million rows
One row per user session. Derived from events with a 30-minute inactivity gap defining session boundaries.

| Column | Type | Description |
|--------|------|-------------|
| session_id | TEXT | Unique session identifier (primary key), matches `events.session_id` |
| user_id | INTEGER | References `users.user_id` |
| session_start | TIMESTAMP | Timestamp of first event in session |
| session_end | TIMESTAMP | Timestamp of last event in session |
| session_date | DATE | Date of the session |
| device | TEXT | Device used: `web`, `ios`, `android` |
| landing_page | TEXT | First page URL in the session |
| page_views | INTEGER | Count of `page_view` events in session |
| events_count | INTEGER | Total events in session |
| had_purchase | BOOLEAN | Whether the session included a `purchase_complete` event |

#### `orders` -- ~50K rows
One row per order, derived from `purchase_complete` events.

| Column | Type | Description |
|--------|------|-------------|
| order_id | INTEGER | Unique order identifier (primary key) |
| user_id | INTEGER | References `users.user_id` |
| order_timestamp | TIMESTAMP | When the order was placed |
| order_date | DATE | Date of order |
| subtotal | DECIMAL | Sum of line items before discount |
| discount_amount | DECIMAL | Discount applied |
| shipping_amount | DECIMAL | Shipping charge ($5.99 for non-Plus, $0 for Plus members) |
| total_amount | DECIMAL | Final amount charged |
| status | TEXT | `completed`, `cancelled`, or `returned` |
| promo_id | INTEGER | References `promotions.promo_id` (NULL if no promo applied) |
| is_plus_member_order | BOOLEAN | Whether the buyer was a Plus member at time of order |
| device | TEXT | Device used to place order |
| session_id | TEXT | Session in which order was placed |

#### `order_items` -- ~120K rows
One row per line item within an order.

| Column | Type | Description |
|--------|------|-------------|
| order_item_id | INTEGER | Unique line item identifier (primary key) |
| order_id | INTEGER | References `orders.order_id` |
| product_id | INTEGER | References `products.product_id` |
| quantity | INTEGER | Quantity purchased (1-3) |
| unit_price | DECIMAL | Price at time of purchase (may differ from `products.price` during promos) |
| discount_amount | DECIMAL | Line-level discount |
| line_total | DECIMAL | `quantity * unit_price - discount_amount` |

#### `memberships` -- ~12K rows
One row per membership state change. Tracks the lifecycle of NovaMart Plus memberships.

| Column | Type | Description |
|--------|------|-------------|
| membership_id | INTEGER | Unique row identifier (primary key) |
| user_id | INTEGER | References `users.user_id` |
| plan_type | TEXT | `plus_trial`, `plus_monthly`, `plus_annual` |
| started_at | TIMESTAMP | When this membership state began |
| ended_at | TIMESTAMP | When this state ended (NULL = currently active) |
| status | TEXT | `active`, `cancelled`, `expired`, `converted` |
| cancel_reason | TEXT | Reason for cancellation: `price`, `not_using`, `competitor`, `other` (NULL if not cancelled) |
| is_current | BOOLEAN | Whether this is the user's current membership row |

#### `support_tickets` -- ~25K rows
One row per customer support ticket.

| Column | Type | Description |
|--------|------|-------------|
| ticket_id | INTEGER | Unique ticket identifier (primary key) |
| user_id | INTEGER | References `users.user_id` |
| created_at | TIMESTAMP | Ticket creation time |
| created_date | DATE | Ticket creation date |
| category | TEXT | `payment_issue`, `delivery_issue`, `product_quality`, `account_issue`, `membership_issue`, `other` |
| severity | TEXT | `low`, `medium`, `high`, `critical` |
| status | TEXT | `open`, `resolved`, `closed` |
| resolved_at | TIMESTAMP | Resolution time (NULL if still open) |
| device | TEXT | Device where issue occurred |
| app_version | TEXT | App version for mobile tickets |
| order_id | INTEGER | References `orders.order_id` (for order-related tickets, NULL otherwise) |

#### `nps_responses` -- ~8K rows
One row per Net Promoter Score survey response.

| Column | Type | Description |
|--------|------|-------------|
| response_id | INTEGER | Unique response identifier (primary key) |
| user_id | INTEGER | References `users.user_id` |
| response_date | DATE | Date the survey was completed |
| score | INTEGER | NPS score (0-10). 0-6 = Detractor, 7-8 = Passive, 9-10 = Promoter |
| user_segment | TEXT | `free` or `plus` (denormalized from membership status) |
| device | TEXT | Device used to respond: `web`, `ios`, `android` |
| comment | TEXT | Open-ended feedback (NULL for ~70% of responses) |

#### `experiment_assignments` -- ~20K rows
One row per user-experiment assignment for A/B tests.

| Column | Type | Description |
|--------|------|-------------|
| assignment_id | INTEGER | Unique assignment identifier (primary key) |
| experiment_id | INTEGER | References `experiments.experiment_id` |
| user_id | INTEGER | References `users.user_id` |
| variant | TEXT | `control` or `treatment` |
| assigned_date | DATE | Date the user was assigned to the experiment |
| first_exposure_date | DATE | Date the user first saw the variant (NULL if never exposed) |

---

### Helper Table

#### `calendar` -- 366 rows (2024 is a leap year)
One row per date in 2024. Useful for filling gaps in time series and joining on date attributes.

| Column | Type | Description |
|--------|------|-------------|
| date | DATE | Calendar date (primary key) |
| day_of_week | TEXT | `Monday` through `Sunday` |
| is_weekend | BOOLEAN | True for Saturday and Sunday |
| month | INTEGER | 1-12 |
| quarter | INTEGER | 1-4 |
| is_holiday | BOOLEAN | True for major US shopping holidays |
| holiday_name | TEXT | Name of holiday (NULL for non-holidays) |

---

## Entity Relationship Summary

The diagram below shows how tables connect. All relationships use the column name shown.

```
users
 |
 |-- user_id --> events
 |-- user_id --> sessions
 |-- user_id --> orders
 |-- user_id --> memberships
 |-- user_id --> support_tickets
 |-- user_id --> nps_responses
 |-- user_id --> experiment_assignments

orders
 |-- order_id --> order_items
 |-- order_id --> support_tickets.order_id (nullable, ~60% of tickets)
 |-- promo_id --> promotions.promo_id (nullable)

events
 |-- session_id --> sessions.session_id
 |-- product_id --> products.product_id (nullable, product-related events only)

orders
 |-- session_id --> sessions.session_id

experiment_assignments
 |-- experiment_id --> experiments.experiment_id

calendar
 |-- date --> can be joined to any date column (event_date, order_date, etc.)
```

**Key joins you will use often:**

| To answer... | Join... |
|-------------|---------|
| User behavior + demographics | `events` JOIN `users` ON `user_id` |
| What was purchased | `orders` JOIN `order_items` ON `order_id` JOIN `products` ON `product_id` |
| Session-level funnels | `events` filtered by `session_id`, or use the `sessions` table directly |
| Membership status at time of event | `memberships` JOIN on `user_id` WHERE event timestamp between `started_at` and `ended_at` |
| Support tickets for a specific order | `support_tickets` JOIN `orders` ON `order_id` |
| NPS by user attributes | `nps_responses` JOIN `users` ON `user_id` |
| Experiment outcomes | `experiment_assignments` JOIN `orders` or `events` ON `user_id` |
| Fill date gaps in time series | `calendar` LEFT JOIN your aggregated data ON `date` |

---

## Quick-Start Queries

These queries work in DuckDB (via the `novamart_practice.duckdb` file) or against the CSV files loaded into any SQL engine. They will help you confirm the data is loaded and get oriented.

### 1. Row counts for every table

```sql
SELECT 'users' AS table_name, COUNT(*) AS row_count FROM users
UNION ALL SELECT 'products', COUNT(*) FROM products
UNION ALL SELECT 'promotions', COUNT(*) FROM promotions
UNION ALL SELECT 'experiments', COUNT(*) FROM experiments
UNION ALL SELECT 'events', COUNT(*) FROM events
UNION ALL SELECT 'sessions', COUNT(*) FROM sessions
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'order_items', COUNT(*) FROM order_items
UNION ALL SELECT 'memberships', COUNT(*) FROM memberships
UNION ALL SELECT 'support_tickets', COUNT(*) FROM support_tickets
UNION ALL SELECT 'nps_responses', COUNT(*) FROM nps_responses
UNION ALL SELECT 'experiment_assignments', COUNT(*) FROM experiment_assignments
UNION ALL SELECT 'calendar', COUNT(*) FROM calendar;
```

### 2. Users by acquisition channel

```sql
SELECT acquisition_channel,
       COUNT(*) AS users,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM users
GROUP BY 1
ORDER BY 2 DESC;
```

### 3. Monthly revenue trend

```sql
SELECT DATE_TRUNC('month', order_date) AS month,
       COUNT(*) AS orders,
       COUNT(DISTINCT user_id) AS buyers,
       ROUND(SUM(total_amount), 2) AS revenue,
       ROUND(AVG(total_amount), 2) AS avg_order_value
FROM orders
WHERE status = 'completed'
GROUP BY 1
ORDER BY 1;
```

### 4. Checkout funnel conversion by device

```sql
SELECT device,
       COUNT(CASE WHEN event_type = 'product_view' THEN 1 END) AS product_views,
       COUNT(CASE WHEN event_type = 'add_to_cart' THEN 1 END) AS add_to_cart,
       COUNT(CASE WHEN event_type = 'checkout_started' THEN 1 END) AS checkout_started,
       COUNT(CASE WHEN event_type = 'payment_attempted' THEN 1 END) AS payment_attempted,
       COUNT(CASE WHEN event_type = 'purchase_complete' THEN 1 END) AS purchase_complete
FROM events
WHERE event_type IN ('product_view', 'add_to_cart', 'checkout_started',
                      'payment_attempted', 'purchase_complete')
GROUP BY 1
ORDER BY 1;
```

### 5. NPS score distribution by segment

```sql
SELECT user_segment,
       COUNT(*) AS responses,
       ROUND(AVG(score), 1) AS avg_score,
       ROUND(100.0 * SUM(CASE WHEN score >= 9 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_promoter,
       ROUND(100.0 * SUM(CASE WHEN score <= 6 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_detractor,
       ROUND(100.0 * (
           SUM(CASE WHEN score >= 9 THEN 1 ELSE 0 END) -
           SUM(CASE WHEN score <= 6 THEN 1 ELSE 0 END)
       ) / COUNT(*), 1) AS nps
FROM nps_responses
GROUP BY 1
ORDER BY 1;
```

### 6. Support tickets by category and severity

```sql
SELECT category,
       COUNT(*) AS total_tickets,
       ROUND(100.0 * SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_critical,
       ROUND(100.0 * SUM(CASE WHEN severity = 'high' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_high,
       ROUND(100.0 * SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_resolved
FROM support_tickets
GROUP BY 1
ORDER BY 2 DESC;
```

---

## Data Freshness and Scale

| Attribute | Value |
|-----------|-------|
| Time range | January 1 - December 31, 2024 |
| Users | ~50,000 |
| Behavioral events | ~6.5 million |
| Sessions | ~1.4 million |
| Orders | ~50K |
| Countries | 6 (US, UK, CA, DE, AU, other) |
| Product catalog | 500 SKUs across 6 categories |
| Platforms | Web, iOS, Android |
| Acquisition channels | 6 (organic, paid_search, social, referral, email, tiktok_ads) |
| Promotions | 5 (including seasonal sales and a year-round welcome offer) |
| A/B tests | 2 completed experiments |

---

## Data Tiers

The dataset is split into two tiers to keep the repo small while providing full data when needed.

### Tier 1: Shipped with the repo (~4MB)

These 8 small reference/dimension tables are included in git:

| File | Rows | Size | Description |
|------|------|------|-------------|
| `calendar.csv` | 366 | 13K | 2024 calendar with holidays |
| `experiments.csv` | 2 | <1K | A/B test definitions |
| `promotions.csv` | 5 | <1K | Promotion definitions |
| `products.csv` | 500 | 29K | Product catalog |
| `nps_responses.csv` | ~8K | 335K | NPS survey responses |
| `memberships.csv` | ~12K | 392K | Plus membership state changes |
| `experiment_assignments.csv` | ~20K | 861K | A/B test assignments |
| `order_items.csv` | ~120K | 2.4M | Order line items |

### Tier 2: Downloaded separately (~690MB)

These 5 large tables must be downloaded after cloning:

| File | Rows | Size | Description |
|------|------|------|-------------|
| `users.csv` | ~50K | 3M | User dimension table |
| `orders.csv` | ~50K | 4.6M | Order records |
| `support_tickets.csv` | ~25K | 2.2M | Customer support tickets |
| `sessions.csv` | ~1.4M | 130M | Session summaries |
| `events.csv` | ~6.5M | 551M | Behavioral events (largest) |

**Download Tier 2 data:**

```bash
# Sample data (10K-row subsets, ~15MB) — good for learning
bash scripts/download-data.sh

# Full dataset (~200MB compressed, ~690MB uncompressed)
bash scripts/download-data.sh --full
```

### Tier 3: Generated locally

| File | Description |
|------|-------------|
| `novamart.duckdb` | Pre-built DuckDB database (generated by `scripts/build-duckdb.sh`) |

```bash
# Build after downloading CSVs
bash scripts/build-duckdb.sh
```

---

## File Inventory

The complete dataset contains 13 CSV files:

| File | Description |
|------|-------------|
| `users.csv` | User dimension table |
| `products.csv` | Product catalog |
| `promotions.csv` | Promotion definitions |
| `experiments.csv` | Experiment definitions |
| `events.csv` | Behavioral events (largest file, ~550 MB) |
| `sessions.csv` | Session summaries (~130 MB) |
| `orders.csv` | Order records |
| `order_items.csv` | Order line items |
| `memberships.csv` | Plus membership state changes |
| `support_tickets.csv` | Customer support tickets |
| `nps_responses.csv` | NPS survey responses |
| `experiment_assignments.csv` | A/B test user assignments |
| `calendar.csv` | 2024 calendar with holidays and day-of-week attributes |

To query a DuckDB database (after building it):
```python
import duckdb
con = duckdb.connect('data/novamart/novamart.duckdb', read_only=True)
con.sql("SELECT COUNT(*) FROM users").show()
```
