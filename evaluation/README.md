# EduMatrix ML Model Evaluation Framework

This directory contains a comprehensive evaluation framework for all ML models, NLP pipelines, and AI services used in the EduMatrix Institutional Academic and Placement Intelligence System.

## Structure

```
evaluation/
├── README.md                          # This file
├── model_inventory.csv                # Complete model inventory
├── dataset_inventory.csv              # Dataset and test data inventory
├── scripts/
│   ├── evaluate_intent_classifier.py  # Intent classification evaluation
│   ├── evaluate_table_recognition.py  # Table recognition evaluation
│   ├── evaluate_gliner.py             # GLiNER entity extraction evaluation
│   ├── evaluate_layoutlmv3.py         # LayoutLMv3 resume analysis evaluation
│   ├── evaluate_ocr.py                # OCR service evaluation
│   ├── evaluate_study_buddy.py        # Study Buddy (Ollama/Phi-4-mini) evaluation
│   ├── evaluate_ai_chat_analyzer.py   # AI Chat Analyzer evaluation
│   ├── evaluate_resume_analyzer.py    # Resume Analyzer evaluation
│   ├── evaluate_jd_parser.py          # JD Parser evaluation
│   └── run_all_evaluations.py         # Master evaluation runner
├── test_cases/
│   ├── intent_classification_cases.csv
│   ├── table_recognition_cases.csv
│   ├── gliner_entity_cases.csv
│   ├── layoutlmv3_resume_cases.csv
│   ├── ocr_cases.csv
│   ├── study_buddy_qa_cases.csv
│   ├── ai_chat_analyzer_cases.csv
│   ├── resume_analyzer_cases.csv
│   └── jd_parser_cases.csv
├── annotations/
│   ├── intent_labels.json
│   ├── table_annotations/
│   ├── gliner_entities.json
│   ├── resume_entities.json
│   └── study_buddy_ground_truth.json
├── results/
│   ├── intent_classification_metrics.json
│   ├── table_recognition_metrics.json
│   ├── gliner_metrics.json
│   ├── layoutlmv3_metrics.json
│   ├── ocr_metrics.json
│   ├── study_buddy_metrics.json
│   ├── ai_chat_analyzer_metrics.json
│   ├── resume_analyzer_metrics.json
│   └── jd_parser_metrics.json
├── graphs/
│   ├── intent_confusion_matrix.png
│   ├── intent_training_curves.png
│   ├── table_recognition_metrics.png
│   ├── gliner_entity_f1.png
│   ├── layoutlmv3_field_accuracy.png
│   ├── ocr_cer_wer.png
│   ├── study_buddy_latency.png
│   ├── ai_chat_precision_recall.png
│   ├── resume_analyzer_score_dist.png
│   └── jd_parser_field_extraction.png
├── reports/
│   ├── model_evaluation_report.md
│   ├── model_evaluation_report.pdf
│   └── executive_summary.md
└── logs/
    └── evaluation_logs.txt
```

## Models Evaluated

| Model | Type | Purpose | Status |
|-------|------|---------|--------|
| **Intent Classifier (SBERT + Logistic Regression)** | Text Classification | Student query intent routing (8 classes) | Trained & Deployed |
| **Sentiment Analyser (DistilBERT)** | Sentiment Analysis | Chat message sentiment (3 classes) | Fine-tuned & Deployed |
| **Table Recognition (Custom CNN+Transformer)** | Table Detection/Structure | Exam duty table parsing | Trained (3 epochs, debug) |
| **LayoutLMv3 (microsoft/layoutlmv3-base)** | Document Understanding | Resume entity verification | Pre-trained (Inference-only) |
| **GLiNER (urchade/gliner_base)** | Zero-shot NER | Placement JD entity extraction | Pre-trained (Inference-only) |
| **Ollama Phi-4-mini** | Generative LLM | Study Buddy academic Q&A | Inference-only (RAG) |
| **Qwen Instruct (Transformers)** | Generative LLM | AI Chat Analyzer institutional Q&A | Inference-only (Grounded) |
| **SBERT (all-MiniLM-L6-v2)** | Embeddings | Semantic search, RAG retrieval | Pre-trained (Inference-only) |
| **spaCy (en_core_web_sm)** | NLP Pipeline | Resume parsing, NER | Pre-trained (Inference-only) |
| **Tesseract OCR** | OCR Engine | Scanned document text extraction | Pre-trained (Inference-only) |
| **Resume Analyzer (Rule-based)** | Scoring Engine | ATS score calculation | Custom logic |

## Evaluation Status

| Model | Training Eval | Validation Eval | Test Eval | Inference Bench | Notes |
|-------|---------------|-----------------|-----------|-----------------|-------|
| Intent Classifier | ⚠️ Partial | ✅ Done | ❌ Needed | ✅ Done | Training logs available |
| Sentiment Analyser | ❌ Unknown | ❌ Unknown | ❌ Needed | ✅ Done | No training logs found |
| Table Recognition | ✅ Done (3 epochs) | ✅ Done | ❌ Needed | ✅ Done | Debug mode only |
| LayoutLMv3 | N/A (Pre-trained) | N/A | ❌ Needed | ⚠️ Partial | No fine-tuning evidence |
| GLiNER | N/A (Pre-trained) | N/A | ❌ Needed | ✅ Done | Zero-shot only |
| Phi-4-mini (Study Buddy) | N/A (Pre-trained) | N/A | ❌ Needed | ✅ Done | RAG mode only |
| Qwen (AI Chat) | N/A (Pre-trained) | N/A | ❌ Needed | ⚠️ Partial | Fallback to rules |
| SBERT Embeddings | N/A (Pre-trained) | N/A | N/A | ✅ Done | Dimension: 384 |
| spaCy NER | N/A (Pre-trained) | N/A | ❌ Needed | ✅ Done | Rule-enhanced |
| Tesseract OCR | N/A (Pre-trained) | N/A | ❌ Needed | ⚠️ Partial | Basic extraction |
| Resume Analyzer | N/A (Rule-based) | N/A | N/A | ✅ Done | Custom scoring |

## Quick Start

```bash
# Install evaluation dependencies
pip install -r ../backend/requirements.txt
pip install matplotlib seaborn scikit-learn pandas openpyxl

# Run all evaluations
cd evaluation/scripts
python run_all_evaluations.py

# Run individual evaluations
python evaluate_intent_classifier.py
python evaluate_table_recognition.py
# ... etc
```

## Scientific Integrity Notes

This evaluation follows strict academic standards:

1. **No fabricated metrics** - All reported numbers come from actual evaluation runs
2. **Proper train/val/test splits** - Where training exists (Intent, Table Recognition)
3. **Pre-trained models clearly labeled** - No claim of project-specific training
4. **Appropriate metrics per task** - Classification vs Generation vs Extraction
5. **Reproducible** - Fixed seeds, documented procedures
6. **Honest limitations** - Clearly marked where evaluation is incomplete

## Report Generation

After running evaluations, generate the final report:

```bash
python scripts/generate_report.py
```

This creates `reports/model_evaluation_report.md` and `.pdf` suitable for academic submission.

---

*Generated as part of EduMatrix Final Year Project - Model Evaluation Phase*