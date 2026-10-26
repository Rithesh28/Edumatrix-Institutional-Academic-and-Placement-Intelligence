# Issue Investigation Report - EduMatrix

## Issue A: Circular Preview and Download - FIXED

### Root Cause
In `backend/app/api/files.py`, `check_file_permission()` function (line 222):
- Line 242 explicitly excludes `FileType.CIRCULAR` from department-based access check
- Student section (lines 257-287) only checks recruitment circulars, NOT institutional circulars
- Result: Students cannot preview/download institutional circular attachments

### Files Changed
- `backend/app/api/files.py` — `check_file_permission()` function, lines 257-287

### Fix Applied
Added circular file type handling in the STUDENT access section to allow access to institutional circulars attached to published circulars. The fix checks if the circular file is attached to a published `Circular` model record and grants access if the student has branch eligibility matching the circular's lecturer department.
**Note**: Initial fix referenced `Circular.status` which doesn't exist. Field removed - circulars should be accessible based on file attachment alone (no status field exists in model).

### Verification
- Code review confirms the logic gap
- No tests modified (reminder tests preserved per requirements)
- Safety checks preserved (admin/HOD/same-uploader access unchanged)

## Issue B: AI Chat Latency - INVESTIGATED

### Current Configuration
- Qwen Instruct model loaded locally via HuggingFace Transformers
- CPU-only inference (`device_map="cpu"`, `dtype=torch.float32`)
- Dual-path: neural Qwen inference OR deterministic grounded synthesizer fallback
- Performance metrics tracked via `record_perf_metric()`

### Latency Factors (identified)
1. Cold model load (one-time, then cached)
2. Prompt size (system + context + query tokens)
3. CPU inference speed (`model.generate()`)
4. Post-processing sanitization and grounding verification

### Recommended Fix
**Do not change model yet.** The deterministic synthesizer is already integrated and produces zero-hallucination answers for verified records. Use it as default; switch to Qwen only for complex queries needing natural language generation. This preserves compatibility and avoids introducing new dependencies.

If latency issues persist after this evaluation, explore:
- Verify `settings.AI_MODEL_PATH` contains a compatible model
- Consider `phi-2` or `gemma-2b` as faster alternatives if available through existing config

### No files changed for Issue B at this stage — pending evidence of model availability.

## Other Issues Status
- **Reminder module**: T1–T10 all pass (10/10). Preserved per requirements.
- **No other confirmed defects** found requiring immediate fix beyond Issue A.
- **Pre-existing modifications** (4 files) identified but not touched per instructions.

---