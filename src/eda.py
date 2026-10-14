"""
Run the EDA: build the SQLite DB, pull the views, render charts, and print the
headline numbers used in the README.

    python src/generate_data.py   # once (about 2 min)
    python src/eda.py

"Units" = items sold. One bag is one unit, whatever its size.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

from load_db import build

ROOT = Path(__file__).resolve().parent.parent
CHARTS = ROOT / "charts"
CHARTS.mkdir(exist_ok=True)

# Grey first, one accent (blue) on what each chart is about.
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
ACCENT, GREY, GREY_LT = "#2a78d6", "#8c8a84", "#c9c7c0"
TIER_LABEL = {"Small": "Small (12 oz)", "Medium": "Medium (2 lb)", "Bulk": "Bulk (5 lb)"}
ORDER = ["Small", "Medium", "Bulk"]
TIER_COLOR = {"Small": GREY_LT, "Medium": GREY, "Bulk": ACCENT}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10.5, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.8,
    "legend.frameon": False, "lines.linewidth": 2,
})
JAN, DEC, MAR = "2025-01", "2025-12", "2026-03"


def shade(ax, xs):
    """Shade the review year (2025) and mark the pricing reset."""
    lo, hi, reset = xs.index("2025-01"), xs.index("2025-12"), xs.index("2026-01")
    ax.axvspan(lo - 0.5, hi + 0.5, color="#f1ede4", zorder=0, lw=0)
    ax.axvline(reset - 0.5, color=INK2, lw=1, ls=(0, (3, 3)), zorder=1)
    top = ax.get_ylim()[1]
    ax.text(lo - 0.3, top, "Review period (2025)", va="top", fontsize=9, color=INK2)
    ax.text(reset - 0.3, top, "Pricing reset", va="top", fontsize=9, color=INK2)


def fmt_months(ax, xs, offset=0):
    ax.set_xticks([i + offset for i in range(len(xs))])
    ax.set_xticklabels([pd.Period(m).strftime("%b\n%y") if i % 3 == 0 else ""
                        for i, m in enumerate(xs)])


def line(ax, xs, values, color, label, lw=2):
    ax.plot(range(len(xs)), values, color=color, label=label, lw=lw, marker="o", ms=3.5,
            markeredgecolor=SURFACE, markeredgewidth=1)


def callout(ax, xs, mo, v, text, dy=8):
    ax.annotate(text, (xs.index(mo), v), xytext=(0, dy), textcoords="offset points",
                ha="center", fontsize=9, color=INK, fontweight="bold")


def save(fig, name):
    fig.tight_layout()
    fig.savefig(CHARTS / name, dpi=160)
    plt.close(fig)


def main():
    con = build()
    m = pd.read_sql("SELECT * FROM v_monthly ORDER BY month", con)
    mt = pd.read_sql("SELECT * FROM v_monthly_tier ORDER BY month", con)
    inv = pd.read_sql("SELECT * FROM v_instock ORDER BY month", con)
    xs = list(m.month)
    m["gross_profit"] = m.net_sales * m.gross_margin
    mi = m.set_index("month")
    tier = lambda t, col: mt[mt.size_tier == t].set_index("month").reindex(xs)[col]

    for old in CHARTS.glob("*.png"):
        old.unlink()

    # 1. The paradox: units vs revenue vs gross profit, indexed to Jan 2025 = 100
    fig, ax = plt.subplots(figsize=(9, 4.6))
    base = mi.loc[JAN]
    for col, lab, c, lw in [("units_sold", "Units sold", GREY, 2), ("net_sales", "Net sales", GREY_LT, 2),
                            ("gross_profit", "Gross profit", ACCENT, 2.5)]:
        v = m[col] / base[col] * 100
        line(ax, xs, v, c, lab, lw)
        callout(ax, xs, DEC, v.iloc[xs.index(DEC)], f"{v.iloc[xs.index(DEC)]:.0f}")
    ax.axhline(100, color=INK2, lw=0.8)
    ax.set_ylim(40, 140)
    ax.set_title("Units climbed, revenue stayed flat, gross profit fell by almost half")
    ax.set_ylabel("Index (Jan 2025 = 100)")
    fmt_months(ax, xs); shade(ax, xs)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.18), ncol=3)
    save(fig, "01_units_revenue_profit.png")

    # 2. Average transaction value
    fig, ax = plt.subplots(figsize=(9, 4.2))
    line(ax, xs, m.avg_transaction_value, ACCENT, "Average transaction value", 2.5)
    for mo in [JAN, DEC, MAR]:
        callout(ax, xs, mo, mi.loc[mo, "avg_transaction_value"], f"${mi.loc[mo, 'avg_transaction_value']:.0f}")
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:.0f}"))
    ax.set_ylim(0, 75)
    ax.set_title("Average transaction value fell from $60 to $38")
    ax.set_ylabel("Net sales per order")
    fmt_months(ax, xs); shade(ax, xs)
    save(fig, "02_avg_transaction_value.png")

    # 3. SKU availability: in-stock SKUs per store, stacked by size
    stock = inv.pivot(index="month", columns="size_tier", values="avg_instock_skus").reindex(xs)[ORDER]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    bottom = pd.Series(0.0, index=stock.index)
    sku_color = {"Small": GREY_LT, "Medium": GREY, "Bulk": "#5f5d58"}  # all sizes fell: no accent
    for t in ORDER:
        ax.bar(range(len(xs)), stock[t], bottom=bottom, color=sku_color[t], width=0.78,
               label=TIER_LABEL[t], edgecolor=SURFACE, linewidth=2)
        bottom += stock[t]
    for mo in [JAN, DEC, MAR]:
        callout(ax, xs, mo, bottom[mo], f"{bottom[mo]:.0f}", dy=4)
    ax.set_ylim(0, 42)
    ax.set_title("In-stock SKUs per store fell 55% across all sizes")
    ax.set_ylabel("Avg in-stock SKUs per store (of 36)")
    fmt_months(ax, xs)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.18), ncol=3)
    save(fig, "03_sku_availability.png")

    # 4. Cannibalization: share of units sold by size
    share = mt.pivot(index="month", columns="size_tier", values="units_sold").reindex(xs)[ORDER]
    share = share.div(share.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    bottom = pd.Series(0.0, index=share.index)
    for t in ORDER:
        ax.bar(range(len(xs)), share[t], bottom=bottom, color=TIER_COLOR[t], width=0.78,
               label=TIER_LABEL[t], edgecolor=SURFACE, linewidth=2)
        bottom += share[t]
    for mo in [JAN, DEC, MAR]:
        i = xs.index(mo); v = share.loc[mo, "Bulk"]
        ax.text(i, 1 - v / 2, f"{v:.0%}", ha="center", va="center", fontsize=9,
                color="white", fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_ylim(0, 1.0)
    ax.set_title("Customers traded down to the cheapest per-oz size: Bulk's unit share nearly tripled")
    ax.set_ylabel("Share of units sold")
    fmt_months(ax, xs)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.18), ncol=3)
    save(fig, "04_unit_mix_by_size.png")

    # 5. Gross margin by size
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for t in ORDER:
        line(ax, xs, tier(t, "gross_margin"), TIER_COLOR[t], TIER_LABEL[t], 2.5 if t == "Bulk" else 2)
    bm = tier("Bulk", "gross_margin")
    for mo in [JAN, DEC, MAR]:
        callout(ax, xs, mo, bm[mo], f"{bm[mo]:.0%}", dy=-16)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_ylim(0, 0.8)
    ax.set_title(f"Bulk gross margin fell from {bm[JAN]:.0%} to {bm[DEC]:.0%}")
    ax.set_ylabel("Gross margin")
    fmt_months(ax, xs); shade(ax, xs)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.18), ncol=3)
    save(fig, "05_gross_margin_by_size.png")

    # 6. Net sales per unit by size
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for t in ORDER:
        line(ax, xs, tier(t, "net_sales_per_unit"), TIER_COLOR[t], TIER_LABEL[t], 2.5 if t == "Bulk" else 2)
    bu = tier("Bulk", "net_sales_per_unit")
    for mo in [JAN, DEC]:
        callout(ax, xs, mo, bu[mo], f"${bu[mo]:.0f}")
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:.0f}"))
    ax.set_ylim(0, 95)
    ax.set_title(f"Revenue per Bulk bag fell {bu[DEC] / bu[JAN] - 1:.0%} as list cuts and promos stacked")
    ax.set_ylabel("Net sales per unit")
    fmt_months(ax, xs); shade(ax, xs)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.18), ncol=3)
    save(fig, "06_net_sales_per_unit_by_size.png")

    # Headline numbers for the README
    pct = lambda a, b: f"{b / a - 1:+.0%}"
    g = lambda t, mo, col: tier(t, col)[mo]
    tot = stock.sum(axis=1)
    out = {
        "units sold Jan->Dec": pct(mi.loc[JAN, "units_sold"], mi.loc[DEC, "units_sold"]),
        "net sales Jan->Dec": pct(mi.loc[JAN, "net_sales"], mi.loc[DEC, "net_sales"]),
        "gross profit Jan->Dec": pct(mi.loc[JAN, "gross_profit"], mi.loc[DEC, "gross_profit"]),
        "ATV Jan->Dec": f"${mi.loc[JAN, 'avg_transaction_value']:.2f} -> ${mi.loc[DEC, 'avg_transaction_value']:.2f} ({pct(mi.loc[JAN, 'avg_transaction_value'], mi.loc[DEC, 'avg_transaction_value'])})",
        "Bulk margin Jan->Dec->Mar": f"{g('Bulk', JAN, 'gross_margin'):.1%} -> {g('Bulk', DEC, 'gross_margin'):.1%} -> {g('Bulk', MAR, 'gross_margin'):.1%}",
        "Bulk discount Jan->Dec": f"{g('Bulk', JAN, 'discount_rate'):.0%} -> {g('Bulk', DEC, 'discount_rate'):.0%}",
        "Bulk $/unit Jan->Dec": f"${g('Bulk', JAN, 'net_sales_per_unit'):.2f} -> ${g('Bulk', DEC, 'net_sales_per_unit'):.2f} ({pct(g('Bulk', JAN, 'net_sales_per_unit'), g('Bulk', DEC, 'net_sales_per_unit'))})",
        "Medium $/unit Jan->Dec": f"${g('Medium', JAN, 'net_sales_per_unit'):.2f} -> ${g('Medium', DEC, 'net_sales_per_unit'):.2f} ({pct(g('Medium', JAN, 'net_sales_per_unit'), g('Medium', DEC, 'net_sales_per_unit'))})",
        "$/oz by size Dec (S/M/B)": " / ".join(f"${g(t, DEC, 'net_sales_per_oz'):.2f}" for t in ORDER),
        "in-stock SKUs Jan->Dec->Mar": f"{tot[JAN]:.1f} -> {tot[DEC]:.1f} -> {tot[MAR]:.1f} ({pct(tot[JAN], tot[DEC])})",
        "Bulk unit share Jan->Dec->Mar": f"{share.loc[JAN, 'Bulk']:.0%} -> {share.loc[DEC, 'Bulk']:.0%} -> {share.loc[MAR, 'Bulk']:.0%}",
        "blended margin Jan / Dec / Mar": f"{mi.loc[JAN, 'gross_margin']:.0%} / {mi.loc[DEC, 'gross_margin']:.0%} / {mi.loc[MAR, 'gross_margin']:.0%}",
        "ATV Mar 2026": f"${mi.loc[MAR, 'avg_transaction_value']:.2f}",
    }
    for k, v in out.items():
        print(f"{k:34s} {v}")


if __name__ == "__main__":
    main()
