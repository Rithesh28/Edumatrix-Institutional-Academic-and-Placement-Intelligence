# AI Chat Analyzer Evaluation Report (Phase 6)

**Date:** 2026-11-04 16:57:59

## Summary

- **Total Test Cases:** 10
- **Evaluated:** 10
- **Intent Accuracy:** 100.00%
- **Intent Macro F1:** 100.00%
- **Sentiment Accuracy:** 90.00%

## Intent Classification Report

```
                precision    recall  f1-score   support

     ask_doubt     1.0000    1.0000    1.0000         1
 ask_exam_info     1.0000    1.0000    1.0000         2
 career_advice     1.0000    1.0000    1.0000         4
check_deadline     1.0000    1.0000    1.0000         1
         other     1.0000    1.0000    1.0000         2

      accuracy                         1.0000        10
     macro avg     1.0000    1.0000    1.0000        10
  weighted avg     1.0000    1.0000    1.0000        10
```

## Sentiment Classification Report

```
              precision    recall  f1-score   support

    negative     0.5000    1.0000    0.6667         1
     neutral     1.0000    0.8889    0.9412         9

    accuracy                         0.9000        10
   macro avg     0.7500    0.9444    0.8039        10
weighted avg     0.9500    0.9000    0.9137        10
```

## Per-Case Results

| Test Case | Intent (Pred/Exp) | Sentiment (Pred/Exp) | Status |
|-----------|-------------------|----------------------|--------|
| TC_AI_001 | ask_exam_info/ask_exam_info ✓ | neutral/neutral ✓ | PASS |
| TC_AI_002 | check_deadline/check_deadline ✓ | neutral/neutral ✓ | PASS |
| TC_AI_003 | career_advice/career_advice ✓ | neutral/neutral ✓ | PASS |
| TC_AI_004 | career_advice/career_advice ✓ | neutral/neutral ✓ | PASS |
| TC_AI_005 | career_advice/career_advice ✓ | neutral/neutral ✓ | PASS |
| TC_AI_006 | other/other ✓ | neutral/neutral ✓ | PASS |
| TC_AI_007 | other/other ✓ | negative/negative ✓ | PASS |
| TC_AI_008 | ask_exam_info/ask_exam_info ✓ | neutral/neutral ✓ | PASS |
| TC_AI_009 | ask_doubt/ask_doubt ✓ | negative/neutral ✗ | FAIL |
| TC_AI_010 | career_advice/career_advice ✓ | neutral/neutral ✓ | PASS |
