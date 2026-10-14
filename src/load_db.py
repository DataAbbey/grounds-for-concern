"""Load the CSVs into a local SQLite DB and build the EDA views."""
import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "ridgeline.db"

def build():
    con = sqlite3.connect(DB)
    for t in ["stores", "products", "transactions", "inventory_snapshots"]:
        pd.read_csv(ROOT / "data" / f"{t}.csv").to_sql(t, con, if_exists="replace", index=False)
    sql = (ROOT / "sql" / "eda_queries.sql").read_text()
    views_only = sql.split("-- Q4.")[0]
    con.executescript(views_only)
    con.commit()
    return con

if __name__ == "__main__":
    build(); print(f"built {DB}")
