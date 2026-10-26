#!/usr/bin/env python
"""Run Tier 1 integration tests with proper environment setup"""
import os
import subprocess
import sys

# Set the required environment variable
os.environ["TIER1_TEST_DATABASE_URL"] = "postgresql://edumatrix_tier1_test_user:OWFQja7WtGVxfj2FVT41pSMwOcfOswBggNBWZTumJPw=@127.0.0.1:5434/edumatrix_tier1_test"

# Run the tests
cmd = [
    sys.executable, "-m", "pytest",
    "tests/integration/test_issue1_postgres_tier1.py",
    "-k", "test_01 or test_02 or test_03 or test_04 or test_05 or test_06 or test_07 or test_08 or test_09 or test_10",
    "-v", "--tb=short"
]

result = subprocess.run(cmd, capture_output=False)
sys.exit(result.returncode)