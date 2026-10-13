import time
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.company import Company
from app.models.job_posting import JobPosting, JobStatus
from app.models.application import Application, ApplicationStatus
from app.services.placement_service import placement_service

def measure_deletion_performance():
    db = SessionLocal()
    try:
        print("=== MEASURING INDIVIDUAL VS BATCHED DELETION ON DISPOSABLE DATA ===")
        # 1. Create a disposable test company
        test_comp = Company(
            name=f"Benchmark_Test_Company_{int(time.time())}",
            is_active=True
        )
        db.add(test_comp)
        db.commit()
        db.refresh(test_comp)

        # 2. Create 20 disposable test jobs with sample applications
        job_ids_individual = []
        job_ids_batched = []
        
        for i in range(10):
            job = JobPosting(
                company_id=test_comp.id,
                title=f"Test Job Indiv {i} {int(time.time())}",
                status=JobStatus.DRAFT,
                required_skills=["Python", "SQL"]
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            job_ids_individual.append(job.id)

        for i in range(10):
            job = JobPosting(
                company_id=test_comp.id,
                title=f"Test Job Batch {i} {int(time.time())}",
                status=JobStatus.DRAFT,
                required_skills=["Python", "SQL"]
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            job_ids_batched.append(job.id)

        print(f"Created 10 individual test jobs and 10 batch test jobs under company {test_comp.id}")

        # Measure 1: Individual Deletion (Simulating current per-record deletion)
        start_indiv = time.perf_counter()
        for jid in job_ids_individual:
            placement_service.delete_job_posting(db, jid)
        elapsed_indiv = time.perf_counter() - start_indiv
        print(f"Individual Deletion (10 jobs, 10 transactions/commits): {elapsed_indiv*1000:.2f} ms ({elapsed_indiv*100:.2f} ms per job)")

        # Measure 2: Batched Set Deletion (Single batched transaction)
        start_batch = time.perf_counter()
        db.execute(text("DELETE FROM job_postings WHERE id IN :jids"), {"jids": tuple(job_ids_batched)})
        db.commit()
        elapsed_batch = time.perf_counter() - start_batch
        print(f"Batched Set Deletion (10 jobs, 1 set query, 1 commit): {elapsed_batch*1000:.2f} ms")

        speedup = (elapsed_indiv / elapsed_batch) if elapsed_batch > 0 else 1.0
        print(f"Speedup: {speedup:.2f}x faster with batched set deletion!")

        # Clean up disposable benchmark company
        db.delete(test_comp)
        db.commit()
        print("Cleaned up disposable benchmark test company.")

    finally:
        db.close()

if __name__ == "__main__":
    measure_deletion_performance()
