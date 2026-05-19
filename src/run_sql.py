import sys
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_USER     = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = int(os.getenv("DB_PORT", 3306))
DB_NAME     = os.getenv("DB_NAME")

def get_engine():
    url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(url, echo=False)

def run_sql_file(filepath: str):
    engine = get_engine()
    with open(filepath, "r") as f:
        raw = f.read()

    # Remove comment lines, split on semicolon
    cleaned_lines = [l for l in raw.splitlines() if not l.strip().startswith("--")]
    cleaned = "\n".join(cleaned_lines)
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]

    print(f"\n▶ Running: {filepath}")
    print(f"  Total statements found: {len(statements)}\n")

    # Use a SINGLE connection so @snapshot_date persists across all statements
    with engine.connect() as conn:
        for i, stmt in enumerate(statements):
            if not stmt:
                continue
            try:
                print(f"  [{i+1}/{len(statements)}] Running: {stmt[:80].strip()}...")
                result = conn.execute(text(stmt))
                conn.commit()

                if result.returns_rows:
                    rows = result.fetchall()
                    cols = list(result.keys())
                    print("\n" + "-" * 60)
                    print("  " + "  |  ".join(cols))
                    print("-" * 60)
                    for row in rows:
                        print("  " + "  |  ".join(str(v) for v in row))
                    print()

            except Exception as e:
                print(f"\n⚠️  Error on statement {i+1}: {e}")
                print(f"   Statement: {stmt[:200]}\n")

    print("\n✅ Done.")

if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "sql/02_rfm_features.sql"
    run_sql_file(filepath)