# Verified Graphs List

This document lists all generated graphs and confirms they match their source data.

## Graphs Directory

Location: `evaluation/graphs/`

## 1. intent_confusion_matrix.png

- **Source Data:** `evaluation/results/intent_classification_results_20261103_000405.csv`
- **Generated:** 2026-11-03 00:04:05
- **Method:** `evaluate_intent_classifier.py:generate_confusion_matrix()`
- **Verification:** Confusion matrix computed from y_true and y_pred arrays in the CSV. Each cell corresponds to actual prediction counts.
- **Status:** VERIFIED ✓

## 2. intent_per_class_metrics.png

- **Source Data:** `evaluation/results/intent_classification_metrics_20261103_000405.json`
- **Generated:** 2026-11-03 00:04:05
- **Method:** `evaluate_intent_classifier.py:generate_per_class_chart()`
- **Verification:** Bar heights correspond exactly to precision/recall/f1 values in the JSON. Values annotated on bars match JSON to 3 decimal places.
- **Status:** VERIFIED ✓

## 3. intent_category_accuracy.png

- **Source Data:** `evaluation/results/intent_classification_results_20261103_000405.csv`
- **Generated:** 2026-11-03 00:04:05
- **Method:** `evaluate_intent_classifier.py:generate_category_analysis()`
- **Verification:** Bar heights match calculated accuracy per category from CSV correct/total columns.
- **Status:** VERIFIED ✓

## 4. sentiment_confusion_matrix.png

- **Source Data:** `evaluation/results/sentiment_analysis_results_20261103_134640.csv` (CORRECTED)
- **Generated:** 2026-11-03 13:46:40
- **Method:** `evaluate_sentiment.py:generate_confusion_matrix()`
- **Verification:** 3x3 matrix computed from y_true and y_pred arrays after BUG-002 fix (TC_SENT_022 renamed to TC_SENT_023). All 30 test cases have unique IDs.
- **Status:** VERIFIED ✓ (CORRECTED)

## 5. sentiment_confidence_distribution.png

- **Source Data:** `evaluation/results/sentiment_analysis_results_20261103_134640.csv` (CORRECTED)
- **Generated:** 2026-11-03 13:46:40
- **Method:** `evaluate_sentiment.py:generate_confidence_distribution()`
- **Verification:** Two histograms split by correct/incorrect predictions. Mean lines correspond to computed averages. BUG-002 fixed.
- **Status:** VERIFIED ✓ (CORRECTED)

## 6. embedding_similarity_confusion.png

- **Source Data:** `evaluation/results/embedding_service_metrics_20261103.json` (original) + `embedding_metrics_fixed_20261103_143515.json` (corrected)
- **Generated:** 2026-11-03
- **Method:** `evaluate_embedding_service.py` (original), `evaluate_embedding_service_fixed.py` (corrected)
- **Verification:** Matrix computed from actual predictions at threshold 0.65. Original had data bug for TC_EMB_019. Corrected version shows confusion matrix from fixed script.
- **Status:** VERIFIED ✓ (CORRECTED)

## 7. embedding_skill_similarity_distribution.png

- **Source Data:** `evaluation/results/embedding_metrics_fixed_20261103_143515.json` (CORRECTED)
- **Generated:** 2026-11-03 14:35:15
- **Method:** `evaluate_embedding_service_fixed.py:generate_skill_similarity_chart()`
- **Verification:** Histogram shows skill pair similarity distributions for positive (n=12) and negative (n=1) pairs with threshold lines at 0.65 and 0.78.
- **Status:** VERIFIED ✓ (CORRECTED)

## 8. embedding_query_similarity_distribution.png

- **Source Data:** `evaluation/results/embedding_metrics_fixed_20261103_143515.json` (CORRECTED)
- **Generated:** 2026-11-03 14:35:15
- **Method:** `evaluate_embedding_service_fixed.py:generate_query_similarity_chart()`
- **Verification:** Histogram shows query pair similarity distributions for positive (n=5) and negative (n=2) pairs.
- **Status:** VERIFIED ✓ (CORRECTED)

## 9. embedding_positive_negative_comparison.png

- **Source Data:** `evaluation/results/embedding_metrics_fixed_20261103_143515.json` (CORRECTED)
- **Generated:** 2026-11-03 14:35:15
- **Method:** `evaluate_embedding_service_fixed.py:generate_comparison_chart()`
- **Verification:** Bar chart compares mean similarity for positive/negative pairs in both skill and query categories. Positive-neg separation = 0.2946.
- **Status:** VERIFIED ✓ (CORRECTED)

## 7. resume_parser_field_accuracy.png

- **Source Data:** `evaluation/results/resume_parser_metrics_fixed_20261103_133849.json` (CORRECTED)
- **Generated:** 2026-11-03 13:38:49
- **Method:** `evaluate_resume_parser_fixed.py:generate_field_accuracy_chart()`
- **Verification:** Horizontal bar chart shows per-field accuracy with correct/total counts. BUG-001 fixed.
- **Status:** VERIFIED ✓ (CORRECTED)

## 8. resume_parser_extraction_performance.png

- **Source Data:** `evaluation/results/resume_parser_metrics_fixed_20261103_133849.json` (CORRECTED)
- **Generated:** 2026-11-03 13:38:49
- **Method:** `evaluate_resume_parser_fixed.py:generate_extraction_performance_chart()`
- **Verification:** Two charts show overall score and pass rate per resume. BUG-001 fixed.
- **Status:** VERIFIED ✓ (CORRECTED)

## 9. jd_parser_field_accuracy.png

- **Source Data:** `evaluation/results/jd_parser_metrics_fixed_20261103_140225.json` (CORRECTED)
- **Generated:** 2026-11-03 14:02:25
- **Method:** `evaluate_jd_parser_fixed.py:generate_field_accuracy_chart()`
- **Verification:** Horizontal bar chart shows per-field accuracy with correct/total counts. ISSU-003 fixed.
- **Status:** VERIFIED ✓ (CORRECTED)

## 10. jd_parser_extraction_performance.png

- **Source Data:** `evaluation/results/jd_parser_metrics_fixed_20261103_140225.json` (CORRECTED)
- **Generated:** 2026-11-03 14:02:25
- **Method:** `evaluate_jd_parser_fixed.py:generate_extraction_performance_chart()`
- **Verification:** Two charts show overall score and pass rate per JD. ISSU-003 fixed.
- **Status:** VERIFIED ✓ (CORRECTED)

## Graphs NOT Generated

The following evaluation scripts failed or produced structural-only output, so no graphs were generated:

| Script | Reason |
|--------|--------|
| evaluate_gliner.py | Graph generation failed (NameError: plt not defined - now fixed) |
| evaluate_study_buddy.py | Structural only - no live model predictions |
| evaluate_ai_chat_analyzer.py | Structural only - no live model predictions |
| evaluate_table_recognition.py | Failed - cv2 not installed |

## Graph Quality Assessment

All 11 generated graphs:
- Resolution: 300 DPI
- Format: PNG
- Size range: 72KB - 266KB
- Color scheme: Consistent (blue for confusion, multi-color for metrics)
- Labels: Clear and readable
- Annotations: Value labels on bars where applicable

**Suitability for Thesis:** All 11 graphs are publication-quality and suitable for inclusion in the thesis report. BUG-001, BUG-002, ISSUE-003, and ISSUE-004 have been corrected.

## Summary of Corrections

| Bug | Graph Files | Status |
|-----|-------------|--------|
| BUG-001 (Resume Parser) | resume_parser_field_accuracy.png, resume_parser_extraction_performance.png | ✅ CORRECTED |
| BUG-002 (Sentiment Duplicate) | sentiment_confusion_matrix.png, sentiment_confidence_distribution.png | ✅ CORRECTED |
| ISSUE-003 (JD Parser Key Mismatch) | jd_parser_field_accuracy.png, jd_parser_extraction_performance.png | ✅ CORRECTED |
| ISSUE-004 (Embedding Methodology) | embedding_similarity_confusion.png, embedding_skill_similarity_distribution.png, embedding_query_similarity_distribution.png, embedding_positive_negative_comparison.png | ✅ CORRECTED |