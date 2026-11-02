# Sentiment Analysis Evaluation Report

**Date:** 2026-11-02 23:43:13

## Overall Metrics

- **Accuracy:** 0.8000
- **Macro F1:** 0.7824
- **Weighted F1:** 0.7849
- **Mean Confidence:** 0.8360

## Per-Class Performance

| Class | Precision | Recall | F1 | Support |
|-------|-----------|--------|----|---------|
| negative | 0.8462 | 0.9167 | 0.8800 | 12.0 |
| neutral | 0.8333 | 0.5000 | 0.6250 | 10.0 |
| positive | 0.7273 | 1.0000 | 0.8421 | 8.0 |

## Test Case Summary

- **Total Cases:** 30
- **Correct:** 24
- **Accuracy:** 80.00%

## Notes

- Model: DistilBERT fine-tuned checkpoint (268MB)
- Training data: Unknown (checkpoint only)
- 3-class: positive, neutral, negative
