#!/usr/bin/env python
"""Direct test runner using pytest API"""
import os
import sys
import pytest

# Must set env vars BEFORE any imports
os.environ["TIER1_TEST_DATABASE_URL"] = "postgresql://edumatrix_tier1_test_user:OWFQja7WtGVxfj2FVT41pSMwOcfOswBggNBWZTumJPw=@127.0.0.1:5434/edumatrix_tier1_test"
os.environ["TIER1_TEST_REDIS_URL"] = "redis://127.0.0.1:6381/0"

# Run T11 only
if __name__ == "__main__":
    sys.exit(pytest.main([
        "tests/integration/test_issue1_postgres_tier1.py::TestIssue1PostgresTier1::test_11_real_redis_eta_queue_dispatch",
        "-v", "--tb=short"
    ]))