from app.core.database import engine
from sqlalchemy import text
from app.services.file_storage.minio_client import minio_client

def inspect_minio_and_files():
    with engine.connect() as conn:
        # 1. Inspect files table grouped by bucket
        print("=== DATABASE FILES TABLE ===")
        buckets = conn.execute(text("SELECT bucket, COUNT(*) FROM files GROUP BY bucket;")).fetchall()
        for b, count in buckets:
            print(f"Bucket: {b} -> {count} records")

        # 2. Inspect references to files from all tables
        # Find all foreign keys targeting files(id)
        fk_files = conn.execute(text("""
            SELECT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
            WHERE ccu.table_name = 'files' AND tc.constraint_type = 'FOREIGN KEY';
        """)).fetchall()
        print("\nForeign keys pointing to files:")
        for tbl, col in fk_files:
            ref_count = conn.execute(text(f'SELECT COUNT(*) FROM "{tbl}" WHERE "{col}" IS NOT NULL;')).scalar()
            print(f"  {tbl}.{col} -> {ref_count} non-null references")

        # Also check circulars.file_id (might not have explicit FK)
        circ_refs = conn.execute(text("SELECT COUNT(*) FROM circulars WHERE file_id IS NOT NULL;")).scalar()
        print(f"  circulars.file_id -> {circ_refs} references")

        # Check placement vs non-placement file usage
        # Placement tables referencing files:
        # - recruitment_circular_attachments.file_id
        # - recruitment_result_batches.file_id
        # Non-placement tables referencing files:
        # - resumes.file_id
        # - circulars.file_id
        file_analysis = conn.execute(text("""
            SELECT 
                f.id,
                f.bucket,
                f.object_key,
                f.filename,
                (SELECT COUNT(*) FROM recruitment_circular_attachments rca WHERE rca.file_id = f.id) as rca_count,
                (SELECT COUNT(*) FROM recruitment_result_batches rrb WHERE rrb.file_id = f.id) as rrb_count,
                (SELECT COUNT(*) FROM resumes res WHERE res.file_id = f.id) as resume_count,
                (SELECT COUNT(*) FROM circulars circ WHERE circ.file_id = f.id) as circ_count
            FROM files f;
        """)).fetchall()

        placement_only_files = []
        shared_files = []
        non_placement_files = []
        orphaned_files = []

        for row in file_analysis:
            f_id, bucket, okey, fname, rca, rrb, res, circ = row
            is_placement = (rca > 0 or rrb > 0)
            is_non_placement = (res > 0 or circ > 0)
            
            if is_placement and is_non_placement:
                shared_files.append((f_id, bucket, okey, fname, rca, rrb, res, circ))
            elif is_placement:
                placement_only_files.append((f_id, bucket, okey, fname, rca, rrb))
            elif is_non_placement:
                non_placement_files.append((f_id, bucket, okey, fname, res, circ))
            else:
                orphaned_files.append((f_id, bucket, okey, fname))

        print(f"\n--- FILE CATEGORIZATION (Total: {len(file_analysis)}) ---")
        print(f"Placement-only files: {len(placement_only_files)}")
        print(f"Shared files (CRITICAL - MUST PRESERVE): {len(shared_files)}")
        if shared_files:
            for sf in shared_files:
                print(f"   SHARED: ID={sf[0]} bucket={sf[1]} key={sf[2]} name={sf[3]} rca={sf[4]} rrb={sf[5]} resume={sf[6]} circ={sf[7]}")
        print(f"Non-placement files (academic circulars / resumes): {len(non_placement_files)}")
        print(f"Orphaned files (not linked to any table): {len(orphaned_files)}")

        # Check buckets in MinIO server
        print("\n=== MINIO OBJECT STORAGE BUCKETS ===")
        try:
            m_buckets = minio_client.client.list_buckets()
            for b in m_buckets:
                objs = list(minio_client.client.list_objects(b.name, recursive=True))
                print(f"MinIO bucket '{b.name}': {len(objs)} objects")
        except Exception as e:
            print(f"Error checking MinIO: {e}")

if __name__ == "__main__":
    inspect_minio_and_files()
