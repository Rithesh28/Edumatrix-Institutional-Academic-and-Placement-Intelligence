from app.core.database import engine
from sqlalchemy import text

def check_fk_isolation():
    placement_tables = [
        'companies', 'job_postings', 'applications', 'shortlists',
        'placement_offers', 'recruitment_circulars', 'recruitment_circular_jobs',
        'recruitment_circular_attachments', 'recruitment_rounds',
        'recruitment_result_batches', 'recruitment_result_items',
        'student_round_outcomes'
    ]
    with engine.connect() as conn:
        q = """
        SELECT
            tc.table_name AS source_table,
            kcu.column_name AS source_column,
            ccu.table_name AS target_table,
            ccu.column_name AS target_column
        FROM
            information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON tc.constraint_name = ccu.constraint_name
              AND tc.table_schema = ccu.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND ccu.table_name IN :ptables
        AND tc.table_name NOT IN :ptables;
        """
        res = conn.execute(text(q), {"ptables": tuple(placement_tables)}).fetchall()
        print(f"External tables referencing placement tables: {len(res)}")
        for r in res:
            print(f"  {r[0]}.{r[1]} -> {r[2]}.{r[3]}")

if __name__ == "__main__":
    check_fk_isolation()
