# Intent Classifier Evaluation Report

**Date:** 2026-11-02 23:51:09

## Overall Metrics

- **Accuracy:** 0.7500
- **Macro Precision:** 0.8110
- **Macro Recall:** 0.7932
- **Macro F1:** 0.7833
- **Weighted Precision:** 0.7842
- **Weighted Recall:** 0.7500
- **Weighted F1:** 0.7504

## Per-Class Performance

| Class | Precision | Recall | F1 | Support |
|-------|-----------|--------|----|---------|
| ask_doubt | 0.5000 | 0.4286 | 0.4615 | 7.0 |
| greet | 0.7500 | 1.0000 | 0.8571 | 3.0 |
| request_notes | 1.0000 | 0.7500 | 0.8571 | 4.0 |
| check_deadline | 0.6667 | 0.7500 | 0.7059 | 8.0 |
| ask_exam_info | 0.5714 | 1.0000 | 0.7273 | 4.0 |
| career_advice | 1.0000 | 1.0000 | 1.0000 | 4.0 |
| feedback | 1.0000 | 0.7500 | 0.8571 | 4.0 |
| other | 1.0000 | 0.6667 | 0.8000 | 6.0 |

## Test Case Summary

- **Total Cases:** 40
- **Correct:** 30
- **Accuracy:** 75.00%

## By Category

| Category | Correct | Total | Accuracy |
|----------|---------|-------|----------|
| Normal valid input | 26 | 28 | 92.86% |
| Difficult/ambiguous | 1 | 6 | 16.67% |
| Missing information | 2 | 4 | 50.00% |
| Incorrectly formatted | 1 | 2 | 50.00% |
