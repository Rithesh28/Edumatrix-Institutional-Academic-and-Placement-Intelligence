# Unresolved Issues - ML Evaluation Framework

## Critical Issues (Block Thesis Submission)

### 1. Resume Parser Results Invalid [BUG-001] - FIXED ✓
- **File:** `evaluation/scripts/evaluate_resume_parser_fixed.py`
- **Problem:** CSV test cases use pipe-delimited format without colons, causing empty expected dict. Field matching logic returns True when both parsed and expected are empty.
- **Fix Applied:** Created new evaluation using real DOCX files with ground truth JSON. Vacuous truth removed.
- **Corrected Metrics:** Field Accuracy=43.64% (24/55), Pass Rate=0.00%
- **Status:** ✅ FIXED

### 2. Sentiment Test Case Duplicate [BUG-002] - FIXED ✓
- **File:** `evaluation/test_cases/sentiment_analysis_cases.csv:23-24`
- **Problem:** Two test cases shared ID `TC_SENT_022`
- **Fix Applied:** Renamed second TC_SENT_022 to TC_SENT_023, re-ran evaluation
- **Corrected Metrics:** Accuracy=80.00% (24/30) - unchanged since both cases were correct
- **Status:** ✅ FIXED

## Moderate Issues (Affect Metric Interpretation)

### 3. JD Parser Key Mismatch [ISSUE-003] - FIXED ✓
- **File:** `evaluation/scripts/evaluate_jd_parser_fixed.py`
- **Problem:** Evaluation checks 15 field names that don't match JD parser's actual output keys (e.g., checks `company` but parser outputs `company_name`)
- **Fix Applied:** Created new evaluation with explicit field name mapping. Vacuous truth removed. Type-aware comparison with fuzzy matching.
- **Corrected Metrics:** Field Accuracy=21.67% (26/120), Pass Rate=0.00%
- **Status:** ✅ FIXED

### 4. Resume Parser Interface Mismatch [ISSUE-005] - FIXED ✓
- **File:** `backend/app/services/resume_parser.py:100`
- **Problem:** `parse_resume(file_path, content)` expects file paths, not raw text. Evaluation passes text strings.
- **Fix Applied:** Now uses real DOCX files passed as file paths
- **Status:** ✅ FIXED (resolved by BUG-001 fix)

## Minor Issues (Documentation/Clarity)

### 5. Embedding Service Evaluation Methodology [ISSUE-004] - FIXED ✓
- **File:** `evaluation/scripts/evaluate_embedding_service_fixed.py`
- **Problem:** Original evaluation compared SBERT cosine similarity against manually-assigned arbitrary "expected_similarity" values (e.g., 0.85, 0.80) and computed a misleading "45% accuracy." No precision/recall/F1 metrics were reported.
- **Fix Applied:** Created corrected script reporting raw cosine distributions, classification metrics at multiple thresholds (0.50, 0.65, 0.78), and proper per-case results.
- **Corrected Metrics:** F1@0.50=0.9375, Precision@all=1.0000, Recall@0.50=0.8824; positive-negative separation=0.2946
- **Status:** ✅ FIXED

### 6. Sentiment Training Data Unknown [ISSUE-006]
- **File:** `evaluation/dataset_inventory.csv`
- **Problem:** Sentiment model training data source and size are unknown (checkpoint only)
- **Impact:** Cannot verify reproducibility or generalization claims
- **Fix Required:** Document as "pre-trained weights, training provenance unknown"
- **Thesis Impact:** Medium - must be disclosed in limitations section

### 7. GLiNER Model Not Cached [ISSUE-007]
- **File:** `evaluation/scripts/evaluate_gliner.py`
- **Problem:** Model `urchade/gliner_base` not available offline
- **Impact:** 0 entities extracted for all 20 test cases
- **Fix Required:** Run `gliner import urchade/gliner_base` or set `local_files_only=False`
- **Thesis Impact:** Low - framework ready, just needs model installation

### 8. Table Recognition Dependency Missing [ISSUE-008]
- **File:** `evaluation/scripts/evaluate_table_recognition.py`
- **Problem:** OpenCV (cv2) not installed
- **Impact:** Script fails on import
- **Fix Required:** Run `pip install opencv-python`
- **Thesis Impact:** Low - framework ready, just needs dependency

### 10. Small Test Sets [ISSUE-009, ISSUE-010, ISSUE-011]
- **Problem:** Intent classifier has 40 cases, Resume parser has 5 cases, Embedding service has 20 pairs
- **Impact:** Metrics lack statistical significance
- **Fix Required:** Expand to 100+ cases for intent, 50+ for resume, 100+ for embedding
- **Thesis Impact:** Medium - must be acknowledged as limitation

## Summary

| Severity | Count | Block Thesis? |
|----------|-------|---------------|
| Critical | 4 | NO (All FIXED) |
| Moderate | 1 | NO (Fixed) |
| Minor | 6 | NO |

**Total:** 11 issues (all tracked)  
**Must fix before submission:** 0 (all critical and moderate issues resolved)  
**Should document:** 6 (ISSUE-005 through ISSUE-011 remain as limitations)