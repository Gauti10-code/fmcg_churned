import os
import pandas as pd
from sqlalchemy import create_engine,text
from tqdm import tqdm
from dotenv import load_dotenv
import warnings
warnings.filterwarnings("ignore")

load_dotenv()

DB_USER=os.getenv("DB_USER")
DB_PASSWORD=os.getenv("DB_PASSWORD")
DB_HOST=os.getenv("DB_HOST","localhost")
DB_PORT=int(os.getenv("DB_PORT",3306))
DB_NAME=os.getenv("DB_NAME")

DATA_PATH="data/online_retail_II.xlsx"
CHUNK_SIZE=10_000

def get_engine():
  url=f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
  return create_engine(url,echo=False)

def create_database_if_missing():
  root_url=f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/"
  engine=create_engine(root_url,echo=False)
  with engine.connect() as conn:
    conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}`"))
  engine.dispose()
  print(f"Database '{DB_NAME}' ready.")

def load_raw_data(path:str)->pd.DataFrame:
  print("Reading Excel file(this takes ~30 seconds)...")
  df1=pd.read_excel(path,sheet_name="Year 2009-2010",dtype={"Customer ID":str})
  df2=pd.read_excel(path,sheet_name="Year 2010-2011",dtype={"Customer ID":str})
  df=pd.concat([df1,df2],ignore_index=True)
  print(f"Raw rows loaded:{len(df):,}")
  return df

def clean_data(df:pd.DataFrame)->pd.DataFrame:
  print("\n Cleaning Data")
  before=len(df)
  df = df.rename(columns={
        "Invoice":     "invoice_no",
        "StockCode":   "stock_code",
        "Description": "description",
        "Quantity":    "quantity",
        "InvoiceDate": "invoice_date",
        "Price":       "unit_price",
        "Customer ID": "distributor_id",
        "Country":     "country"
    })
  
  df=df.dropna(subset=["distributor_id"])
  df=df[~df["invoice_no"].astype(str).str.startswith("C")]
  df=df[df["quantity"]>0]
  df=df[df["unit_price"]>0]
  df=df.drop_duplicates()

  df["distributor_id"]=df["distributor_id"].str.strip()
  df["invoice_date"]=pd.to_datetime(df["invoice_date"])
  df["quantity"]=df["quantity"].astype(int)
  df["unit_price"]=df["unit_price"].astype(float)
  df["description"]=df["description"].fillna("UNKNOWN").str.strip().str[:255]

  after=len(df)
  print(f" Rows after cleaning:{after,} (removed{before-after:,}dirty_rows)")
  return df

def build_distributors(df: pd.DataFrame) -> pd.DataFrame:
    dist = df.groupby("distributor_id").agg(
        country         = ("country",      lambda x: x.mode()[0]),
        first_seen_date = ("invoice_date", "min"),
        last_seen_date  = ("invoice_date", "max"),
        total_orders    = ("invoice_no",   "nunique"),
        total_revenue   = ("unit_price",   lambda x: (x * df.loc[x.index, "quantity"]).sum())
    ).reset_index()

    dist["first_seen_date"] = dist["first_seen_date"].dt.date
    dist["last_seen_date"]  = dist["last_seen_date"].dt.date
    dist["total_revenue"]   = dist["total_revenue"].round(2)
    print(f"\n👥 Unique distributors: {len(dist):,}")
    return dist      # ← must be indented at this level, inside the def

def run_schema(engine):
  print("Creating tables")
  with open("sql/schema.sql","r")as f:
    statements=f.read().split(";")
  with engine.connect() as conn:
    for stmt in statements:
      stmt=stmt.strip()
      if stmt:
        conn.execute(text(stmt))
    conn.commit()
  print("Tables created:distributors, orders")

def load_distributors(df_dist:pd.DataFrame,engine):
  df_dist.to_sql("distributors",con=engine,if_exists="append",index=False,method="multi")
  print(f"{len(df_dist):,} distributors inserted")

def load_orders(df: pd.DataFrame, engine):
    """Load orders in chunks to avoid memory issues with 500K rows."""
    cols = ["invoice_no", "distributor_id", "stock_code",
            "description", "quantity", "invoice_date", "unit_price", "country"]
    df_orders = df[cols].copy()

    total_chunks = (len(df_orders) // CHUNK_SIZE) + 1
    print(f"\n📤 Loading orders table in {total_chunks} chunks of {CHUNK_SIZE:,} rows...")

    for i, start in enumerate(tqdm(range(0, len(df_orders), CHUNK_SIZE))):
        chunk = df_orders.iloc[start : start + CHUNK_SIZE]
        chunk.to_sql(
            "orders",
            con=engine,
            if_exists="append",
            index=False,
            method="multi"
        )

    print(f"   ✅ {len(df_orders):,} order rows inserted")

def verify_load(engine):
    print("\n🔍 Verification queries:")
    checks = {
        "Total distributors" : "SELECT COUNT(*) FROM distributors",
        "Total order rows"   : "SELECT COUNT(*) FROM orders",
        "Date range"         : "SELECT MIN(invoice_date), MAX(invoice_date) FROM orders",
        "Top 5 countries"    : """
            SELECT country, COUNT(DISTINCT distributor_id) AS dist_count
            FROM distributors GROUP BY country ORDER BY dist_count DESC LIMIT 5
        """
    }
    with engine.connect() as conn:
        for label, query in checks.items():
            result = conn.execute(text(query)).fetchall()
            print(f"\n   {label}:")
            for row in result:
                print(f"      {row}")


if __name__ == "__main__":
    create_database_if_missing()
    engine = get_engine()
    
    df        = load_raw_data(DATA_PATH)
    df        = clean_data(df)
    df_dist   = build_distributors(df)

    run_schema(engine)
    load_distributors(df_dist, engine)
    load_orders(df, engine)
    verify_load(engine)

    print("\n🎉 Step 1 complete! Database fmcg_churn is ready.")
    print("   Next: run sql/02_rfm_features.sql to build churn labels.")
  