from app.core.database import engine
from sqlalchemy import text
from app.services.file_storage.minio_client import minio_client

def inspect_placement_files():
    with engine.connect() as conn:
        q = """
        SELECT f.id, f.bucket, f.object_key, f.filename, f.file_size
        FROM files f
        WHERE f.id IN (
            SELECT file_id FROM recruitment_circular_attachments WHERE file_id IS NOT NULL
            UNION
            SELECT file_id FROM recruitment_result_batches WHERE file_id IS NOT NULL
            UNION
            SELECT offer_letter_file_id FROM placement_offers WHERE offer_letter_file_id IS NOT NULL
        );
        """
        rows = conn.execute(text(q)).fetchall()
        print(f"Total placement files in DB: {len(rows)}")
        
        # Check which exist in MinIO
        minio_exists = 0
        minio_missing = 0
        buckets_used = {}
        for r in rows:
            f_id, bucket, okey, fname, fsize = r
            buckets_used[bucket] = buckets_used.get(bucket, 0) + 1
            try:
                minio_client.client.stat_object(bucket, okey)
                minio_exists += 1
            except Exception:
                minio_missing += 1

        print("Placement files by DB bucket:", buckets_used)
        print(f"Actually present in MinIO: {minio_exists}")
        print(f"Missing from MinIO (DB record only): {minio_missing}")

if __name__ == "__main__":
    inspect_placement_files()
