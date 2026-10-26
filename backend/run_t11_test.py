import os
import subprocess
import sys

# Set required environment variables
os.environ["TIER1_TEST_DATABASE_URL"] = (
    "postgresql://edumatrix_tier1_test_user:OWFQja7WtGVxfj2FVT41pSMwOcfOswBggNBWZTumJPw=@127.0.0.1:5434/edumatrix_tier1_test"
)
os.environ["TIER1_TEST_REDIS_URL"] = "redis://127.0.0.1:6381/0"

# Run T11 only
cmd = [
    sys.executable, "-m", "pytest",
    "tests/integration/test_issue1_postgres_tier1.py::TestIssue1PostgresTier1::test_11_real_redis_eta_queue_dispatch",
    "-v", "--tb=short"
]

result = subprocess.run(cmd, capture_output=False)
sys.exit(result.returncode)