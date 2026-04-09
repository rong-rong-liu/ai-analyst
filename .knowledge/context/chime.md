# Chime — Company Context

Chime is a financial technology company offering fee-free banking services. Core business model is interchange revenue from member card transactions. Primary databases: ANALYTICS_DB (dbt models) and EDW_DB (DTS pipelines), both in Snowflake.

---

## Products

| Product | Description | Key Metrics |
|---------|-------------|-------------|
| **Checking Account** | Fee-free checking + debit card. Core product, all members have one. Primary revenue via debit interchange. | transaction_actives, deposit_volume, purchase_volume, flowthrough_rate |
| **Direct Deposit** | Payroll/govt DD to Chime. $200+ qualifying DD = "Current DDer" (core engagement metric). | current_dders, d30_dd_conversion_rate, dd_retention_rate |
| **SpotMe** | Fee-free overdraft protection for eligible DDers. Revenue from optional tips. | spotme_revenue, projected_spotme_loss |
| **Credit Builder** | Secured credit card for building credit. No fee/interest. "Single Balance" variant merges credit + spending. | credit_mix, credit_builder_usage, credit_interchange_revenue |
| **Savings** | High-yield savings with auto-save features (round-ups, Save When I Get Paid). | savings_revenue, savings_balance |
| **Pay Friends (P2P)** | Free instant transfers between Chime members. | pay_friends_transaction_count |
| **Pay Anyone** | Send money to non-Chime users. Also an acquisition channel (recipients may enroll). | pay_anyone_enrollments, pay_anyone_guest_account_dv |
| **MyPay (Earned Wage Access)** | Early paycheck access. Advance types: DDER, Non-DDER, DTE. | mypay_advances, projected_mypay_loss |
| **Instant Loans** | Short-term lending with underwriting and servicing. | loan_origination_volume, loan_charge_off_rate |

---

## Teams

| Team | Owns | Key Metrics |
|------|------|-------------|
| **Growth** | Acquisition, conversion, retention, pacing | enrollments, d30_dd_conversion_rate, current_dders, dd_retention_rate |
| **Finance** | Unit economics (MUE), revenue, cost modeling, forecasting | contribution_margin, deposit_volume, purchase_volume |
| **Research & Strategy Analytics** | Central analytics, cross-functional | all |
| **Product** | Product features (SpotMe, Credit Builder, P2P, MyPay) | product_attach, credit_mix, spotme_revenue |
| **Marketing** | Paid/organic spend, attribution, campaigns | d30_dd_cac, cost_per_enrollment, dr_spend |
| **Data Engineering (DTS)** | Data pipelines (data-transformation repo), ETL, data quality | — |

---

## Key Metrics

### Growth (Stock — use M3 value for quarterly)
- **Transaction Actives (TAs)** — Members with 1+ qualifying transaction in the month. Guardrail: ta_retention_rate.
- **Current DDers** — Members with $200+ qualifying DD in the month. Core engagement metric. Guardrails: dd_retention_rate, d30_dd_conversion_rate.
- **Active DDers** — Current DDers AND Transaction Active.
- **Primary Accounts** — Members using Chime as primary bank (DV threshold over L30).

### Acquisition (Flow — sum for quarterly)
- **Enrollments** — New sign-ups. By channel: Paid, Organic, Referral, Pay Anyone, PLM.
- **New DDers** — First-time DDer conversions in the month.
- **D30 DD Conversion Rate** — Pct of enrollment cohort converting to DDer within 30 days. ~30 day lag. Guardrail: d30_dd_cac.
- **D30 DD CAC** — Marketing spend / D30 conversions. ~30 day lag. By channel.
- **Cost Per Enrollment (CPE)** — Marketing spend / enrollments.

### Retention
- **DD Retention Rate** — Pct of prior month DDers still DDers this month. Segmented by tenure: M1, M2, M2+, M2-M6, M7-M12, M13-M24, M25-M36, M37+.
- **Net Retention** — (Retained + Resurrected) / Prior month DDers. Can exceed 100%.

### Volume (Flow)
- **Deposit Volume (DV)** — Total deposits. Includes DD and non-DD (VMT, ACH, IIT, cash, MCD, IP2P).
- **Purchase Volume (PV)** — Total debit + credit card spend. Key revenue driver (interchange).
- **Flowthrough Rate** — PV / DV. Measures spend engagement.
- **DV 35d Per DDer** — Avg deposit volume per new DDer in first 35 days post-conversion.

### Unit Economics
- **Contribution Margin** — Total revenue - (txn costs + event variable costs + projected losses). Per-member profitability.
- **Transaction Margin** — Contribution margin + event variable costs. Transaction-only profitability.

### Product
- **Credit Mix** — Credit card spend / total PV.
- **Product Attach** — Number of Chime products per member (debit, credit, P2P, savings, SpotMe).

### Pacing
- **EOM Projection** — End-of-month forecast from pacing models. Methods: day-of-week ratios and ML.
- **Stock vs Flow** — Stock (TAs, DDers, PAs) use M3 for quarterly. Flow (enrollments, new DDers) sum M1+M2+M3.

---

## Business Glossary

### Member Lifecycle
- **Enrollment** — Completing sign-up. Date from member_details.enrollment_date. Exclude user_status in ('failed_id', 'needs_enrollment').
- **Transaction Active (TA)** — is_active = 1 on base__user_day/month.
- **Current DDer** — is_current_dd = 1. $200+ qualifying DD in the month.
- **Active DDer** — is_active_dd = 1. Both Current DDer AND Transaction Active.
- **Proforma** — Updated DD qualification logic applied retroactively. Use `_proforma` columns for trend analysis. Non-proforma for legacy report matching.
- **Primary Account** — is_primary_l30 = 1. Deposit volume threshold over L30 window.
- **Lifecycle Type** — Monthly status: New, Retained, Churned, Winback. Columns: active_type, current_dd_type, primary_type on base__user_month.
- **Enrollment Channel** — Paid, Organic, Referral, Pay Anyone, PLM. Case-sensitive in Snowflake.
- **Synth/Fraud** — synth_or_fraud flag. Always exclude from analysis.
- **Program Bank** — Bancorp or Stride. On base__user_month.

### Direct Deposit Types & Conversion
- **DD Conversion** — First qualifying DD. conversion_date on base__user_dates.
- **D30 DD Conversion Rate** — Pct converting within 30 days of enrollment. ~30 day lag.
- **Conversion Cohort Timing** — M0 (same month as enrollment), M1 (next month), M2+ (2+ months later).
- **DD Conversion Type** — payroll, government_benefit, gig_instant_payout, social_security, child_support, unknown, other_unknown.
- **Qualified DD** — $200+ deposit. Broken by type: qualified_payroll_dd, qualified_government_benefit_dd, etc.
- **DD Hierarchical Type** — Priority: payroll > govt_benefit > unknown > other_unknown. On base__user_month.

### Retention & Churn
- **DD Retention Rate** — Retained / (Retained + Churned). By tenure bucket.
- **Net Retention** — (Retained + Resurrected) / Prior total. Can exceed 100%.
- **Churned DDer** — current_dd_type = 'Churned'. Tracked by churn frequency (1st/2nd/3rd+).
- **Resurrected DDer (Winback)** — Returned after 1+ month gap. Tracked by dormancy duration.

### Volumes
- **Deposit Volume (DV)** — SUM(deposits) on base tables. total_dv_amt on mr__summary_v2.
- **Purchase Volume (PV)** — SUM(spend). Can be negative (refunds). purchase_volume on mr__summary_v2.
- **Flowthrough Rate** — PV / DV.
- **DV 35d Per DDer** — First 35 days post-conversion (not post-enrollment). Check is_35_day_mature flag.
- **OIT Volume** — Outbound instant transfers. Generates fee revenue. pv_plus_oit = PV + net OIT.
- **Non-DD Deposit Types** — VMT, ACH Push/Pull, IIT, Cash, MCD, IP2P, Pay Anyone guest.

### Acquisition & Cost
- **D30 DD CAC** — spend / (enrollments * d30_conversion_rt). ~30 day lag.
- **CPE** — spend / enrollments.
- **DR Spend** — Direct response marketing spend.
- **Intro Offer** — Promotional creatives (LIKE '%offer%' OR '%350%'). Tracked separately.
- **Core vs Expansion Segment** — expansion_segment from member_details. Defaults to 'Core' if null.

### Unit Economics (MUE)
- **MUE** — Daily user-level P&L. Grain: user_id x calendar_date.
- **Transaction Revenue** — Debit/credit interchange + ATM + cash deposit partner + SpotMe tips + EPA + instant loan + instant transfer fees.
- **Total Revenue** — txn_revenue + savings_revenue.
- **Transaction Costs** — ATM (in/out network), purchase processing (debit/credit), DD, cash/check deposit, instant transfer.
- **Event Variable Costs** — Phone/chat/email contact costs, fraud processing, card reissue.
- **Projected Losses** — SpotMe + MyPay + disputes + non-SpotMe losses. 365-day write-off schedule.
- **Contribution Margin** — total_revenue - total_projected_costs.
- **Transaction Margin** — contribution_margin + event_variable_costs (Finance cut).
- **Interchange Rate (bps)** — (payments_revenue / PV) * 10000.

### Pacing & Forecasting
- **Pacing** — In-month EOM projections. 17 metrics, methods: ratios + ML. Only retains current + prior month.
- **Goals** — Annual targets from Pigment. metric_type = 'Goals' on mr__summary_v2.
- **RDF Lag** — Transaction data lags ~3-4 days. base__last_rdf_day = today - 4.
- **D30 Lag** — D30 metrics available ~2nd of M+2. Uses coalesce(actuals, pacing, mgmt_plan).
- **D30-to-M2 Multiplier** — 1.21x for conversions, 1.1x for activations. Forecasting only.
- **MUE Month Length** — Standardized 30 days for normalizing monthly metrics.

---

## Data Lineage

### Where to look across repos

| Need | Location | Repo |
|------|----------|------|
| How an ANALYTICS_DB model is built | `models/{domain}/{model}.sql` | dbt (mumbai) |
| Schema/column docs for dbt model | `models/{domain}/{model}.yml` | dbt (mumbai) |
| How an EDW_DB table is populated | `transformation/self_serving_etl/{domain}/` | data-transformation (dublin) |
| DQC rules for EDW_DB table | Same YAML, `dqc:` section | data-transformation (dublin) |
| Source system definitions | `models/sources/*.yml` | dbt (mumbai) |

### Data flow

```
Source Systems (MySQL, Postgres, Segment, Fivetran)
  --> EDW_DB (DTS pipelines, data-transformation repo)
      --> EDW_DB.CORE: dim_member, ftr_transaction, member_details
      --> EDW_DB.MEMBER: member_transaction_detail_daily
      --> EDW_DB.FINANCE: ftr_revenue_cost
      --> EDW_DB.MARKETING: fact_marketing_spend
      --> EDW_DB.GROWTH: monthly_active_members
  --> ANALYTICS_DB (dbt models, dbt repo)
      --> base__user_dates, base__user_day, base__user_month (spine)
      --> mue__member_unit_economics (P&L)
      --> mr__summary_v2, mr__summary_tiles (reporting)
      --> pacing__latest_eom_projection (forecasting)
      --> growth_forecast_summary (planning)
```

### dbt directories

| Directory | Models | Purpose |
|-----------|--------|---------|
| `models/base/` | 13 | User spine, daily/monthly metrics |
| `models/mue/` | 16 | Revenue, costs, loss projections |
| `models/metrics_review/` | 33 | Pre-aggregated KPI reporting |
| `models/pacing/` | 17 subdirs | In-month EOM projections |
| `models/finance/` | 30+ | Growth forecasting, board reporting |
| `models/sources/` | 8 YAML | Upstream source definitions |

### EDW_DB schemas (from data-transformation)

| Schema | Tables | Domain |
|--------|--------|--------|
| CORE | 96 | core, finplat, experimentation |
| MEMBER | 66 | member, member_360 |
| FINANCE | 109 | finance, finance_product_pl |
| MARKETING | 89 | marketing, lcm, liveramp |
| GROWTH | 39 | growth |
| FUNDING | 16 | funding |
| FUNNEL | 61 | funnel, visitor_360 |
| SPOTME | 27 | spotme |
| MYPAY | 17 | mypay |
| EPA_MYPAY | 54 | epa_mypay |
| INSTANT_LOANS | 11 | instant_loans |
| EXPERIMENTATION_PLATFORM | 36 | experimentation |
| FEATURE_STORE | 893 | ML features |

### External data sources

Via Fivetran Google Sheets: MUE cost factors, daily brand spend, finance actual spend, growth forecast targets, retention/conversion inputs, spend budgets, business plan data, seasonal adjustments.

Other: Looker PDTs, Zendesk/OMX, Risk scoring, Segment events, ML model inferences.
