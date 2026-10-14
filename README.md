# Grounds for Concern
### Ridgeline Coffee Sizing Impact Report

**Units up 13%, revenue flat, gross margin down 46%.** An EDA of how underpriced bulk bags, stacked discounts and a thinning shelf trained customers to trade down, and what it would take to win the margin back.

📄 **[Read the full report (Google Doc)](https://docs.google.com/document/d/1lU5B2a1CKG4U8uVeBsMaXXyvfq0pTHoA6peX7-m9_Yk/edit?usp=sharing)**: all nine charts, store-level SKU snapshots and the full reasoning.

> **Synthetic data.** Ridgeline Roasters is a fictional 6-store specialty coffee retailer. The data is generated in this repo and modeled on a real sizing and pricing analysis I led in a regulated retail category. A **unit** is one bag sold, of any size: Small (12 oz), Medium (2 lb) or Bulk (5 lb).

![Net sales by size](charts/01_net_sales_by_size.png)

## The question

Has the bag-size assortment changed, and if so, what has it done to business performance?

## What I found (Jan to Dec 2025)

| Signal | Change |
|---|---|
| Net sales | flat: $387K → $388K a month |
| Units sold | **+13%** (11.3K → 12.8K) |
| Average transaction value | **−37%** ($60 → $38) |
| Gross margin dollars | **−46%** ($232K → $125K a month) |
| Bulk gross margin % | **58% → 23%** |
| Bulk net sales per ounce | **−46%** ($1.00 → $0.54) |
| Bulk discount rate | 1% → **29%** |
| In-stock SKUs (store snapshot) | **−51%** (213 → 104) |
| Big baskets (36 oz+) with a Bulk bag | 48% → **89%** |

**Bottom line:** customers weren't buying more coffee. They were trading down into a discounted Bulk bag because smaller sizes went out of stock, which cannibalized higher-margin Small and Medium sales.

## Recommendations

| Goal | Action | Estimated impact |
|---|---|---|
| Bulk back to **$0.90–$1.00 net per oz** (from $0.54) | **Pricing overhaul:** reverse the 25% list cut, set a **$0.90/oz net floor** | Up to **$168K/month** at Dec volumes (upper bound). Reset lifted Bulk margin 23% → **57%** |
| Bulk & Medium discounts **≤ 10%** (from 29% / 28%) | **Discount cap** by size tier, no promo stacking | **~$334K** recovered, **7.6% of 2025 net sales** |
| **≥ 10 of 12 SKUs** per size in stock per store (from 4–7) | **Inventory floor** by size; protect high-margin demand first | ATV **$38 → $60**, gross margin **$125K → $222K/month** (+77%) after the reset |

<table>
<tr>
<td><img src="charts/05_gross_margin_pct_by_size.png" alt="Gross margin % by size"></td>
<td><img src="charts/09_big_basket_mix.png" alt="Big-basket composition"></td>
</tr>
</table>

## How it's built

```
grounds-for-concern/
├── src/generate_data.py   # seeded synthetic data: stores, SKUs, ~165k order lines, weekly inventory
├── src/load_db.py         # loads CSVs into SQLite and builds the views
├── sql/eda_queries.sql    # every report metric as a view (ports to Snowflake/Postgres)
├── src/eda.py             # renders the nine report charts from those views
└── charts/                # chart PNGs used here and in the full report
```

```bash
pip install -r requirements.txt
python src/generate_data.py   # ~2 min, seeded so results reproduce
python src/eda.py             # builds the DB, renders charts, prints headline numbers
```

**Tools:** SQL · Python (pandas, NumPy, matplotlib) · **Metrics:** net sales per unit and per ounce, gross margin by size, discount rate, SKU availability, ATV, basket composition
