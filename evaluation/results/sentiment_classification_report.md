# Sentiment Classification Report (Phase 7 Baseline)

**Evaluation Dataset:** 55 test cases  
**Model:** DistilBERT (fine-tuned on Twitter sentiment data)  
**Date:** 2026-11-04

## Overall Metrics

| Metric | Value |
|--------|-------|
| Accuracy | 81.82% |
| Macro F1 | 67.22% |
| Weighted F1 | 85.44% |
| Macro Precision | 61.57% |
| Macro Recall | 93.06% |

## Per-Class Performance

| Class | Precision | Recall | F1-Score | Support |
|-------|-----------|--------|----------|---------|
| Negative | 62.50% | 100.00% | 76.92% | 5 |
| Neutral | 100.00% | 79.17% | 88.37% | 48 |
| Positive | 22.22% | 100.00% | 36.36% | 2 |

## Confusion Matrix

```
                 Predicted
                 neg   neu   pos
Actual  negative  5    0    0
        neutral   3    38    7
        positive  0    0    2
```

## Key Findings

1. **Neutral class**: Highest support (48 cases) but only 79.17% recall — many neutral queries misclassified
2. **Negative class**: Perfect recall (100%) but lower precision (62.50%) — model over-predicts negative
3. **Positive class**: Small support (2 cases) with 100% recall but very low precision (22.22%)
4. **Major error pattern**: Neutral queries with emotional words ('help', 'confused', 'hello') are misclassified
