#!/usr/bin/env python3
"""
ML Evaluation Orchestrator
Runs all model evaluation scripts and compiles results.
"""

import sys
import os
import json
import subprocess
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))


def run_script(script_path, name):
    """Run an evaluation script and return result."""
    print(f"\n{'='*60}")
    print(f"RUNNING: {name}")
    print(f"{'='*60}")

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=300
        )
        print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
        if result.stderr:
            print(f"STDERR: {result.stderr[-300:]}")
        return {'status': 'SUCCESS', 'returncode': result.returncode}
    except subprocess.TimeoutExpired:
        return {'status': 'TIMEOUT', 'returncode': -1}
    except Exception as e:
        return {'status': 'ERROR', 'error': str(e), 'returncode': -1}


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    results_dir = os.path.join(base_dir, 'results')
    summary_path = os.path.join(results_dir, 'evaluation_summary.json')

    os.makedirs(results_dir, exist_ok=True)

    scripts = [
        ('evaluate_intent_classifier.py', 'Intent Classifier (SBERT+LR)'),
        ('evaluate_sentiment.py', 'Sentiment Analyser (DistilBERT)'),
        ('evaluate_gliner.py', 'GLiNER Entity Extraction'),
        ('evaluate_resume_parser.py', 'Resume Parser'),
        ('evaluate_jd_parser.py', 'JD Parser'),
        ('evaluate_study_buddy.py', 'Study Buddy RAG (Phi-4-mini)'),
        ('evaluate_ai_chat_analyzer.py', 'AI Chat Analyzer (Qwen)'),
        ('evaluate_table_recognition.py', 'Table Recognition (CNN+Transformer)'),
    ]

    all_results = {}
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    for script, name in scripts:
        script_path = os.path.join(base_dir, 'scripts', script)
        if os.path.exists(script_path):
            result = run_script(script_path, name)
            all_results[name] = result
        else:
            all_results[name] = {'status': 'MISSING', 'error': f'Script not found: {script}'}

    # Save summary
    summary = {
        'timestamp': timestamp,
        'evaluations': all_results,
        'completed': sum(1 for r in all_results.values() if r.get('status') == 'SUCCESS'),
        'failed': sum(1 for r in all_results.values() if r.get('status') in ['ERROR', 'TIMEOUT']),
        'missing': sum(1 for r in all_results.values() if r.get('status') == 'MISSING'),
    }

    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*60}")
    print("ALL EVALUATIONS COMPLETE")
    print(f"{'='*60}")
    print(f"Completed: {summary['completed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Missing: {summary['missing']}")
    print(f"\nSummary saved to: {summary_path}")


if __name__ == '__main__':
    main()