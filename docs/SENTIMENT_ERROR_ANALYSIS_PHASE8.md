# Sentiment Error Analysis — Phase 8

**Date:** 2026-11-04  
**Model:** DistilBERT (fine-tuned on Twitter sentiment + domain-specific data)  
**Evaluation Dataset:** 55 manually verified student queries  
**Error Rate:** 10/55 (18.2%)

---

## Error Summary

| Error Category | Count | Description |
|----------------|-------|-------------|
| Neutral → Negative | 3 | Academic queries with "help", "confused" keywords |
| Neutral → Positive | 6 | Greetings, help requests, polite queries |
| Negative → Others | 0 | All negative queries correctly classified |
| Positive → Others | 0 | No positive queries misclassified |

---

## Detailed Error Analysis

### 1. Neutral → Negative (3 cases)

| Test Case | Query | Predicted | Confidence | Root Cause |
|-----------|-------|-----------|------------|------------|
| TC_AI_009 | "I need help with my assignment but I am not sure which one" | negative | 0.614 | "not sure" triggers uncertainty/negative bias |
| TC_AI_012 | "I don't understand pointers in C language" | negative | 0.844 | "don't understand" = confusion/negative |
| TC_AI_026 | "I am confused about branching criteria" | negative | 0.862 | "confused" = strong negative signal |

**Pattern:** Words expressing uncertainty or confusion are mapped to negative sentiment by the model, even though the query itself is neutral/informational.

---

### 2. Neutral → Positive (6 cases)

| Test Case | Query | Predicted | Confidence | Root Cause |
|-----------|-------|-----------|------------|------------|
| TC_AI_011 | "Can you share the lecture notes for Data Structures?" | positive | 0.525 | Polite request ("can you") interpreted positively |
| TC_AI_013 | "Hello, I'm a first year student" | positive | 0.623 | Greeting "Hello" mapped to positive |
| TC_AI_018 | "How to crack Amazon campus interview?" | positive | 0.488 | "crack" (success verb) triggers positive |
| TC_AI_029 | "Can you suggest some good colleges for MS?" | positive | 0.827 | "good" keyword dominates sentiment |
| TC_AI_031 | "Good morning sir" | positive | 0.785 | "Good morning" = greeting = positive |
| TC_AI_032 | "Hey, can you help me?" | positive | 0.571 | "help me" + greeting = positive |
| TC_AI_038 | "Who is the HOD of ECE department?" | positive | 0.544 | Neutral question incorrectly tagged |

**Pattern:** Greetings, polite requests, and words like "good", "help", "can you" trigger positive bias. These are **information-seeking** queries with no emotional content.

---

## Key Findings

1. **Neutral class is most affected**: 10/48 neutral queries (20.8%) misclassified
2. **Negative confusion**: Academic frustration ("confused", "don't understand") → negative
3. **Positive confusion**: Politeness/greetings ("hello", "can you", "good") → positive
4. **Negative and positive classes are well-classified**: 5/5 negative (100%), 2/2 positive (100%)
5. **Domain gap**: Training data is Twitter conversations; student academic queries don't match patterns

---

## Recommendations

1. **Add domain-specific neutral examples** to training data
2. **Create explicit rules** for greeting phrases (hello, hey, good morning)
3. **Separate "help" intent from sentiment**: Help requests are neutral intent, not negative sentiment
4. **Add academic context to training**: Questions about exams, assignments, placements should be labeled neutral
5. **Consider a two-stage approach**: First detect if query is a simple greeting, then classify sentiment

---

## Confusion Matrix (Phase 7)

```
                 Predicted
                 neg   neu   pos
Actual  negative   5     0     0
        neutral    3    38     7
        positive   0     0     2
```

**Correct predictions:** 45/55 (81.8%)  
**Neutral recall:** 38/48 (79.2%) — biggest area for improvement
