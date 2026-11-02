# ML Evaluation Framework - Scientific Audit Report

**Audit Date:** 2026-11-03  
**Auditor:** Claude Code (automated verification)  
**Framework Version:** 1.0  
**Project:** EduMatrix - Institutional Academic and Placement Intelligence

---

## Executive Summary

| Category | Result |
|----------|--------|
| **Critical Bugs Found** | 2 |
| **Moderate Issues** | 3 |
| **Minor Issues** | 2 |
| **Verified Correct** | 3 models |
| **Metrics Need Correction** | 3 models |
| **Graphs Verified** | 5/5 |

**Overall Assessment:** The framework infrastructure is sound, but two critical bugs invalidate the Resume Parser results and skew the Sentiment Analyzer results. The Intent Classifier and Sentiment Analyzer metrics are verified correct. The JD Parser has key-mismatch issues that inflate apparent accuracy.

---

## 1. Critical Bugs (Must Fix Before Thesis Submission)

### BUG-001: Resume Parser Evaluation - FALSE 100% Accuracy [CRITICAL]

**Severity:** P0 - Results Completely Invalid  
**Files Affected:** 
- `evaluation/scripts/evaluate_resume_parser.py:82-86` (expected parsing)
- `evaluation/scripts/evaluate_resume_parser.py:50-72` (field matching logic)
- `evaluation/test_cases/resume_parser_cases.csv:2-6` (test case format)
- `evaluation/results/resume_parser_results_*.csv` (all result files)
- `evaluation/reports/model_evaluation_report.md` (claims 100% accuracy)

**Root Cause (Two-Part Failure):**

**Part A - Empty Expected Dict:** The CSV uses pipe-delimited format (`"John Smith|john.smith@example.com|..."`) but the parser expects colon-separated key-value pairs (`"key: value|key2: value2"`). Since no colons exist in the data, the parsing returns an empty dict `{}` for every test case.

```python
# evaluate_resume_parser.py:84
expected = {k.strip(): v.strip() for k, v in [pair.split(':') for pair in expected_str.split('|') if ':' in pair]}
# With pipe-only data: expected = {}  (always empty!)
```

**Part B - Vacuous Truth in Field Matching:** When both `parsed` and `expected` are empty dicts, the field matching function returns `True` for every field:

```python
# evaluate_resume_parser.py:52-53
if field not in parsed and field not in expected:
    return True  # BOTH EMPTY → returns True for ALL 14 fields!
```

**Evidence from Raw Results:**
```
TC_RESUME_001 predicted: {"success": "False", "error": "Unsupported file type: ."}
TC_RESUME_001 expected: {} (empty due to parsing bug)
Result: 14/14 fields matched (1.00) → FALSE POSITIVE
```

**Actual State:** The resume parser correctly rejects plain text input (returns error), but the evaluation script incorrectly reports 100% field match due to the double-empty-dict bug.

**Impact:** All 5 test cases show 14/14 field match when the actual field match is 0/14. The reported 100% accuracy is completely fabricated by the evaluation bug, not the model.

**Required Fix:**
1. Fix CSV format to use colon-separated key-value pairs
2. OR update the parser to accept raw text content via `content` parameter
3. Re-run evaluation with corrected script
4. Update all reports with actual metrics

---

### BUG-002: Sentiment Test Case Duplicate ID [HIGH]

**Severity:** P1 - Metrics Inflated  
**Files Affected:**
- `evaluation/test_cases/sentiment_analysis_cases.csv:23-24`
- `evaluation/results/sentiment_analysis_results_*.csv`
- `evaluation/results/sentiment_analysis_metrics_*.json`
- `evaluation/reports/model_evaluation_report.md`

**Root Cause:** Test case `TC_SENT_022` appears twice with different content:
- Line 23: `"I am so angry and frustrated with the system"` → expected: negative
- Line 24: `"Thank you so much for your help"` → expected: positive

**Impact:**
- Report claims 30 test cases; actual unique cases = 29
- Accuracy may be inflated if duplicate happened to be correct
- Statistical claims about 30 cases are invalid

**Required Fix:** Rename one duplicate to TC_SENT_023 and renumber subsequent cases.

---

## 2. Moderate Issues (Affect Metric Interpretation)

### ISSUE-003: JD Parser Key Mismatch

**Severity:** P2 - Metrics Partially Valid  
**Files Affected:**
- `evaluation/scripts/evaluate_jd_parser.py:82-86` (field list)
- `evaluation/test_cases/jd_parser_cases.csv` (expected fields format)
- `backend/app/services/jd_parser_service.py:2600-2640` (actual output keys)

**Root Cause:** Evaluation script checks for 15 specific keys that don't match the JD parser's actual output keys:

| Check Key (Script) | Actual Parser Key | Match? |
|---|---|---|
| `company` | `company_name` | ✗ |
| `job_title` | `title` | ✗ |
| `skills` | `required_skills` | ✗ |
| `experience_years` | `experience_level` | ✗ |
| `academic_requirements` | `degree_eligibility` | ✗ |
| `cgpa_requirement` | `cgpa_criteria` | ✗ |
| `percentage_10th` | `academic_percentages['tenth']` | ✗ |
| `percentage_12th` | `academic_percentages['twelfth']` | ✗ |
| `percentage_degree` | `academic_percentages['degree']` | ✗ |
| `compensation` | `salary_range` + `compensation_details` | ✗ |
| `date` | `application_deadline` | ✗ |
| `has_bond` | `bond_details` | ✗ |
| `qualification_required` | `degree_eligibility` | ✗ |

**Impact:** Most fields fall into the "both missing" category (parser key exists but under different name, check key doesn't exist). The reported 13/15 matches are coincidental due to partial key overlap and fuzzy string matching.

**Evidence:** From raw results, `company_name: "TCS ROLE"` but check looks for `company` key which doesn't exist in parsed output. Similarly `title: "Software Trainee..."` but check looks for `job_title`.

**Required Fix:** Map evaluation check keys to actual parser output keys, or update the evaluation script to use the correct key names.

---

### ISSUE-004: Macro F1 > Accuracy Explanation Needed

**Severity:** P3 - Reporting Clarity  
**Files Affected:**
- `evaluation/reports/model_evaluation_report.md`

**Finding:** Intent classifier reports Macro F1 (0.7833) > Accuracy (0.7500). This is mathematically valid but requires explanation in the report.

**Explanation:** Macro F1 averages per-class F1 scores equally, while accuracy weights by class support. With imbalanced classes (ask_doubt has 7 samples, greet has 3), classes with higher F1 but lower support can pull macro F1 above accuracy. In this case:
- career_advice: F1=1.0, support=4 (perfect)
- request_notes: F1=0.857, support=4 (perfect precision)
- feedback: F1=0.857, support=4 (perfect precision)
- These high-F1 low-support classes pull macro average above overall accuracy

This is a valid phenomenon but should be explicitly documented.

---

### ISSUE-005: Resume Parser Architecture Mismatch

**Severity:** P2 - Documentation Gap  
**Files Affected:**
- `evaluation/reports/model_evaluation_report.md`
- `evaluation/README.md`

**Finding:** The report describes the resume parser as "spaCy NER + regex + LayoutLMv3 verification" but the actual `parse_resume()` method expects a file path (PDF/DOCX/JPG), not raw text. The service has separate methods for text extraction (`_extract_from_pdf`, `_extract_from_docx`, `_extract_from_image`).

**Impact:** The evaluation tests the wrong interface. Real usage involves: (1) file upload → text extraction → spaCy NER → LayoutLMv3 verification. The evaluation only tests step 3 in isolation with wrong input type.

**Required Fix:** Either (a) test the full pipeline with actual PDF/DOCX files, or (b) document that this evaluation tests only the text-to-entities sub-component and rename accordingly.

---

## 3. Verified Correct Results

### 3.1 Intent Classifier (SBERT + LR) - VERIFIED ✓

**Re-executed and confirmed:**

| Metric | Reported | Recalculated | Status |
|--------|----------|--------------|--------|
| Accuracy | 0.7500 | 0.7500 (30/40) | ✓ Correct |
| Macro Precision | 0.8110 | 0.8110 | ✓ Correct |
| Macro Recall | 0.7932 | 0.7932 | ✓ Correct |
| Macro F1 | 0.7833 | 0.7833 | ✓ Correct |
| Weighted F1 | 0.7504 | 0.7504 | ✓ Correct |
| Mean Confidence | 0.3412 | 0.3412 | ✓ Correct |

**Per-class F1 verification:**
| Class | Support | Precision | Recall | F1 | Verified |
|-------|---------|-----------|--------|-----|----------|
| ask_doubt | 7 | 0.5000 | 0.4286 | 0.4615 | ✓ |
| greet | 3 | 0.7500 | 1.0000 | 0.8571 | ✓ |
| request_notes | 4 | 1.0000 | 0.7500 | 0.8571 | ✓ |
| check_deadline | 8 | 0.6667 | 0.7500 | 0.7059 | ✓ |
| ask_exam_info | 4 | 0.5714 | 1.0000 | 0.7273 | ✓ |
| career_advice | 4 | 1.0000 | 1.0000 | 1.0000 | ✓ |
| feedback | 4 | 1.0000 | 0.7500 | 0.8571 | ✓ |
| other | 6 | 1.0000 | 0.6667 | 0.8000 | ✓ |

**Test case distribution verified:** 40 unique IDs, 8 intents, balanced with edge cases.

**Graphs verified:** 3 PNG files generated from actual computed matrices, correspond to CSV data.

---

### 3.2 Sentiment Analyzer (DistilBERT) - VERIFIED WITH CAVEAT ✓

**Re-executed and confirmed (with duplicate ID caveat):**

| Metric | Reported | Recalculated | Status |
|--------|----------|--------------|--------|
| Accuracy | 0.8000 | 0.8000 (24/30) | ✓ Correct* |
| Macro F1 | 0.7824 | 0.7824 | ✓ Correct |
| Weighted F1 | 0.7849 | 0.7849 | ✓ Correct |
| Mean Confidence | 0.8360 | 0.8360 | ✓ Correct |

*If deduplicated to 29 unique cases, accuracy would be 24/29 = 82.76% (one of the TC_SENT_022 duplicates was correct).

**Per-class metrics verified from JSON:**
| Class | Precision | Recall | F1 | Support |
|-------|-----------|--------|-----|---------|
| negative | 0.8462 | 0.9167 | 0.8800 | 12 |
| neutral | 0.8333 | 0.5000 | 0.6250 | 10 |
| positive | 0.7273 | 1.0000 | 0.8421 | 8 |

**Graphs verified:** 2 PNG files generated from actual metrics.

---

### 3.3 GLiNER - STRUCTURAL EVALUATION ✓

**Status:** Model unavailable (not cached locally). Script runs but returns 0 entities for all cases. This is correctly reported as "FAILED" in the summary. The structural framework is correct for when the model becomes available.

---

### 3.4 Study Buddy (RAG) & AI Chat Analyzer - STRUCTURAL ✓

Both scripts correctly identify as "PENDING_MODEL_EVAL" and produce structural placeholder reports. No metrics are fabricated.

---

## 4. Reproducibility Audit

### 4.1 Dataset Provenance

| Dataset | Source | Samples | Can Reproduce |
|---------|--------|---------|---------------|
| Intent Classification | Custom manual annotation | 80 (64 train / 16 val) | ✓ Yes, in repo |
| Sentiment | Unknown (checkpoint only) | Unknown | ✗ Cannot verify training |
| TabRecSet | Public academic dataset | Large (symlinked) | ✓ Yes, symlinked |
| Test Cases (all models) | Custom annotated | 95+ | ✓ Yes, in CSV files |

### 4.2 Training/Validation/Test Separation

| Model | Train | Val | Test | Leakage Risk |
|-------|-------|-----|------|-------------|
| Intent Classifier | 64 (80%) | 16 (20%) | 40 external cases | ✓ None |
| Sentiment | Unknown | Unknown | Unknown | ⚠ Cannot verify |
| Table Recognition | 100 (debug) | 20 (debug) | N/A | ✓ None (debug) |

### 4.3 Random Seed

**Intent Classifier:** `seed=42` used in `train_intent_sbert.py:11` ✓  
**Sentiment:** Unknown (no training code in repo)  
**Table Recognition:** `seed=42` used in `train.py` ✓

### 4.4 Model Checkpoints

| Model | Checkpoint Path | Size | Version |
|-------|----------------|------|---------|
| Intent SBERT | `/tmp/intent_model_sbert` | ~1MB | scikit-learn 1.3.2 (unpickled with 1.9.1) |
| Sentiment | `backend/app/ml/sentiment_model/` | 268MB | Unknown |
| Table Recognition | `backend/app/ml/table_recognition/weights/best_model.pth` | 145MB | 3 epochs debug |
| LayoutLMv3 | Auto-downloaded HF cache | Variable | layoutlmv3-base |
| GLiNER | Not cached | N/A | Requires download |

### 4.5 Evaluation Commands

```bash
# Single model
cd evaluation/scripts && python evaluate_intent_classifier.py
cd evaluation/scripts && python evaluate_sentiment.py
cd evaluation/scripts && python evaluate_gliner.py
cd evaluation/scripts && python evaluate_resume_parser.py
cd evaluation/scripts && python evaluate_jd_parser.py

# All models
cd evaluation/scripts && python run_all_evaluations.py
```

### 4.6 Dependencies (Verified)

```
torch, transformers, sentence-transformers, sklearn, matplotlib, seaborn, numpy, pandas, spacy, gliner, pdfplumber, pillow
```

### 4.7 Hardware

All evaluations run on CPU (no GPU detected in any script). This affects latency but not accuracy metrics.

---

## 5. Generated Artifacts Inventory

### 5.1 Verified Graphs (5 files)

| Graph | Source Data | Generated | Verified |
|-------|-------------|-----------|----------|
| `intent_confusion_matrix.png` | intent_classification_results_*.csv | 2026-11-02 | ✓ Matches CSV |
| `intent_per_class_metrics.png` | intent_classification_metrics_*.json | 2026-11-02 | ✓ Matches JSON |
| `intent_category_accuracy.png` | intent_classification_results_*.csv | 2026-11-02 | ✓ Matches CSV |
| `sentiment_confusion_matrix.png` | sentiment_analysis_results_*.csv | 2026-11-02 | ✓ Generated correctly |
| `sentiment_confidence_distribution.png` | sentiment_analysis_results_*.csv | 2026-11-02 | ✓ Generated correctly |

### 5.2 Result Files (19 files)

All JSON files contain computable metrics that match their corresponding CSV/evaluation outputs. No fabricated values detected in verified models.

### 5.3 Reports (8 files)

| Report | Status | Issue |
|--------|--------|-------|
| `intent_classification_report_*.md` | ✓ Accurate | None |
| `sentiment_analysis_report_*.md` | ⚠ Duplicate ID | TC_SENT_022 counted twice |
| `resume_parser_report_*.md` | ✗ INVALID | Based on false 100% match |
| `jd_parser_report_*.md` | ⚠ Partial | Key mismatch inflates score |
| `study_buddy_report_*.md` | ✓ Structural | Correctly marked as pending |
| `ai_chat_analyzer_report_*.md` | ✓ Structural | Correctly marked as pending |
| `model_evaluation_report.md` | ✗ NEEDS UPDATE | Contains incorrect claims |
| `README.md` | ⚠ NEEDS UPDATE | Claims 100% accuracy |

---

## 6. Unresolved Issues

| ID | Severity | Issue | Fix Required |
|----|----------|-------|-------------|
| BUG-001 | P0 | Resume parser eval returns false 100% | Fix CSV format and re-run |
| BUG-002 | P1 | Duplicate TC_SENT_022 in sentiment | Rename and re-run |
| ISSUE-003 | P2 | JD parser key mismatch | Update field mapping |
| ISSUE-004 | P3 | Macro F1 > accuracy unexplained | Add explanation to report |
| ISSUE-005 | P2 | Resume parser tests wrong interface | Use actual PDF files or document sub-component |
| ISSUE-006 | P3 | Sentiment training data unknown | Document as limitation |
| ISSUE-007 | P3 | GLiNER model not cached | Install via `gliner import` |
| ISSUE-008 | P3 | Table recognition missing cv2 | Install opencv-python |
| ISSUE-009 | P3 | Small intent test set (40 cases) | Expand to 100+ for thesis |
| ISSUE-010 | P3 | Resume test set too small (5 cases) | Expand to 50+ for thesis |

---

## 7. Recommendations for Thesis Submission

1. **DO NOT submit** the current resume parser results (100% is false)
2. **Fix BUG-001** before any thesis presentation
3. **Fix BUG-002** and recalculate sentiment metrics
4. **Document ISSUE-003** honestly - acknowledge key-mismatch limitation
5. **Add confidence intervals** to all reported metrics (current n too small)
6. **Expand test sets** to 100+ cases per model for statistical significance
7. **Run RAG evaluations** with live models (Ollama + Qwen) for actual grounding metrics
8. **Include ablation study** showing impact of each pipeline component

---

**Audit Status:** INCOMPLETE - Requires bug fixes before results can be certified accurate.  
**Next Action:** Fix BUG-001 and BUG-002, re-run evaluations, regenerate this audit.
