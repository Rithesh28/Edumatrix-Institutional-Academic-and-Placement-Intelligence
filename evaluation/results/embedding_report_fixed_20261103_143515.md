# Embedding Service Evaluation Report (Corrected Methodology)

**Model:** all-MiniLM-L6-v2 (SBERT all-MiniLM-L6-v2)
**Embedding Dimension:** 384
**Evaluation Date:** 2026-11-03 14:35:42

## Methodology

The original evaluation compared SBERT cosine similarity scores against manually-assigned
"expected_similarity" values (e.g., 0.85, 0.80) and computed a misleading "accuracy" of 45%.
This is scientifically invalid because:

1. Expected similarities were arbitrarily assigned, not independently established ground truth
2. The threshold (0.65) was hand-waved as "reasonable" with no validation
3. The 45% metric conflates label quality with model quality

**Corrected approach:** Report raw cosine similarity distributions, compute proper
classification metrics (precision/recall/F1) at multiple validated thresholds, separate
skill pairs from query pairs, and transparently document dataset limitations.

## Dataset

- **Total pairs:** 20 (13 skill + 7 query)
- **Positive pairs (semantic match):** 17
- **Negative pairs (no semantic match):** 3
- **Limitation:** Small dataset (n=20); labels are manually assigned

## Descriptive Statistics

### All Pairs

- Mean cosine similarity: 0.5778
- Std deviation: 0.1715
- Range: [0.1121, 0.8189]

### Positive Pairs (Expected Match)

- Mean: 0.6220, Std: 0.1316
- Range: [0.3312, 0.8189]

### Negative Pairs (Expected No-Match)

- Mean: 0.3274, Std: 0.1557
- Range: [0.1121, 0.4750]

**Positive-Negative separation:** 0.2946

### Skill Pairs

- Positive (n=12): mean=0.6003, std=0.1389
- Negative (n=1): mean=0.3952, std=0.0000

### Query Pairs

- Positive (n=5): mean=0.6740, std=0.0934
- Negative (n=2): mean=0.2935, std=0.1815

## Classification Metrics at Multiple Thresholds

| Threshold | Accuracy | Precision | Recall | F1 | TP | TN | FP | FN |
|-----------|----------|-----------|--------|-----|----|----|----|----|
| threshold_0.50 | 0.9000 | 1.0000 | 0.8824 | 0.9375 | 15 | 3 | 0 | 2 |
| threshold_0.65 | 0.4500 | 1.0000 | 0.3529 | 0.5217 | 6 | 3 | 0 | 11 |
| threshold_0.78 | 0.2500 | 1.0000 | 0.1176 | 0.2105 | 2 | 3 | 0 | 15 |

## Per-Case Results

| Case ID | Category | Cosine Sim | Expected | Pred@0.65 | Pred@0.78 | Pred@0.50 |
|---------|----------|------------|----------|-----------|-----------|-----------|
| TC_EMB_001 | Skill Match | 0.7582 | Yes | Yes | No | Yes |
| TC_EMB_002 | Skill Match | 0.6328 | Yes | No | No | Yes |
| TC_EMB_003 | Skill Match | 0.3952 | No | No | No | No |
| TC_EMB_004 | Skill Match | 0.3556 | Yes | No | No | No |
| TC_EMB_005 | Skill Match | 0.6144 | Yes | No | No | Yes |
| TC_EMB_006 | Query Similarity | 0.6806 | Yes | Yes | No | Yes |
| TC_EMB_007 | Query Similarity | 0.6294 | Yes | No | No | Yes |
| TC_EMB_008 | Query Similarity | 0.1121 | No | No | No | No |
| TC_EMB_009 | Query Similarity | 0.7975 | Yes | Yes | Yes | Yes |
| TC_EMB_010 | Skill Match | 0.7251 | Yes | Yes | No | Yes |
| TC_EMB_011 | Skill Match | 0.8189 | Yes | Yes | Yes | Yes |
| TC_EMB_012 | Skill Match | 0.5426 | Yes | No | No | Yes |
| TC_EMB_013 | Skill Match | 0.6327 | Yes | No | No | Yes |
| TC_EMB_014 | Query Similarity | 0.7379 | Yes | Yes | No | Yes |
| TC_EMB_015 | Query Similarity | 0.5247 | Yes | No | No | Yes |
| TC_EMB_016 | Skill Match | 0.6259 | Yes | No | No | Yes |
| TC_EMB_017 | Skill Match | 0.3312 | Yes | No | No | No |
| TC_EMB_018 | Skill Match | 0.6272 | Yes | No | No | Yes |
| TC_EMB_019 | Query Similarity | 0.4750 | No | No | No | No |
| TC_EMB_020 | Skill Match | 0.5385 | Yes | No | No | Yes |

## Limitations

1. **Small dataset (n=20):** Statistical significance is limited. Results are indicative.
2. **Manually assigned labels:** Expected match labels were subjectively assigned, not independently validated.
3. **No held-out validation set:** Threshold selection (0.65, 0.78) is based on production usage, not cross-validation.
4. **Domain specificity:** Pairs are education/skill-domain specific; general STS benchmarks (e.g., STSbenchmark) may show different performance.
5. **No ranking evaluation:** The dataset does not support ranking metrics (Recall@K, NDCG) as there are no relevance hierarchies.

## Conclusion

The SBERT all-MiniLM-L6-v2 embedding service produces cosine similarity scores in the range
[0.1121, 0.8189] with mean 0.5778.
Positive pairs (expected semantic match) average 0.6220
while negative pairs average 0.3274, giving a separation of 0.2946.
At the production threshold of 0.78, the model achieves F1=0.2105.
At the evaluation threshold of 0.65, the model achieves F1=0.5217.
These metrics should be interpreted with caution due to the small dataset (n=20).
