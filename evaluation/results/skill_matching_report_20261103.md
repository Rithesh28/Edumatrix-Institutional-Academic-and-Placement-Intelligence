# Skill Matching Service Evaluation Report

**Model:** 3-Level Deterministic Skill Matching
**Threshold:** 0.78 (semantic similarity)
**Evaluation Date:** 2026-11-03

## Results

- **Total Cases:** 20
- **Correct Predictions:** 16
- **Accuracy:** 0.8000

### Match Type Distribution

- Exact: 14
- Synonym: 4
- Semantic: 1
- No Match: 1

## Per-Case Results

| Case ID | Student Skill | Job Skill | Expected | Actual | Method |
|---------|--------------|-----------|----------|--------|--------|
| TC_MATCH_001 | Python | python | exact | True | exact |
| TC_MATCH_002 | JavaScript | javascript | exact | True | exact |
| TC_MATCH_003 | Machine Learning | machine learning | exact | True | exact |
| TC_MATCH_004 | SQL | sql | exact | True | exact |
| TC_MATCH_005 | React | React.js | synonym | True | synonym |
| TC_MATCH_006 | Node.js | nodejs | synonym | True | synonym |
| TC_MATCH_007 | Deep Learning | deep learning | exact | True | exact |
| TC_MATCH_008 | AWS | aws | exact | True | exact |
| TC_MATCH_009 | Docker | docker | exact | True | exact |
| TC_MATCH_010 | Kubernetes | kubernetes | exact | True | exact |
| TC_MATCH_011 | REST API | rest api | exact | True | exact |
| TC_MATCH_012 | Git Version Control | git | synonym | False | none |
| TC_MATCH_013 | PostgreSQL | postgresql | exact | True | exact |
| TC_MATCH_014 | MongoDB | mongodb | exact | True | exact |
| TC_MATCH_015 | Natural Language Processing | nlp | semantic | True | synonym |
| TC_MATCH_016 | Computer Vision | computer vision | exact | True | exact |
| TC_MATCH_017 | Data Structures | data structures | exact | True | exact |
| TC_MATCH_018 | Object Oriented Programming | oop | semantic | True | synonym |
| TC_MATCH_019 | Agile Methodology | agile | exact | True | semantic |
| TC_MATCH_020 | Cloud Computing | cloud computing | exact | True | exact |
