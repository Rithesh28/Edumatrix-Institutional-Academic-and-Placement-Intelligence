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

- **Source Data:** `evaluation/results/sentiment_analysis_results_20261102_235133.csv`
- **Generated:** 2026-11-02 23:51:33
- **Method:** `evaluate_sentiment.py:generate_confusion_matrix()`
- **Verification:** 3x3 matrix computed from y_true and y_pred arrays.
- **Status:** VERIFIED ✓

## 5. sentiment_confidence_distribution.png

- **Source Data:** `evaluation/results/sentiment_analysis_results_20261102_235133.csv`
- **Generated:** 2026-11-02 23:51:33
- **Method:** `evaluate_sentiment.py:generate_confidence_distribution()`
- **Verification:** Two histograms split by correct/incorrect predictions. Mean lines correspond to computed averages.
- **Status:** VERIFIED ✓

## Graphs NOT Generated

The following evaluation scripts failed or produced structural-only output, so no graphs were generated:

| Script | Reason |
|--------|--------|
| evaluate_gliner.py | Graph generation failed (NameError: plt not defined - now fixed) |
| evaluate_resume_parser.py | No graph generated (script exited before chart creation) |
| evaluate_jd_parser.py | No graph generated (script exited before chart creation) |
| evaluate_study_buddy.py | Structural only - no live model predictions |
| evaluate_ai_chat_analyzer.py | Structural only - no live model predictions |
| evaluate_table_recognition.py | Failed - cv2 not installed |

## Graph Quality Assessment

All 5 generated graphs:
- Resolution: 300 DPI
- Format: PNG
- Size range: 77KB - 191KB
- Color scheme: Consistent (blue for confusion, multi-color for metrics)
- Labels: Clear and readable
- Annotations: Value labels on bars where applicable

**Suitability for Thesis:** All 5 graphs are publication-quality and suitable for inclusion in the thesis report.