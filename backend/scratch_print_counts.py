from app.core.database import engine
from sqlalchemy import text

def main():
    with engine.connect() as conn:
        tables = [r[0] for r in conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;")).fetchall()]
        print("--- ALL TABLE ROW COUNTS ---")
        for t in tables:
            cnt = conn.execute(text(f'SELECT COUNT(*) FROM "{t}";')).scalar()
            print(f"{t:35} : {cnt}")

if __name__ == "__main__":
    main()
