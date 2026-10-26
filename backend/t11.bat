@echo off
set TIER1_TEST_DATABASE_URL=postgresql://edumatrix_tier1_test_user:OWFQja7WtGVxfj2FVT41pSMwOcfOswBggNBWZTumJPw=@127.0.0.1:5434/edumatrix_tier1_test
set TIER1_TEST_REDIS_URL=redis://127.0.0.1:6381/0
cd /d Edumatrix-Institutional-Academic-and-Placement-Intelligence\backend
python -m pytest tests\integration\test_issue1_postgres_tier1.py::TestIssue1PostgresTier1::test_11_real_redis_eta_queue_dispatch -v --tb=short %*