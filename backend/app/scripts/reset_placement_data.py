"""
EduMatrix - Permanent Placement Data Reset Script
Location: backend/app/scripts/reset_placement_data.py

Destructive script to permanently purge all placement and recruitment data
from the EduMatrix development database while preserving all user accounts,
student academic profiles, resumes, skills, and academic workflows.
"""

import sys
import argparse
from typing import Dict, Any
from sqlalchemy import text
from app.core.database import SessionLocal, engine
from app.services.file_storage.minio_client import minio_client
from app.services.placement_service import placement_service

def verify_environment(db):
    """Confirm connected database is the intended development database."""
    res = db.execute(text("SELECT current_database(), current_user, version();")).fetchone()
    db_name, db_user, version = res[0], res[1], res[2]
    if db_name != "edumatrix":
        raise RuntimeError(f"ABORT: Connected database '{db_name}' is not 'edumatrix'.")
    return db_name, db_user, version

def execute_permanent_placement_reset(clean_audit_logs: bool = False) -> Dict[str, Any]:
    db = SessionLocal()
    report = {
        "status": "pending",
        "deleted_rows": {},
        "updated_rows": {},
        "minio_cleaned": [],
        "minio_failed": [],
        "dashboard_stats": {}
    }
    
    try:
        db_name, db_user, version = verify_environment(db)
        print(f"Verified connected environment: DB='{db_name}', User='{db_user}'")

        # 1. Foreign Key Ordered Deletion Sequence
        tables_to_delete = [
            "student_round_outcomes",
            "recruitment_result_items",
            "recruitment_result_batches",
            "placement_offers",
            "shortlists",
            "recruitment_circular_attachments",
            "recruitment_circular_jobs",
            "recruitment_circulars",
            "recruitment_rounds",
            "applications",
            "job_postings",
            "companies"
        ]

        print("\n--- EXECUTING TRANSACTIONAL DATABASE DELETION ---")
        for table in tables_to_delete:
            del_count = db.execute(text(f'DELETE FROM "{table}";')).rowcount
            report["deleted_rows"][table] = del_count
            print(f"  Deleted {del_count:5d} records from '{table}'")

        # 2. Placement Notifications Cleanup
        notif_del = db.execute(text("""
            DELETE FROM notifications 
            WHERE type IN ('placement_circular', 'placement_job', 'placement_offer', 'placement_result', 'placement_confirm', 'job_posting');
        """)).rowcount
        report["deleted_rows"]["notifications_placement"] = notif_del
        print(f"  Deleted {notif_del:5d} placement notifications")

        # 3. Optional Placement Audit Logs Cleanup
        if clean_audit_logs:
            audit_del = db.execute(text("""
                DELETE FROM audit_logs 
                WHERE target_type IN ('placement_offer', 'recruitment_result_batch', 'student_round_outcome', 'recruitment_round', 'company_bulk', 'circular_bulk');
            """)).rowcount
            report["deleted_rows"]["audit_logs_placement"] = audit_del
            print(f"  Deleted {audit_del:5d} placement audit log records")
        else:
            print("  Preserved placement audit logs for historical audit compliance")

        # 4. Student Profiles Placement Status Reset
        profile_update = db.execute(text("""
            UPDATE student_profiles 
            SET placement_status = 'NOT_APPLIED' 
            WHERE placement_status != 'NOT_APPLIED';
        """)).rowcount
        report["updated_rows"]["student_profiles_reset"] = profile_update
        print(f"  Reset   {profile_update:5d} student profiles to 'NOT_APPLIED' status")

        # 5. Placement-only Files Metadata Cleanup (excluding resumes & circulars)
        files_del = db.execute(text("""
            DELETE FROM files
            WHERE bucket IN ('placement-docs', 'placement-documents')
            AND id NOT IN (SELECT file_id FROM resumes WHERE file_id IS NOT NULL)
            AND id NOT IN (SELECT file_id FROM circulars WHERE file_id IS NOT NULL);
        """)).rowcount
        report["deleted_rows"]["files_placement_metadata"] = files_del
        print(f"  Deleted {files_del:5d} placement-only files metadata records")

        # Commit DB transaction
        db.commit()
        print("Database transaction COMMITTED successfully.")

        # 6. Post-Commit MinIO Object Storage Cleanup (placement-only objects)
        print("\n--- CLEANING PLACEMENT-ONLY MINIO OBJECTS ---")
        placement_objects = [
            ("placement-docs", "5d7c9362-2b08-4989-a198-d3644b2043bf/final_offers.csv"),
            ("placement-docs", "80057404-3683-4f9e-bfa7-c42f6de41f1f/drive_results.csv"),
            ("placement-docs", "c502bca5-3eba-4480-9aee-22943485e34a/secret_draft.pdf"),
            ("placement-docs", "ca395eca-ab3d-4bd5-8ce2-e2986f6d0c4c/drive_poster.pdf"),
            ("placement-docs", "debf36ec-f490-430e-baea-bd621756df47/guidelines.pdf")
        ]
        
        for bucket, obj_key in placement_objects:
            try:
                minio_client.client.remove_object(bucket, obj_key)
                report["minio_cleaned"].append(f"{bucket}/{obj_key}")
                print(f"  Removed MinIO object: {bucket}/{obj_key}")
            except Exception as e:
                report["minio_failed"].append({"object": f"{bucket}/{obj_key}", "error": str(e)})
                print(f"  WARNING: Failed to remove MinIO object {bucket}/{obj_key}: {e}")

        # 7. Verification: Calculate Metrics via Real Placement Service
        print("\n--- RE-CALCULATING DASHBOARD STATS FROM DATABASE ---")
        stats = placement_service.get_placement_statistics(db)
        report["dashboard_stats"] = {
            "total_companies": stats.total_companies,
            "total_jobs": stats.total_jobs,
            "total_applications": stats.total_applications,
            "total_shortlists": stats.total_shortlists,
            "total_placed": stats.total_placed,
            "placement_rate": stats.placement_rate,
            "total_verified_offers": stats.total_verified_offers,
            "verified_placed_students_count": stats.verified_placed_students_count,
            "verified_placement_rate": stats.verified_placement_rate
        }
        
        # Student & Academic Integrity Verification
        total_students = db.execute(text("SELECT COUNT(*) FROM users WHERE role = 'STUDENT';")).scalar()
        total_profiles = db.execute(text("SELECT COUNT(*) FROM student_profiles;")).scalar()
        academic_circ = db.execute(text("SELECT COUNT(*) FROM circulars;")).scalar()
        resumes_cnt = db.execute(text("SELECT COUNT(*) FROM resumes;")).scalar()
        skills_cnt = db.execute(text("SELECT COUNT(*) FROM skills;")).scalar()
        
        report["integrity_verification"] = {
            "total_students": total_students,
            "total_student_profiles": total_profiles,
            "academic_circulars": academic_circ,
            "student_resumes": resumes_cnt,
            "student_skills": skills_cnt
        }

        report["status"] = "success"
        print(f"Reset Complete. Dashboard Metrics: {report['dashboard_stats']}")
        return report

    except Exception as e:
        db.rollback()
        report["status"] = "failed"
        report["error"] = str(e)
        print(f"ERROR: Reset failed and transaction was rolled back: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EduMatrix Placement Data Reset")
    parser.add_argument("--confirm-reset", action="store_true", help="Authorize destructive deletion")
    parser.add_argument("--clean-audit-logs", action="store_true", help="Also purge placement audit logs")
    args = parser.parse_args()

    if not args.confirm_reset:
        print("ABORTED: --confirm-reset flag is required to execute deletion.")
        sys.exit(1)

    execute_permanent_placement_reset(clean_audit_logs=args.clean_audit_logs)
