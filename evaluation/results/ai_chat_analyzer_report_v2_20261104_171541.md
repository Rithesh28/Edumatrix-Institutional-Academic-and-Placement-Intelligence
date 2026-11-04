# AI Chat Analyzer Evaluation Report (Phase 6)

**Date:** 2026-11-04 17:15:41

## Summary

- **Total Test Cases:** 55
- **Evaluated:** 55
- **Intent Accuracy:** 76.36%
- **Intent Macro F1:** 77.44%
- **Sentiment Accuracy:** 81.82%

## Intent Classification Report

```
                precision    recall  f1-score   support

     ask_doubt     1.0000    0.5714    0.7273         7
 ask_exam_info     0.7778    0.6364    0.7000        11
 career_advice     0.6667    0.9333    0.7778        15
check_deadline     0.6667    1.0000    0.8000         6
      feedback     1.0000    0.7500    0.8571         4
         greet     1.0000    1.0000    1.0000         3
         other     0.6667    0.6667    0.6667         3
 request_notes     1.0000    0.5000    0.6667         6

      accuracy                         0.7636        55
     macro avg     0.8472    0.7572    0.7744        55
  weighted avg     0.8101    0.7636    0.7579        55
```

## Sentiment Classification Report

```
              precision    recall  f1-score   support

    negative     0.6250    1.0000    0.7692         5
     neutral     1.0000    0.7917    0.8837        48
    positive     0.2222    1.0000    0.3636         2

    accuracy                         0.8182        55
   macro avg     0.6157    0.9306    0.6722        55
weighted avg     0.9376    0.8182    0.8544        55
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
| TC_AI_011 | request_notes/request_notes ✓ | positive/neutral ✗ | FAIL |
| TC_AI_012 | ask_doubt/ask_doubt ✓ | negative/neutral ✗ | FAIL |
| TC_AI_013 | greet/greet ✓ | positive/neutral ✗ | FAIL |
| TC_AI_014 | ask_exam_info/ask_exam_info ✓ | neutral/neutral ✓ | PASS |
| TC_AI_015 | check_deadline/check_deadline ✓ | neutral/neutral ✓ | PASS |
| TC_AI_016 | check_deadline/check_deadline ✓ | neutral/neutral ✓ | PASS |
| TC_AI_017 | career_advice/career_advice ✓ | neutral/neutral ✓ | PASS |
| TC_AI_018 | career_advice/career_advice ✓ | positive/neutral ✗ | FAIL |
| TC_AI_019 | feedback/feedback ✓ | positive/positive ✓ | PASS |
| TC_AI_020 | feedback/feedback ✓ | negative/negative ✓ | PASS |
| TC_AI_021 | ask_exam_info/career_advice ✗ | neutral/neutral ✓ | FAIL |
| TC_AI_022 | ask_exam_info/request_notes ✗ | neutral/neutral ✓ | FAIL |
| TC_AI_023 | ask_exam_info/ask_exam_info ✓ | neutral/neutral ✓ | PASS |
| TC_AI_024 | career_advice/request_notes ✗ | neutral/neutral ✓ | FAIL |
| TC_AI_025 | check_deadline/ask_exam_info ✗ | neutral/neutral ✓ | FAIL |
| TC_AI_026 | ask_doubt/ask_doubt ✓ | negative/neutral ✗ | FAIL |
| TC_AI_027 | career_advice/career_advice ✓ | neutral/neutral ✓ | PASS |
| TC_AI_028 | check_deadline/ask_exam_info ✗ | neutral/neutral ✓ | FAIL |
| TC_AI_029 | career_advice/career_advice ✓ | positive/neutral ✗ | FAIL |
| TC_AI_030 | request_notes/request_notes ✓ | neutral/neutral ✓ | PASS |
| TC_AI_031 | greet/greet ✓ | positive/neutral ✗ | FAIL |
| TC_AI_032 | greet/greet ✓ | positive/neutral ✗ | FAIL |
| TC_AI_033 | ask_exam_info/ask_exam_info ✓ | neutral/neutral ✓ | PASS |
| TC_AI_034 | career_advice/career_advice ✓ | neutral/neutral ✓ | PASS |
| TC_AI_035 | career_advice/ask_doubt ✗ | negative/negative ✓ | FAIL |
| TC_AI_036 | career_advice/career_advice ✓ | neutral/neutral ✓ | PASS |
| TC_AI_037 | check_deadline/ask_exam_info ✗ | neutral/neutral ✓ | FAIL |
| TC_AI_038 | career_advice/other ✗ | positive/neutral ✗ | FAIL |
| TC_AI_039 | ask_exam_info/ask_exam_info ✓ | neutral/neutral ✓ | PASS |
| TC_AI_040 | career_advice/ask_doubt ✗ | neutral/neutral ✓ | FAIL |
| TC_AI_041 | career_advice/career_advice ✓ | neutral/neutral ✓ | PASS |
| TC_AI_042 | other/feedback ✗ | negative/negative ✓ | FAIL |
| TC_AI_043 | feedback/feedback ✓ | positive/positive ✓ | PASS |
| TC_AI_044 | check_deadline/check_deadline ✓ | neutral/neutral ✓ | PASS |
| TC_AI_045 | career_advice/request_notes ✗ | neutral/neutral ✓ | FAIL |
| TC_AI_046 | check_deadline/check_deadline ✓ | neutral/neutral ✓ | PASS |
| TC_AI_047 | career_advice/career_advice ✓ | neutral/neutral ✓ | PASS |
| TC_AI_048 | career_advice/ask_doubt ✗ | negative/negative ✓ | FAIL |
| TC_AI_049 | ask_doubt/ask_doubt ✓ | neutral/neutral ✓ | PASS |
| TC_AI_050 | career_advice/career_advice ✓ | neutral/neutral ✓ | PASS |
| TC_AI_051 | check_deadline/check_deadline ✓ | neutral/neutral ✓ | PASS |
| TC_AI_052 | career_advice/career_advice ✓ | neutral/neutral ✓ | PASS |
| TC_AI_053 | career_advice/ask_exam_info ✗ | neutral/neutral ✓ | FAIL |
| TC_AI_054 | ask_exam_info/ask_exam_info ✓ | neutral/neutral ✓ | PASS |
| TC_AI_055 | request_notes/request_notes ✓ | neutral/neutral ✓ | PASS |
