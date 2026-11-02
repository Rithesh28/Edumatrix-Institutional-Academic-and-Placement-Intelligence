# ML Model Evaluation Framework

**Project:** EduMatrix - Institutional Academic and Placement Intelligence  
**Version:** 1.0  
**Date:** 2026-11-02

---

## Overview

This framework provides scientifically rigorous evaluation of all ML/NLP models in the EduMatrix platform. It follows academic standards with proper train/val/test separation, honest reporting of limitations, and reproducible evaluation pipelines.

## Directory Structure

```
evaluation/
├── model_inventory.csv          # Complete model catalog (14 models)
├── dataset_inventory.csv        # Dataset provenance (15 datasets)
├── test_cases/                  # Evaluation test cases (95+ cases)
│   ├── intent_classification_cases.csv
│   ├── sentiment_analysis_cases.csv
│   ├── gliner_extraction_cases.csv
│   ├── resume_parser_cases.csv
│   ├── jd_parser_cases.csv
│   ├── study_buddy_cases.csv
│   └── ai_chat_analyzer_cases.csv
├── scripts/                     # Evaluation scripts
│   ├── evaluate_intent_classifier.py
│   ├── evaluate_sentiment.py
│   ├── evaluate_gliner.py
│   ├── evaluate_resume_parser.py
│   ├── evaluate_jd_parser.py
│   ├── evaluate_study_buddy.py
│   ├── evaluate_ai_chat_analyzer.py
│   ├── evaluate_table_recognition.py
│   └── run_all_evaluations.py
├── annotations/                 # Manual ground truth annotations
├── results/                     # Evaluation outputs
│   ├── evaluation_summary.json
│   └── [model]_results_*.csv
├── graphs/                      # Publication-quality visualizations
│   ├── intent_confusion_matrix.png
│   └── ...
├── reports/                     # Final compiled reports
│   └── model_evaluation_report.md
└── logs/                        # Execution logs
```

## Models Evaluated

### Project-Trained Models

| Model | Architecture | Training Samples | Status |
|-------|--------------|------------------|--------|
| Intent Classifier | SBERT + LR | 80 (64 train / 16 val) | ✅ Tested |
| Sentiment Analyser | DistilBERT | Unknown (checkpoint) | ✅ Tested |
| Table Recognition | CNN+Transformer | 100 debug | ⚠️ Limited |

### Pre-trained Inference Models

| Model | Purpose | Fine-tuned |
|-------|---------|------------|
| LayoutLMv3 | Resume verification | No |
| GLiNER | Zero-shot NER | No |
| Phi-4-mini (Ollama) | RAG Q&A | No |
| Qwen Instruct | Institutional chat | No |
| SBERT embeddings | Vector search | No |
| spaCy NER | Resume parsing | No |
| Tesseract OCR | Text extraction | No |

## Quick Start

### Run All Evaluations
```bash
cd evaluation/scripts
python run_all_evaluations.py
```

### Run Individual Model
```bash
python evaluate_intent_classifier.py
python evaluate_sentiment.py
python evaluate_gliner.py
```

### View Results
```bash
# Metrics
cat results/intent_classification_metrics_*.json

# Reports
cat reports/model_evaluation_report.md

# Graphs
open graphs/intent_confusion_matrix.png
```

## Key Results

### Intent Classifier (SBERT + LR)
- **Accuracy:** 75.00%
- **Macro F1:** 0.7833
- **Best Class:** career_advice (F1=1.0)
- **Weakest Class:** ask_doubt (F1=0.46)
- **Test Cases:** 40

### Sentiment Analyser (DistilBERT)
- **Accuracy:** 80.00%
- **Macro F1:** 0.7824
- **Mean Confidence:** 0.836
- **Test Cases:** 30

### Resume Parser
- **Field Match:** 100%
- **Test Cases:** 5
- **Status:** Perfect on structured inputs

### JD Parser
- **Field Match:** 86.7%
- **Test Cases:** 10
- **Status:** Consistent across all cases

## Scientific Integrity

### Rules Applied
1. ✅ No data leakage in splits
2. ✅ Fixed random seeds (42)
3. ✅ Clear pre-trained vs fine-tuned distinction
4. ✅ Honest limitation reporting
5. ✅ Reproducible pipelines
6. ✅ No fabricated metrics

### Limitations
- Small training data for intent classifier (80 samples)
- Table recognition in debug mode only
- Some test cases have subjective ground truth
- RAG evaluations are structural (need live models)

## Citations

For thesis/report citations:
```bibtex
@misc{edumatrix_eval2026,
  title={ML Model Evaluation Framework for EduMatrix},
  author={Project Team},
  year={2026},
  url={evaluation/}
}
```

---

**Total Test Cases:** 95  
**Graphs Generated:** 5  
**Reports Generated:** 8  
**Framework Status:** Production Ready