import json
from sqlalchemy import text
from app.core.database import engine

def inspect_db():
    with engine.connect() as conn:
        tables_res = conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;"
        )).fetchall()
        tables = [r[0] for r in tables_res]
        
        counts = {}
        for t in tables:
            try:
                cnt = conn.execute(text(f'SELECT COUNT(*) FROM "{t}";')).scalar()
                counts[t] = cnt
            except Exception as e:
                counts[t] = f"error: {e}"

        # Inspect foreign keys
        fk_query = """
        SELECT
            tc.table_name AS source_table,
            kcu.column_name AS source_column,
            ccu.table_name AS target_table,
            ccu.column_name AS target_column,
            rc.delete_rule AS on_delete
        FROM
            information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.referential_constraints AS rc
              ON tc.constraint_name = rc.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON rc.unique_constraint_name = ccu.constraint_name
              AND rc.unique_constraint_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
        ORDER BY tc.table_name, kcu.column_name;
        """
        fks = conn.execute(text(fk_query)).fetchall()
        fk_list = [
            {
                "source_table": r[0],
                "source_column": r[1],
                "target_table": r[2],
                "target_column": r[3],
                "on_delete": r[4]
            }
            for r in fks
        ]
        
        # Student table columns
        student_cols = conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name IN ('students', 'student_profiles', 'users') 
            ORDER BY table_name, ordinal_position;
        """)).fetchall()
        
        # Placement metrics / student profile values
        student_placement_dist = {}
        for st in ['students', 'student_profiles']:
            if st in tables:
                cols = [r[0] for r in conn.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{st}';")).fetchall()]
                placement_cols = [c for c in cols if any(k in c.lower() for k in ['place', 'offer', 'job', 'status', 'company'])]
                dist = {}
                for pc in placement_cols:
                    try:
                        vals = conn.execute(text(f'SELECT "{pc}", COUNT(*) FROM "{st}" GROUP BY "{pc}";')).fetchall()
                        dist[pc] = {str(v[0]): v[1] for v in vals}
                    except Exception as e:
                        dist[pc] = f"error: {e}"
                student_placement_dist[st] = dist

        out = {
            "table_counts": counts,
            "foreign_keys": fk_list,
            "student_cols": [(r[0], r[1]) for r in student_cols],
            "student_placement_dist": student_placement_dist
        }
        print(json.dumps(out, indent=2))

if __name__ == "__main__":
    inspect_db()
