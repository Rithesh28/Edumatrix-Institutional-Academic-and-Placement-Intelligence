from sqlalchemy import text
from app.core.database import SessionLocal
from app.services.placement_service import placement_service
from app.services.placement_offer_service import placement_offer_service

def run_dry_run_simulation():
    db = SessionLocal()
    try:
        # Start transaction
        print("=== COMMENCING DRY-RUN SIMULATION (WILL ROLLBACK) ===")
        
        # 1. Capture baseline counts
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
        
        baseline_counts = {}
        for t in tables_to_delete:
            baseline_counts[t] = db.execute(text(f'SELECT COUNT(*) FROM "{t}";')).scalar()
            
        notif_placement_count = db.execute(text("""
            SELECT COUNT(*) FROM notifications 
            WHERE type IN ('placement_circular', 'placement_job', 'placement_offer', 'placement_result', 'placement_confirm', 'job_posting');
        """)).scalar()
        
        student_profiles_to_reset = db.execute(text("""
            SELECT COUNT(*) FROM student_profiles WHERE placement_status != 'NOT_APPLIED';
        """)).scalar()
        
        total_students_before = db.execute(text("SELECT COUNT(*) FROM users WHERE role = 'STUDENT';")).scalar()
        total_profiles_before = db.execute(text("SELECT COUNT(*) FROM student_profiles;")).scalar()
        total_users_before = db.execute(text("SELECT COUNT(*) FROM users;")).scalar()
        academic_circ_before = db.execute(text("SELECT COUNT(*) FROM circulars;")).scalar()
        resumes_before = db.execute(text("SELECT COUNT(*) FROM resumes;")).scalar()
        skills_before = db.execute(text("SELECT COUNT(*) FROM skills;")).scalar()

        # Find placement-only file IDs
        placement_files_query = """
        SELECT id FROM files
        WHERE bucket IN ('placement-docs', 'placement-documents')
        AND id NOT IN (SELECT file_id FROM resumes WHERE file_id IS NOT NULL)
        AND id NOT IN (SELECT file_id FROM circulars WHERE file_id IS NOT NULL);
        """
        placement_file_ids = [str(r[0]) for r in db.execute(text(placement_files_query)).fetchall()]
        
        print("\n--- BASELINE AUDIT ---")
        for t in tables_to_delete:
            print(f"  {t:35}: {baseline_counts[t]} rows")
        print(f"  {'placement_notifications':35}: {notif_placement_count} rows")
        print(f"  {'student_profiles_to_reset':35}: {student_profiles_to_reset} records")
        print(f"  {'placement_only_files_in_db':35}: {len(placement_file_ids)} records")
        
        print("\n--- SIMULATING DELETION SEQUENCE IN TRANSACTION ---")
        deleted_counts = {}
        for t in tables_to_delete:
            del_cnt = db.execute(text(f'DELETE FROM "{t}";')).rowcount
            deleted_counts[t] = del_cnt
            print(f"  DELETE FROM {t:32} -> {del_cnt} rows deleted")
            
        del_notifs = db.execute(text("""
            DELETE FROM notifications 
            WHERE type IN ('placement_circular', 'placement_job', 'placement_offer', 'placement_result', 'placement_confirm', 'job_posting');
        """)).rowcount
        print(f"  DELETE FROM notifications (placement)     -> {del_notifs} rows deleted")

        updated_profiles = db.execute(text("""
            UPDATE student_profiles SET placement_status = 'NOT_APPLIED' WHERE placement_status != 'NOT_APPLIED';
        """)).rowcount
        print(f"  UPDATE student_profiles (reset status)    -> {updated_profiles} records updated")

        del_files = db.execute(text("""
            DELETE FROM files
            WHERE bucket IN ('placement-docs', 'placement-documents')
            AND id NOT IN (SELECT file_id FROM resumes WHERE file_id IS NOT NULL)
            AND id NOT IN (SELECT file_id FROM circulars WHERE file_id IS NOT NULL);
        """)).rowcount
        print(f"  DELETE FROM files (placement-only)        -> {del_files} metadata rows deleted")

        # Verify integrity within transaction
        print("\n--- INTEGRITY CHECKS WITHIN TRANSACTION ---")
        for t in tables_to_delete:
            cnt = db.execute(text(f'SELECT COUNT(*) FROM "{t}";')).scalar()
            print(f"  Table {t:32} remaining: {cnt}")
            assert cnt == 0, f"Table {t} should have 0 records"

        total_students_after = db.execute(text("SELECT COUNT(*) FROM users WHERE role = 'STUDENT';")).scalar()
        total_profiles_after = db.execute(text("SELECT COUNT(*) FROM student_profiles;")).scalar()
        total_users_after = db.execute(text("SELECT COUNT(*) FROM users;")).scalar()
        academic_circ_after = db.execute(text("SELECT COUNT(*) FROM circulars;")).scalar()
        resumes_after = db.execute(text("SELECT COUNT(*) FROM resumes;")).scalar()
        skills_after = db.execute(text("SELECT COUNT(*) FROM skills;")).scalar()
        
        print(f"  User accounts (total)      : Before={total_users_before}, After={total_users_after} (MATCH: {total_users_before == total_users_after})")
        print(f"  Student users              : Before={total_students_before}, After={total_students_after} (MATCH: {total_students_before == total_students_after})")
        print(f"  Student profiles           : Before={total_profiles_before}, After={total_profiles_after} (MATCH: {total_profiles_before == total_profiles_after})")
        print(f"  Academic circulars         : Before={academic_circ_before}, After={academic_circ_after} (MATCH: {academic_circ_before == academic_circ_after})")
        print(f"  Resumes                    : Before={resumes_before}, After={resumes_after} (MATCH: {resumes_before == resumes_after})")
        print(f"  Skills                     : Before={skills_before}, After={skills_after} (MATCH: {skills_before == skills_after})")

        # Test Placement Dashboard Stats Calculation
        print("\n--- DASHBOARD STATS API CALCULATION WITHIN TRANSACTION ---")
        stats = placement_service.get_placement_statistics(db)
        print(f"  Total Companies   : {stats.total_companies}")
        print(f"  Total Jobs        : {stats.total_jobs}")
        print(f"  Total Applications: {stats.total_applications}")
        print(f"  Total Shortlists  : {stats.total_shortlists}")
        print(f"  Students Placed   : {stats.total_placed}")
        print(f"  Placement Rate    : {stats.placement_rate}%")
        print(f"  Verified Offers   : {stats.total_verified_offers}")
        print(f"  Verified Placed   : {stats.verified_placed_students_count}")
        print(f"  Verified Rate     : {stats.verified_placement_rate}%")
        
        assert stats.total_companies == 0
        assert stats.total_jobs == 0
        assert stats.total_applications == 0
        assert stats.total_shortlists == 0
        assert stats.total_placed == 0
        assert stats.placement_rate == 0.0
        assert stats.total_verified_offers == 0
        assert stats.verified_placed_students_count == 0
        assert stats.verified_placement_rate == 0.0
        print("\n>>> ALL ASSERTIONS PASSED! ZERO HARDCODING, PURE DB CALCULATIONS. <<<")
        
    finally:
        print("\n=== ROLLING BACK TRANSACTION (ZERO CHANGES COMMITTED) ===")
        db.rollback()
        db.close()
        
    # Verify post-rollback that database is 100% untouched
    verify_db = SessionLocal()
    comp_cnt = verify_db.execute(text("SELECT COUNT(*) FROM companies;")).scalar()
    circ_cnt = verify_db.execute(text("SELECT COUNT(*) FROM recruitment_circulars;")).scalar()
    verify_db.close()
    print(f"Post-rollback live companies: {comp_cnt}, recruitment_circulars: {circ_cnt}")

if __name__ == "__main__":
    run_dry_run_simulation()
