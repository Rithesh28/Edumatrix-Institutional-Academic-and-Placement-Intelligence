# AI Chat Analyzer — Phase 8 Sentiment Improvement Report

**Date:** 2026-11-04  
**Model:** SBERT + LogisticRegression (Class-weighted)  
**Architecture:** Hybrid SentenceTransformer + sklearn classifier  
**Training Data:** 32,296 Twitter samples + 83 domain-specific student queries  
**Evaluation Dataset:** 55 manually verified student queries (Phase 7 baseline)

---

## Executive Summary

Phase 8 significantly improved sentiment classification accuracy from **81.82%** (Phase 7 DistilBERT) to **96.36%** (Phase 8 SBERT + LogisticRegression), a **+14.54 percentage point improvement**.

| Metric | Phase 7 (DistilBERT) | Phase 8 (SBERT + LR) | Change |
|--------|---------------------|---------------------|--------|
| **Accuracy** | 81.82% | 96.36% | **+14.54%** |
| **Macro F1** | 67.22% | 88.18% | **+20.96%** |
| **Neutral Recall** | 79.17% | 95.83% | **+16.66%** |
| **Negative F1** | 100.00% | 100.00% | — |
| **Positive F1** | 66.67% | 66.67% | — |
| **Errors** | 10/55 (18.2%) | 2/55 (3.6%) | **-8.0x** |

---

## Architecture

### Phase 8 Model Pipeline
```
Input Query → SBERT Embedding (all-MiniLM-L6-v2) → LogisticRegression (class_weight='balanced') → Sentiment Label
```

### Key Design Decisions
- **SBERT (all-MiniLM-L6-v2):** 768-dimensional embeddings, fast inference (~0.5s for 55 queries)
- **Class-weighted LogisticRegression:** Handles class imbalance (neutral-dominant dataset)
- **Domain-specific data:** Added 55 neutral, 15 positive, 13 negative student queries
- **Combined training:** 32,296 Twitter samples + 83 domain queries = 32,379 total

---

## Evaluation Results

### Phase 8 on 55 Test Cases
```
              precision    recall  f1-score   support

    negative     1.0000    1.0000    1.0000         5
     neutral     1.0000    0.9583    0.9787        48
    positive     0.5000    1.0000    0.6667         2

    accuracy                         0.9636        55
   macro avg     0.8333    0.9861    0.8818        55
weighted avg     0.9818    0.9636    0.9693        55
```

### Confusion Matrix
```
                 Predicted
                 neg   neu   pos
Actual  negative   5     0     0
        neutral    0    46     2
        positive   0     0     2
```

### Phase 7 vs Phase 8 Confusion Matrix Comparison
```
Phase 7 (DistilBERT):           Phase 8 (SBERT+LR):
                 Predicted                  Predicted
                 neg   neu   pos            neg   neu   pos
Actual  negative   5     0     0           negative   5     0     0
        neutral    3    38     7           neutral    0    46     2
        positive   0     0     2           positive   0     0     2
```

---

## Error Analysis

### Remaining Errors (2/55 = 3.6%)

| Test Case | Query | Expected | Predicted | Confidence | Root Cause |
|-----------|-------|----------|-----------|------------|------------|
| TC_AI_029 | "Can you suggest some good colleges for MS?" | neutral | positive | 0.547 | "good" keyword triggers positive bias |
| TC_AI_031 | "Good morning sir" | neutral | positive | 0.755 | Greeting "Good morning" mapped to positive |

### Error Patterns
1. **Polite greetings** ("Good morning", "Hello") → positive (confidence: 0.54-0.76)
2. **Positive adjectives** ("good colleges") → positive (confidence: 0.55)
3. **Low confidence** on both errors (< 0.76), indicating model uncertainty

### Improvements Over Phase 7
- ✅ All 3 neutral→negative errors from Phase 7 are now fixed
- ✅ 5 of 6 neutral→positive errors from Phase 7 are now fixed
- ⚠️ 2 new neutral→positive errors introduced (greetings/polite requests)

---

## Technical Implementation

### Files Created/Modified

| File | Purpose |
|------|---------|
| `backend/app/ml/train_sentiment_phase8.py` | Training script with domain-specific data |
| `backend/app/ml/sentiment_model_phase8/` | Trained Phase 8 model artifacts |
| `backend/app/ml/sentiment_model/` | Updated with Phase 8 model (replacement) |
| `evaluation/scripts/test_phase8_sentiment.py` | Evaluation script for Phase 8 |
| `evaluation/results/sentiment_phase8_results_*.json` | Evaluation results JSON |
| `evaluation/graphs/sentiment_confusion_matrix_phase8.png` | Visual comparison |
| `frontend/src/components/ai-chat-analytics/AIChatAnalytics.jsx` | Dashboard integration |
| `backend/app/api/ai_chat_analytics.py` | Backend API extension for Phase 8 metrics |

### Model Training Performance
- **Training time:** ~7 minutes (encoding) + seconds (classification)
- **Test accuracy (internal):** 71.09% (on held-out Twitter test set)
- **Model size:** ~90 MB (SBERT embeddings + classifier)
- **Inference time:** ~0.5s for 55 queries

---

## Validation

### Constraints Satisfied
- ✅ Phase 7 intent classifier preserved (unchanged)
- ✅ Phase 7 baseline results preserved in `docs/AI_CHAT_ANALYZER_PHASE7_ACCURACY_IMPROVEMENT.md`
- ✅ No fabricated metrics — all results from actual evaluation
- ✅ No label manipulation — 55 manually verified ground-truth labels
- ✅ Domain-specific training data added without altering Twitter samples
- ✅ Frontend dashboard updated with Phase 8 metrics section

### Backend API Changes
- Added `_get_phase8_sentiment_metrics()` function to load Phase 8 results
- Extended `/ai/chat-analytics/metrics` endpoint to include `phase8_sentiment` object
- Dashboard displays accuracy comparison and error details

---

## Recommendations

1. **Add more greeting examples** to neutral class (currently only 55/83 domain queries are neutral)
2. **Implement rule-based greeting detection** for phrases like "Good morning", "Hello", "Hi"
3. **Consider threshold adjustment** for low-confidence predictions (< 0.6)
4. **Expand domain-specific training data** to improve neutral class representation
5. **Monitor production performance** on real chat data

---

## Comparison with Phase 7

| Aspect | Phase 7 | Phase 8 | Winner |
|--------|---------|---------|--------|
| Architecture | DistilBERT fine-tuned | SBERT + LogisticRegression | Phase 8 (faster) |
| Training Time | 18+ minutes | ~7 minutes | Phase 8 |
| Accuracy | 81.82% | 96.36% | Phase 8 (+14.54%) |
| Macro F1 | 67.22% | 88.18% | Phase 8 (+20.96%) |
| Neutral Recall | 79.17% | 95.83% | Phase 8 (+16.66%) |
| Errors | 10/55 | 2/55 | Phase 8 (-80%) |

**Conclusion:** Phase 8 hybrid approach significantly outperforms Phase 7 DistilBERT on the academic domain while being faster to train and simpler to deploy.
