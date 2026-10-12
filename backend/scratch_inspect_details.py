from app.core.database import engine
from sqlalchemy import text

def inspect_details():
    with engine.connect() as conn:
        print("=== NOTIFICATIONS SCHEMA & TYPES ===")
        notif_cols = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'notifications';")).fetchall()
        for c in notif_cols:
            print(f"  {c[0]}: {c[1]}")
        notif_types = conn.execute(text("SELECT type, COUNT(*) FROM notifications GROUP BY type;")).fetchall()
        print("Notification types:")
        for t in notif_types:
            print(f"  {t[0]}: {t[1]}")

        print("\n=== AUDIT LOGS SCHEMA & ACTIONS ===")
        audit_cols = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'audit_logs';")).fetchall()
        for c in audit_cols:
            print(f"  {c[0]}: {c[1]}")
        audit_entities = conn.execute(text("SELECT target_type, COUNT(*) FROM audit_logs GROUP BY target_type;")).fetchall()
        print("Audit target types:")
        for e in audit_entities:
            print(f"  {e[0]}: {e[1]}")

        print("\n=== FILES REFERENCES ===")
        # files references
        # Check files referenced by recruitment_circular_attachments
        rc_files = conn.execute(text("SELECT COUNT(DISTINCT file_id) FROM recruitment_circular_attachments;")).scalar()
        print(f"Files referenced by recruitment_circular_attachments: {rc_files}")
        
        # Check files referenced by recruitment_result_batches
        rb_files = conn.execute(text("SELECT COUNT(DISTINCT file_id) FROM recruitment_result_batches WHERE file_id IS NOT NULL;")).scalar()
        print(f"Files referenced by recruitment_result_batches: {rb_files}")
        
        # Check files referenced by resumes
        res_files = conn.execute(text("SELECT COUNT(DISTINCT file_id) FROM resumes WHERE file_id IS NOT NULL;")).scalar()
        print(f"Files referenced by resumes: {res_files}")
        
        # Check if academic circulars reference files
        circ_cols = [r[0] for r in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'circulars';")).fetchall()]
        print(f"Academic circulars columns: {circ_cols}")
        if 'file_id' in circ_cols:
            ac_files = conn.execute(text("SELECT COUNT(DISTINCT file_id) FROM circulars WHERE file_id IS NOT NULL;")).scalar()
            print(f"Files referenced by academic circulars: {ac_files}")
            
        file_cols = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'files';")).fetchall()
        print("Files table columns:")
        for c in file_cols:
            print(f"  {c[0]}: {c[1]}")

if __name__ == "__main__":
    inspect_details()
