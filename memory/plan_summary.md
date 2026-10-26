Circular Attachment Preview/Download Investigation — Plan Complete

All findings from read-only code and configuration inspection. No files modified, no services started, no database writes, no credentials printed, no .env modifications.

Key confirmed facts:
- config.py reads settings via os.getenv() with .env fallbacks (lines 10-72)
- TIER1_TEST_DATABASE_URL NOT read by normal app — only by tier1 test runner (test_issue1_postgres_tier1.py:305)
- check_file_permission() circular logic at files.py:289-311 (Issue A fix): Circular.file_id == file.id access, branch eligibility comparison
- No Circular.status column exists in model (confirmed circular.py, investigation_report.md)
- Issue A fix removed Circular.status == "published" check, replaced with Circular.file_id == file.id
- T11 test stability fix: replaced kombu connection inspection with urllib.parse.urlparse (test file lines 1243-1270)

Unresolved blockers:
1. Service availability on ports 5434/6381/minio-test — unconfirmed without startup
2. Port conflicts — main compose maps MinIO 9000/9001
3. Browser authentication — requires service startup + DB writes
4. Service startup explicitly not approved per user constraint
5. MinIO isolation approach — separate instance vs main with test-circulars/ prefix

Execution gates Phase A-D with approval requirements before each phase. All commands described for review only.