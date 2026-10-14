"""
Run the EDA: build the SQLite DB, pull the views, render charts, and print the
headline numbers used in the README.

    python src/generate_data.py   # once (about 1 min)
    python src/eda.py
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

# Palette: validated reference slots 1-3 (all-pairs safe), light surface.
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
TIER = {"Small": "#2a78d6", "Medium": "#1baf7a", "Bulk": "#eb6834"}
TIER_LABEL = {"Small": "Small (12 oz)", "Medium": "Medium (2 lb)", "Bulk": "Bulk (5 lb)"}
ORDER = ["Small", "Medium", "Bulk"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10.5, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.8,
    "legend.frameon": False, "lines.linewidth": 2,
})


def shade(ax, xs):
    """Shade the drift window (Jul-Dec 2025) and mark the pricing reset."""
    lo, hi, reset = xs.index("2025-07"), xs.index("2025-12"), xs.index("2026-01")
    ax.axvspan(lo - 0.5, hi + 0.5, color="#f1ede4", zorder=0, lw=0)
    ax.axvline(reset - 0.5, color=INK2, lw=1, ls=(0, (3, 3)), zorder=1)
    top = ax.get_ylim()[1]
    ax.text(lo - 0.3, top, "Assortment drift", va="top", fontsize=9, color=INK2)
    ax.text(reset - 0.3, top, "Pricing reset", va="top", fontsize=9, color=INK2)


def fmt_months(ax, xs):
    ax.set_xticks(range(len(xs)))
    ax.set_xticklabels([pd.Period(m).strftime("%b\n%y") if i % 3 == 0 else ""
                        for i, m in enumerate(xs)])


def tier_lines(ax, df, col, xs, label_fmt):
    for t in ORDER:
        s = df[df.size_tier == t].set_index("month").reindex(xs)[col]
        ax.plot(range(len(xs)), s.values, color=TIER[t], label=TIER_LABEL[t],
                marker="o", ms=3.5, markeredgecolor=SURFACE, markeredgewidth=1)
        if label_fmt:
            ax.annotate(label_fmt(s.values[-1]), (len(xs) - 1, s.values[-1]),
                        xytext=(6, 0), textcoords="offset points", va="center",
                        fontsize=9, color=INK2)


def main():
    con = build()
    m = pd.read_sql("SELECT * FROM v_monthly ORDER BY month", con)
    mt = pd.read_sql("SELECT * FROM v_monthly_tier ORDER BY month", con)
    inv = pd.read_sql("SELECT * FROM v_instock ORDER BY month", con)
    xs = list(m.month)
    m["gross_profit"] = m.net_sales * m.gross_margin

    # 1. The paradox: volume vs revenue vs profit, indexed to Jun 2025 = 100
    base = m.set_index("month").loc["2025-06"]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    series = [("oz_sold", "Volume (oz sold)", "#2a78d6"),
              ("net_sales", "Net sales", "#1baf7a"),
              ("gross_profit", "Gross profit", "#eb6834")]
    for col, lab, c in series:
        v = m[col] / base[col] * 100
        ax.plot(range(len(xs)), v, color=c, label=lab, marker="o", ms=3.5,
                markeredgecolor=SURFACE, markeredgewidth=1)
        dec = v[xs.index("2025-12")]
        ax.annotate(f"{dec:.0f}", (xs.index("2025-12"), dec), xytext=(0, 8),
                    textcoords="offset points", ha="center", fontsize=9, color=INK2)
    ax.axhline(100, color=INK2, lw=0.8)
    ax.set_title("Volume more than doubled. Gross profit went down.")
    ax.set_ylabel("Index (Jun 2025 = 100)")
    fmt_months(ax, xs); shade(ax, xs)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.18), ncol=3)
    fig.tight_layout(); fig.savefig(CHARTS / "01_volume_vs_profit.png", dpi=160); plt.close(fig)

    # 2. Price ladder: net sales per oz by size
    fig, ax = plt.subplots(figsize=(9, 4.6))
    tier_lines(ax, mt, "net_sales_per_oz", xs, lambda v: f"${v:.2f}")
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:.2f}"))
    ax.set_ylim(0, 1.9)
    ax.set_title("The per-oz price ladder stretched: Bulk fell to a third of Small")
    ax.set_ylabel("Net sales per oz")
    fmt_months(ax, xs); shade(ax, xs)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.18), ncol=3)
    fig.tight_layout(); fig.savefig(CHARTS / "02_net_sales_per_oz_by_size.png", dpi=160); plt.close(fig)

    # 3. Gross margin by size
    fig, ax = plt.subplots(figsize=(9, 4.6))
    tier_lines(ax, mt, "gross_margin", xs, lambda v: f"{v:.0%}")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_ylim(0, 0.8)
    ax.set_title("Bulk gross margin collapsed while Small held steady")
    ax.set_ylabel("Gross margin")
    fmt_months(ax, xs); shade(ax, xs)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.18), ncol=3)
    fig.tight_layout(); fig.savefig(CHARTS / "03_gross_margin_by_size.png", dpi=160); plt.close(fig)

    # 4. Assortment depth
    fig, ax = plt.subplots(figsize=(9, 4.6))
    inv2 = inv.rename(columns={"avg_instock_skus": "v"})
    tier_lines(ax, inv2, "v", xs, None)
    ax.set_ylim(0, 13.5)
    d = xs.index("2025-12"); low = inv2[(inv2.month == "2025-12") & (inv2.size_tier == "Small")].v.iloc[0]
    ax.annotate(f"~{low:.0f} of 12 in stock", (d, low), xytext=(-12, -18),
                textcoords="offset points", ha="right", fontsize=9, color=INK2)
    ax.set_title("Small and Medium SKUs went out of stock; Bulk stayed full")
    ax.set_ylabel("Avg in-stock SKUs per store (of 12)")
    fmt_months(ax, xs); shade(ax, xs)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.18), ncol=3)
    fig.tight_layout(); fig.savefig(CHARTS / "04_instock_skus_by_size.png", dpi=160); plt.close(fig)

    # 5. Mix shift: share of oz sold by size (stacked, 100%)
    share = mt.pivot(index="month", columns="size_tier", values="oz_sold").reindex(xs)[ORDER]
    share = share.div(share.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    bottom = pd.Series(0.0, index=share.index)
    for t in ORDER:
        ax.bar(range(len(xs)), share[t], bottom=bottom, color=TIER[t], width=0.78,
               label=TIER_LABEL[t], edgecolor=SURFACE, linewidth=2)
        bottom += share[t]
    for mo in ["2025-06", "2025-12", "2026-03"]:
        i = xs.index(mo); v = share.loc[mo, "Bulk"]
        ax.text(i, 1 - v / 2, f"{v:.0%}", ha="center", va="center", fontsize=9,
                color=INK, fontweight="bold")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.set_ylim(0, 1.0)
    ax.set_title("Bulk took over the category's volume, then gave some back")
    ax.set_ylabel("Share of oz sold")
    fmt_months(ax, xs)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.18), ncol=3)
    fig.tight_layout(); fig.savefig(CHARTS / "05_size_mix_share.png", dpi=160); plt.close(fig)

    # Headline numbers for the README
    g = lambda df, mo, col, t=None: (df[(df.month == mo) & (df.size_tier == t)] if t else df[df.month == mo])[col].iloc[0]
    jun, dec, mar = "2025-06", "2025-12", "2026-03"
    sm_jun = inv[(inv.month == jun) & inv.size_tier.isin(["Small", "Medium"])].avg_instock_skus.sum()
    sm_dec = inv[(inv.month == dec) & inv.size_tier.isin(["Small", "Medium"])].avg_instock_skus.sum()
    out = {
        "oz sold Jun->Dec": f"{g(m, dec, 'oz_sold') / g(m, jun, 'oz_sold') - 1:+.0%}",
        "net sales Jun->Dec": f"{g(m, dec, 'net_sales') / g(m, jun, 'net_sales') - 1:+.0%}",
        "gross profit Jun->Dec": f"{g(m, dec, 'gross_profit') / g(m, jun, 'gross_profit') - 1:+.0%}",
        "net $/oz Jun->Dec": f"${g(m, jun, 'net_sales_per_oz'):.2f} -> ${g(m, dec, 'net_sales_per_oz'):.2f} ({g(m, dec, 'net_sales_per_oz') / g(m, jun, 'net_sales_per_oz') - 1:+.0%})",
        "Bulk margin Jun->Dec": f"{g(mt, jun, 'gross_margin', 'Bulk'):.0%} -> {g(mt, dec, 'gross_margin', 'Bulk'):.0%}",
        "Bulk discount Jun->Dec": f"{g(mt, jun, 'discount_rate', 'Bulk'):.0%} -> {g(mt, dec, 'discount_rate', 'Bulk'):.0%}",
        "Small+Medium in-stock SKUs Jun->Dec": f"{sm_jun:.1f} -> {sm_dec:.1f} ({sm_dec / sm_jun - 1:+.0%})",
        "Bulk share of oz Jun->Dec->Mar": f"{share.loc[jun, 'Bulk']:.0%} -> {share.loc[dec, 'Bulk']:.0%} -> {share.loc[mar, 'Bulk']:.0%}",
        "net $/oz Mar 2026 (post-reset)": f"${g(m, mar, 'net_sales_per_oz'):.2f}",
        "Bulk margin Mar 2026 (post-reset)": f"{g(mt, mar, 'gross_margin', 'Bulk'):.0%}",
        "blended margin Jun / Dec / Mar": f"{g(m, jun, 'gross_margin'):.0%} / {g(m, dec, 'gross_margin'):.0%} / {g(m, mar, 'gross_margin'):.0%}",
    }
    for k, v in out.items():
        print(f"{k:38s} {v}")


if __name__ == "__main__":
    main()
