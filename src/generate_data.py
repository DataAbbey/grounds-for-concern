"""
Generate a synthetic retail dataset for the Grounds for Concern EDA.

Business: "Ridgeline Roasters", a fictional 6-store specialty coffee retailer.
Category under review: whole-bean coffee, sold in three bag sizes:
    12 oz  (Small)   |   2 lb / 32 oz  (Medium)   |   5 lb / 80 oz  (Bulk)

The data is fake but built to reproduce a real-world pattern:
  * Jan-Jun 2025: healthy price ladder, broad assortment.
  * Jul-Dec 2025: inventory buys tilt toward Bulk bags, Small/Medium SKUs go
    out of stock, Bulk gets list-price cuts plus stacked promos. Volume climbs,
    revenue stalls, per-oz revenue and Bulk margin collapse.
  * Jan-Mar 2026: pricing reset (per-oz ladder restored, Bulk promos capped,
    assortment rebalanced). Per-oz revenue recovers.

Outputs (CSV, in ../data):
    stores.csv, products.csv, transactions.csv, inventory_snapshots.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)
OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)

START, END = "2025-01-01", "2026-03-31"
FIX_DATE = pd.Timestamp("2026-01-01")

# ---------------------------------------------------------------- dimensions
stores = pd.DataFrame({
    "store_id": [f"S{i:02d}" for i in range(1, 7)],
    "store_name": ["Harbor St", "Elm Square", "North Mill", "Westgate",
                   "Union Yard", "Lakeside"],
    "region": ["East", "East", "East", "West", "West", "West"],
    "traffic_index": [1.25, 1.10, 0.85, 1.00, 0.95, 0.85],
})

ORIGINS = ["Colombia Huila", "Ethiopia Yirgacheffe", "Guatemala Antigua",
           "Kenya Nyeri", "Brazil Cerrado", "Sumatra Mandheling",
           "Costa Rica Tarrazu", "Peru Cajamarca", "Honduras Marcala",
           "Rwanda Huye", "House Espresso", "Morning Blend"]
SIZES = {  # size_oz: (tier, base list $/oz, unit cost $/oz)
    12: ("Small", 1.60, 0.55),
    32: ("Medium", 1.15, 0.47),
    80: ("Bulk", 0.95, 0.39),
}

rows = []
for i, origin in enumerate(ORIGINS):
    for size_oz, (tier, per_oz, cost_oz) in SIZES.items():
        premium = 1 + 0.04 * (i % 4)          # a little price spread by origin
        rows.append({
            "sku_id": f"RR-{i+1:02d}-{size_oz:02d}",
            "origin": origin,
            "size_oz": size_oz,
            "size_tier": tier,
            "base_list_price": round(per_oz * premium * size_oz, 2),
            "unit_cost": round(cost_oz * premium * size_oz, 2),
        })
products = pd.DataFrame(rows)

# ------------------------------------------------- monthly business levers
months = pd.period_range(START, END, freq="M")
# 0 = healthy, 1 = full drift (Dec 2025), then reset in 2026
drift = {}
for m in months:
    if m < pd.Period("2025-07"):
        drift[m] = 0.0
    elif m <= pd.Period("2025-12"):
        drift[m] = (m.month - 6) / 6           # Jul .17 ... Dec 1.0
    else:
        drift[m] = {1: 0.55, 2: 0.25, 3: 0.10}[m.month]  # recovery glide


def levers(m):
    d = drift[m]
    fixed = m >= pd.Period("2026-01")
    return {
        # Bulk list price multiplier (1.0 -> 0.84 at full drift)
        "bulk_list_mult": 1 - 0.16 * d,
        # average promo depth by tier
        "promo": {"Small": 0.04, "Medium": 0.06 + 0.06 * d,
                  "Bulk": 0.05 + (0.08 if fixed else 0.33) * d},
        # share of Small/Medium SKUs in stock (1.0 -> ~0.40)
        "sm_instock": 1 - 0.60 * d,
        "bulk_instock": 1.0,
        # customer tier preference shifts toward Bulk as ladder & stock tilt
        "tier_weights": {"Small": 0.52 - 0.30 * d,
                         "Medium": 0.33 - 0.08 * d,
                         "Bulk": 0.15 + 0.38 * d},
        "traffic_mult": 1 + 0.10 * d,   # deals pull a bit more traffic
    }


# ------------------------------------------------------------ inventory
weeks = pd.date_range(START, END, freq="W-MON")
inv_rows = []
instock_lookup = {}  # (store, week_start) -> set(sku)
for s in stores.store_id:
    for w in weeks:
        lv = levers(w.to_period("M"))
        live = set()
        for _, p in products.iterrows():
            p_in = lv["bulk_instock"] if p.size_tier == "Bulk" else lv["sm_instock"]
            in_stock = rng.random() < max(0.05, min(1.0, p_in + rng.normal(0, 0.05)))
            if p.size_tier == "Bulk":
                on_hand = int(rng.integers(8, 20) * (1 + drift[w.to_period('M')]))
            else:
                on_hand = int(rng.integers(6, 30)) if in_stock else 0
            if on_hand > 0:
                live.add(p.sku_id)
            inv_rows.append({"week_start": w.date(), "store_id": s,
                             "sku_id": p.sku_id, "on_hand_units": on_hand})
        instock_lookup[(s, w)] = live
inventory = pd.DataFrame(inv_rows)

# --------------------------------------------------------- transactions
prod_by_tier = {t: products[products.size_tier == t] for t in ["Small", "Medium", "Bulk"]}
days = pd.date_range(START, END, freq="D")
tx = []
order_seq = 0
for day in days:
    m = day.to_period("M")
    lv = levers(m)
    wk = day - pd.Timedelta(days=day.weekday())
    weekend = 1.25 if day.weekday() >= 5 else 1.0
    season = 1 + 0.12 * np.cos((day.dayofyear - 340) / 365 * 2 * np.pi)  # holiday bump
    for _, st in stores.iterrows():
        n_orders = rng.poisson(38 * st.traffic_index * weekend * season * lv["traffic_mult"])
        live = instock_lookup.get((st.store_id, wk), set(products.sku_id))
        tw = lv["tier_weights"]
        tiers = list(tw)
        probs = np.array([tw[t] for t in tiers]); probs /= probs.sum()
        for _ in range(n_orders):
            order_seq += 1
            tier = rng.choice(tiers, p=probs)
            cand = prod_by_tier[tier]
            cand = cand[cand.sku_id.isin(live)]
            if cand.empty:  # wanted size is out -> trade to Bulk (cannibalization)
                tier = "Bulk"
                cand = prod_by_tier["Bulk"]
            p = cand.iloc[rng.integers(len(cand))]
            qty = 1 if tier != "Small" else int(rng.choice([1, 1, 1, 2]))
            list_price = p.base_list_price * (lv["bulk_list_mult"] if tier == "Bulk" else 1.0)
            promo = max(0.0, rng.normal(lv["promo"][tier], 0.04))
            gross = round(list_price * qty, 2)
            disc = round(gross * promo, 2)
            tx.append((f"O{order_seq:07d}", day.date(), st.store_id, p.sku_id, qty,
                       round(list_price, 2), gross, disc, round(gross - disc, 2),
                       round(p.unit_cost * qty, 2)))

transactions = pd.DataFrame(tx, columns=[
    "order_id", "order_date", "store_id", "sku_id", "qty", "unit_list_price",
    "gross_sales", "discount_amt", "net_sales", "cogs"])

stores.to_csv(OUT / "stores.csv", index=False)
products.to_csv(OUT / "products.csv", index=False)
transactions.to_csv(OUT / "transactions.csv", index=False)
inventory.to_csv(OUT / "inventory_snapshots.csv", index=False)
print(f"stores {len(stores)} | products {len(products)} | "
      f"transactions {len(transactions):,} | inventory rows {len(inventory):,}")
