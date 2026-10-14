"""
Run the EDA: build the SQLite DB, render the report charts, and print the
headline numbers used in the README.

    python src/generate_data.py   # once (about 2 min)
    python src/eda.py

A "unit" is one item sold: one bag counts as one unit, whatever its size.
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

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
ORDER = ["Small", "Medium", "Bulk"]
LABEL = {"Small": "Small (12 oz)", "Medium": "Medium (2 lb)", "Bulk": "Bulk (5 lb)"}
COLOR = {"Small": "#2a78d6", "Medium": "#008300", "Bulk": "#e34948"}  # blue, green, red

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10.5, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.8,
    "legend.frameon": False, "lines.linewidth": 2, "text.parse_math": False,
})
JAN, DEC, MAR = "2025-01", "2025-12", "2026-03"


def shade(ax, xs):
    """Shade the review year (2025) and mark the pricing reset."""
    end = max(i for i, k in enumerate(xs) if k < "2026")
    ax.axvspan(-0.5, end + 0.5, color="#f1ede4", zorder=0, lw=0)
    ax.axvline(end + 0.5, color=INK2, lw=1, ls=(0, (3, 3)), zorder=1)
    top = ax.get_ylim()[1]
    ax.text(-0.3, top, "Review period (2025)", va="top", fontsize=9, color=INK2)
    ax.text(end + 0.7, top, "Pricing reset", va="top", fontsize=9, color=INK2)


def fmt_x(ax, xs, every=3):
    ax.set_xticks(range(len(xs)))
    ax.set_xticklabels([pd.Timestamp(k).strftime("%b\n%y") if i % every == 0 else ""
                        for i, k in enumerate(xs)])
    ax.tick_params(axis="x", length=0)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(CHARTS / name, dpi=160)
    plt.close(fig)


def stacked(wide, xs, title, ylabel, fmt, ymax, name, totals=(JAN, DEC)):
    fig, ax = plt.subplots(figsize=(9, 4.6))
    bottom = pd.Series(0.0, index=wide.index)
    for t in ORDER:
        ax.bar(range(len(xs)), wide[t], bottom=bottom, color=COLOR[t], alpha=0.85, width=0.78,
               label=LABEL[t], edgecolor=SURFACE, linewidth=2)
        bottom += wide[t]
    for k in totals:
        ax.annotate(fmt(bottom[k]), (xs.index(k), bottom[k]), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=9, fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: fmt(v)))
    ax.set_ylim(0, ymax)
    ax.set_title(title); ax.set_ylabel(ylabel)
    fmt_x(ax, xs)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.18), ncol=3)
    save(fig, name)


def lines(wide, xs, title, ylabel, fmt, ymax, name, callouts=(), every=3, markers=True):
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for t in ORDER:
        ax.plot(range(len(xs)), wide[t].values, color=COLOR[t], label=LABEL[t],
                lw=2.5 if t == "Bulk" else 2, marker="o" if markers else None, ms=3.5,
                markeredgecolor=SURFACE, markeredgewidth=1)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: fmt(v)))
    ax.set_ylim(0, ymax)
    for k, dy in callouts:
        v = wide.loc[k, "Bulk"]
        ax.annotate(fmt(v), (xs.index(k), v), xytext=(8 if xs.index(k) < 3 else 0, dy),
                    textcoords="offset points", ha="center", fontsize=9, fontweight="bold")
    ax.set_title(title); ax.set_ylabel(ylabel)
    fmt_x(ax, xs, every); shade(ax, xs)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.18), ncol=3)
    save(fig, name)


def main():
    con = build()
    for old in CHARTS.glob("*.png"):
        old.unlink()

    t = pd.read_sql("""SELECT substr(order_date,1,7) m, p.size_tier s, SUM(net_sales) ns, SUM(qty) u,
                       SUM(net_sales)-SUM(cogs) gm, (SUM(net_sales)-SUM(cogs))/SUM(net_sales) gmp,
                       SUM(discount_amt)/SUM(gross_sales) dr
                       FROM transactions t JOIN products p USING (sku_id) GROUP BY 1,2""", con)
    atv = pd.read_sql("""WITH o AS (SELECT order_id, substr(order_date,1,7) m, SUM(net_sales) ns FROM transactions GROUP BY 1,2),
                         os AS (SELECT DISTINCT t.order_id, p.size_tier s FROM transactions t JOIN products p USING (sku_id))
                         SELECT m, s, AVG(ns) atv FROM o JOIN os USING (order_id) GROUP BY 1,2""", con)
    wk = pd.read_sql("""SELECT date(order_date,'weekday 1','-7 days') m, p.size_tier s,
                        SUM(net_sales)/SUM(qty*size_oz) npo
                        FROM transactions t JOIN products p USING (sku_id) GROUP BY 1,2""", con)
    wk = wk[wk.m >= "2025-01-06"]
    inv = pd.read_sql("""SELECT substr(week_start,1,7) m, size_tier s,
                         SUM(CASE WHEN on_hand_units>0 THEN 1 ELSE 0 END) k
                         FROM inventory_snapshots JOIN products USING (sku_id) GROUP BY 1,2""", con)
    bk = pd.read_sql("""WITH o AS (SELECT order_id, substr(order_date,1,7) m, SUM(qty*size_oz) oz,
                          MAX(size_tier='Small') Small, MAX(size_tier='Medium') Medium, MAX(size_tier='Bulk') Bulk
                          FROM transactions JOIN products USING (sku_id) GROUP BY 1,2)
                        SELECT m, AVG(Small) Small, AVG(Medium) Medium, AVG(Bulk) Bulk FROM o WHERE oz >= 36 GROUP BY 1""",
                     con).set_index("m")
    piv = lambda df, col: df.pivot(index="m", columns="s", values=col)[ORDER]
    xs = sorted(t.m.unique())
    K = lambda v: f"${v / 1000:.0f}K"
    pct = lambda v: f"{v:.0%}"

    # Section 1: steady net sales, rising units, eroding ATV
    stacked(piv(t, "ns"), xs, "Net sales held steady near $370K a month", "Net sales", K, 500_000,
            "01_net_sales_by_size.png")
    stacked(piv(t, "u"), xs, "Units sold rose 13%, from 11.3K to 12.8K", "Units sold (1 bag = 1 unit)",
            lambda v: f"{v / 1000:.1f}K", 16_000, "02_units_by_size.png")
    lines(piv(atv, "atv"), xs, "ATV on Bulk baskets halved, from $110 to $53",
          "ATV of orders containing each size", lambda v: f"${v:.0f}", 140, "03_atv_by_size.png",
          callouts=[(JAN, 8), (DEC, -16)])
    # Section 2: margin and discounts
    stacked(piv(t, "gm"), xs, "Gross margin dollars fell 46%, from $232K to $125K", "Gross margin ($)", K,
            300_000, "04_gross_margin_dollars_by_size.png")
    lines(piv(t, "gmp"), xs, "Bulk gross margin fell from 58% to 23%", "Gross margin %", pct, 0.8,
          "05_gross_margin_pct_by_size.png", callouts=[(DEC, -16), (MAR, -16)])
    lines(piv(t, "dr"), xs, "Discounts on Bulk climbed from 1% to 29%", "Discount %", pct, 0.4,
          "06_discount_pct_by_size.png", callouts=[(DEC, 8)])
    # Section 3: net sales per ounce, weekly
    wxs = sorted(wk.m.unique())
    lines(piv(wk, "npo"), wxs, "Bulk net sales per ounce fell 46%, from $1.00 to $0.54",
          "Net sales per ounce", lambda v: f"${v:.2f}", 2.0, "07_net_sales_per_oz_weekly.png",
          callouts=[("2025-01-13", -16), ("2025-12-15", -16)], every=13, markers=False)
    # Section 4: assortment and customer behavior
    stacked(piv(inv, "k"), xs, "In-stock SKU count events fell by half, from 848 to 413",
            "In-stock SKU count events", lambda v: f"{v:.0f}", 1100, "08_instock_sku_events.png",
            totals=(JAN, "2025-11"))
    lines(bk.reindex(xs), xs, "Bulk went from 48% to 89% of big baskets",
          "Share of 36 oz+ baskets with each size", pct, 1.0, "09_big_basket_mix.png",
          callouts=[(JAN, -16), (DEC, 8)])

    m = pd.read_sql("SELECT * FROM v_monthly", con).set_index("month")
    m["gp"] = m.net_sales * m.gross_margin
    print(f"units Jan->Dec      {m.loc[JAN, 'units_sold']:,.0f} -> {m.loc[DEC, 'units_sold']:,.0f}")
    print(f"net sales Jan->Dec  {K(m.loc[JAN, 'net_sales'])} -> {K(m.loc[DEC, 'net_sales'])}")
    print(f"ATV Jan->Dec->Mar   ${m.loc[JAN, 'avg_transaction_value']:.2f} -> ${m.loc[DEC, 'avg_transaction_value']:.2f} -> ${m.loc[MAR, 'avg_transaction_value']:.2f}")
    print(f"gross margin $      {K(m.loc[JAN, 'gp'])} -> {K(m.loc[DEC, 'gp'])} -> {K(m.loc[MAR, 'gp'])}")


if __name__ == "__main__":
    main()
