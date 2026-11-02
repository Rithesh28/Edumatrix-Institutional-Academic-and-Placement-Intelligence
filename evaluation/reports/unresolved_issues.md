# Unresolved Issues - ML Evaluation Framework

## Critical Issues (Block Thesis Submission)

### 1. Resume Parser Results Invalid [BUG-001]
- **File:** `evaluation/scripts/evaluate_resume_parser.py:82-86`
- **Problem:** CSV test cases use pipe-delimited format without colons, causing empty expected dict. Field matching logic returns True when both parsed and expected are empty.
- **Impact:** Reported 100% accuracy is completely false. Actual accuracy is unknown (parser returns error for text input).
- **Fix Required:** 
  - Option A: Convert CSV to colon-separated format (`"name: John Smith|email: john.smith@example.com"`)
  - Option B: Modify parser to accept raw text content
  - Option C: Test with actual PDF/DOCX resume files
- **Thesis Impact:** Cannot claim any resume parser performance until fixed

### 2. Sentiment Test Case Duplicate [BUG-002]
- **File:** `evaluation/test_cases/sentiment_analysis_cases.csv:23-24`
- **Problem:** Two test cases share ID `TC_SENT_022`
- **Impact:** 30 reported cases = 29 unique. Accuracy claim of 80% (24/30) should be 82.76% (24/29) if deduplicated.
- **Fix Required:** Rename second TC_SENT_022 to TC_SENT_023, re-run evaluation
- **Thesis Impact:** Minor - changes accuracy by 2.76 percentage points

## Moderate Issues (Affect Metric Interpretation)

### 3. JD Parser Key Mismatch [ISSUE-003]
- **File:** `evaluation/scripts/evaluate_jd_parser.py:82-86`
- **Problem:** Evaluation checks 15 field names that don't match JD parser's actual output keys (e.g., checks `company` but parser outputs `company_name`)
- **Impact:** Reported 86.7% field match (13/15) is coincidental. Many "matches" are from the "both missing" fallback or fuzzy string matching.
- **Fix Required:** Map check keys to actual parser output keys
- **Thesis Impact:** Must be documented as a limitation; actual extraction quality needs separate verification

### 4. Resume Parser Interface Mismatch [ISSUE-005]
- **File:** `backend/app/services/resume_parser.py:100`
- **Problem:** `parse_resume(file_path, content)` expects file paths, not raw text. Evaluation passes text strings.
- **Impact:** Parser returns `UNSUPPORTED_FORMAT` error for all text inputs. The evaluation tests the wrong code path.
- **Fix Required:** Either pass actual file paths to the parser, or add a `parse_text()` method
- **Thesis Impact:** Must document that this evaluation tests a non-production code path

## Minor Issues (Documentation/Clarity)

### 5. Macro F1 > Accuracy Explanation Missing [ISSUE-004]
- **File:** `evaluation/reports/model_evaluation_report.md`
- **Problem:** Intent classifier shows Macro F1 (0.7833) > Accuracy (0.7500) without explanation
- **Impact:** Reader may question this counter-intuitive result
- **Fix Required:** Add explanation that macro averaging gives equal weight to all classes regardless of support
- **Thesis Impact:** Low - add one paragraph to methodology section

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

### 9. Small Test Sets [ISSUE-009, ISSUE-010]
- **Problem:** Intent classifier has 40 cases, Resume parser has 5 cases
- **Impact:** Metrics lack statistical significance
- **Fix Required:** Expand to 100+ cases for intent, 50+ for resume
- **Thesis Impact:** Medium - must be acknowledged as limitation

## Summary

| Severity | Count | Block Thesis? |
|----------|-------|---------------|
| Critical | 2 | YES |
| Moderate | 2 | NO (but must document) |
| Minor | 5 | NO |

**Total:** 9 unresolved issues
**Must fix before submission:** 2 (BUG-001, BUG-002)
**Should document:** 3 (ISSUE-003, ISSUE-004, ISSUE-005)