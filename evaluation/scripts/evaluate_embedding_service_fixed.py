"""
Evaluate Embedding Service (SBERT all-MiniLM-L6-v2) - CORRECTED METHODOLOGY

This script fixes the following methodological issues in the original evaluation:
1. Drops meaningless "expected_similarity" comparison (manually assigned arbitrary values)
2. Uses proper classification metrics (precision/recall/F1) instead of fake accuracy
3. Separates skill pairs from query pairs
4. Reports raw cosine similarity distributions
5. Analyzes positive/negative pair separation
6. Documents dataset limitations transparently
"""

import csv
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def load_test_cases(csv_path: str) -> List[Dict[str, Any]]:
    """Load test cases from CSV. Preserves original file unchanged."""
    cases = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Validate required fields
            tid = row.get('test_case_id', '').strip()
            text1 = row.get('text1', '').strip()
            text2 = row.get('text2', '').strip()
            category = row.get('category', '').strip()
            expected_match_str = row.get('is_semantic_match', '').strip().lower()

            if not tid or not text1 or not text2:
                print(f"[SKIP] {tid}: Missing required fields")
                continue

            try:
                expected_match = expected_match_str == 'true'
            except Exception:
                expected_match = False

            cases.append({
                'test_case_id': tid,
                'text1': text1,
                'text2': text2,
                'category': category,
                'expected_match': expected_match,
            })
    return cases


def evaluate_embeddings(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluate embedding service with corrected methodology."""
    from app.services.embedding_service import embedding_service

    if not embedding_service.is_available():
        return {
            'error': 'Embedding service model not available',
            'model_name': embedding_service.model_name,
        }

    results = []
    for case in cases:
        sim = embedding_service.compute_similarity(case['text1'], case['text2'])
        if sim is None:
            sim = 0.0

        # Binary prediction at default threshold (same as production)
        pred_match = sim >= 0.65

        # Also compute at 0.78 (production skill matching threshold)
        pred_match_78 = sim >= 0.78

        # Also compute at 0.5 (midpoint)
        pred_match_50 = sim >= 0.50

        results.append({
            'test_case_id': case['test_case_id'],
            'text1': case['text1'],
            'text2': case['text2'],
            'category': case['category'],
            'expected_match': case['expected_match'],
            'cosine_similarity': round(sim, 4),
            'pred_match_065': pred_match,
            'pred_match_078': pred_match_78,
            'pred_match_050': pred_match_50,
        })

    return {'results': results, 'model_info': embedding_service.get_model_info()}


def compute_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute proper classification metrics at multiple thresholds."""
    thresholds = [0.50, 0.65, 0.78]
    all_metrics = {}

    for threshold in thresholds:
        tp = tn = fp = fn = 0
        for r in results:
            actual = r['expected_match']
            predicted = r['cosine_similarity'] >= threshold
            if actual and predicted:
                tp += 1
            elif actual and not predicted:
                fn += 1
            elif not actual and predicted:
                fp += 1
            else:
                tn += 1

        total = tp + tn + fp + fn
        accuracy = (tp + tn) / total if total > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        all_metrics[f'threshold_{threshold:.2f}'] = {
            'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
            'accuracy': round(accuracy, 4),
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1': round(f1, 4),
        }

    return all_metrics


def compute_descriptive_stats(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute distribution statistics for similarity scores."""
    import numpy as np

    all_sims = [r['cosine_similarity'] for r in results]
    pos_sims = [r['cosine_similarity'] for r in results if r['expected_match']]
    neg_sims = [r['cosine_similarity'] for r in results if not r['expected_match']]

    skill_results = [r for r in results if r['category'] == 'Skill Match']
    query_results = [r for r in results if r['category'] == 'Query Similarity']
    skill_pos = [r['cosine_similarity'] for r in skill_results if r['expected_match']]
    skill_neg = [r['cosine_similarity'] for r in skill_results if not r['expected_match']]
    query_pos = [r['cosine_similarity'] for r in query_results if r['expected_match']]
    query_neg = [r['cosine_similarity'] for r in query_results if not r['expected_match']]

    def stats(arr):
        if not arr:
            return {'mean': 0, 'std': 0, 'min': 0, 'max': 0, 'median': 0}
        return {
            'mean': round(float(np.mean(arr)), 4),
            'std': round(float(np.std(arr)), 4),
            'min': round(float(np.min(arr)), 4),
            'max': round(float(np.max(arr)), 4),
            'median': round(float(np.median(arr)), 4),
            'count': len(arr),
        }

    return {
        'all': stats(all_sims),
        'positive_pairs': stats(pos_sims),
        'negative_pairs': stats(neg_sims),
        'skill_positive': stats(skill_pos),
        'skill_negative': stats(skill_neg),
        'query_positive': stats(query_pos),
        'query_negative': stats(query_neg),
        'skill_total': len(skill_results),
        'query_total': len(query_results),
        'pos_count': len(pos_sims),
        'neg_count': len(neg_sims),
    }


def generate_skill_similarity_chart(results: List[Dict[str, Any]], out_dir: str):
    """Chart: skill similarity score distribution."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    skill_results = [r for r in results if r['category'] == 'Skill Match']
    pos_sims = [r['cosine_similarity'] for r in skill_results if r['expected_match']]
    neg_sims = [r['cosine_similarity'] for r in skill_results if not r['expected_match']]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Histogram
    ax0 = axes[0]
    bins = np.linspace(0, 1, 21)
    ax0.hist(pos_sims, bins=bins, alpha=0.7, label=f'Positive (n={len(pos_sims)})', color='green')
    ax0.hist(neg_sims, bins=bins, alpha=0.7, label=f'Negative (n={len(neg_sims)})', color='red')
    ax0.axvline(x=0.65, color='orange', linestyle='--', label='Threshold=0.65')
    ax0.axvline(x=0.78, color='purple', linestyle='--', label='Threshold=0.78')
    ax0.set_xlabel('Cosine Similarity')
    ax0.set_ylabel('Count')
    ax0.set_title('Skill Pairs: Similarity Score Distribution')
    ax0.legend(fontsize=9)

    # Box plot
    ax1 = axes[1]
    box_data = [pos_sims, neg_sims]
    bp = ax1.boxplot(box_data, tick_labels=['Positive\n(expected match)', 'Negative\n(expected no-match)'],
                     patch_artist=True)
    for patch, color in zip(bp['boxes'], ['lightgreen', 'lightcoral']):
        patch.set_facecolor(color)
    ax1.set_ylabel('Cosine Similarity')
    ax1.set_title('Skill Pairs: Positive vs Negative Distribution')

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'embedding_skill_similarity_distribution.png'), dpi=300)
    plt.close()
    print(f"  Generated: embedding_skill_similarity_distribution.png")


def generate_query_similarity_chart(results: List[Dict[str, Any]], out_dir: str):
    """Chart: query similarity score distribution."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    query_results = [r for r in results if r['category'] == 'Query Similarity']
    pos_sims = [r['cosine_similarity'] for r in query_results if r['expected_match']]
    neg_sims = [r['cosine_similarity'] for r in query_results if not r['expected_match']]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Histogram
    ax0 = axes[0]
    bins = np.linspace(0, 1, 21)
    ax0.hist(pos_sims, bins=bins, alpha=0.7, label=f'Positive (n={len(pos_sims)})', color='green')
    ax0.hist(neg_sims, bins=bins, alpha=0.7, label=f'Negative (n={len(neg_sims)})', color='red')
    ax0.axvline(x=0.65, color='orange', linestyle='--', label='Threshold=0.65')
    ax0.axvline(x=0.78, color='purple', linestyle='--', label='Threshold=0.78')
    ax0.set_xlabel('Cosine Similarity')
    ax0.set_ylabel('Count')
    ax0.set_title('Query Pairs: Similarity Score Distribution')
    ax0.legend(fontsize=9)

    # Box plot
    ax1 = axes[1]
    box_data = [pos_sims, neg_sims]
    bp = ax1.boxplot(box_data, tick_labels=['Positive\n(expected match)', 'Negative\n(expected no-match)'],
                     patch_artist=True)
    for patch, color in zip(bp['boxes'], ['lightgreen', 'lightcoral']):
        patch.set_facecolor(color)
    ax1.set_ylabel('Cosine Similarity')
    ax1.set_title('Query Pairs: Positive vs Negative Distribution')

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'embedding_query_similarity_distribution.png'), dpi=300)
    plt.close()
    print(f"  Generated: embedding_query_similarity_distribution.png")


def generate_comparison_chart(results: List[Dict[str, Any]], desc_stats: Dict, out_dir: str):
    """Chart: positive vs negative similarity comparison across categories."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=(10, 6))

    categories = ['Skill Positive', 'Skill Negative', 'Query Positive', 'Query Negative']
    means = [
        desc_stats['skill_positive']['mean'],
        desc_stats['skill_negative']['mean'],
        desc_stats['query_positive']['mean'],
        desc_stats['query_negative']['mean'],
    ]
    stds = [
        desc_stats['skill_positive']['std'],
        desc_stats['skill_negative']['std'],
        desc_stats['query_positive']['std'],
        desc_stats['query_negative']['std'],
    ]
    counts = [
        desc_stats['skill_positive']['count'],
        desc_stats['skill_negative']['count'],
        desc_stats['query_positive']['count'],
        desc_stats['query_negative']['count'],
    ]
    colors = ['darkgreen', 'darkred', 'forestgreen', 'darkred']

    bars = ax.bar(categories, means, yerr=stds, capsize=5, color=colors, alpha=0.8, edgecolor='black')
    ax.axhline(y=0.65, color='orange', linestyle='--', linewidth=2, label='Threshold 0.65')
    ax.axhline(y=0.78, color='purple', linestyle='--', linewidth=2, label='Threshold 0.78')
    ax.set_ylabel('Mean Cosine Similarity')
    ax.set_title('Embedding Service: Positive vs Negative Similarity by Category\n(n=' + str(len(results)) + ' total pairs)')
    ax.set_ylim(0, 1.0)
    ax.legend(fontsize=9)

    # Add value labels
    for bar, mean, count in zip(bars, means, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f'{mean:.3f}\nn={count}', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, 'embedding_positive_negative_comparison.png'), dpi=300)
    plt.close()
    print(f"  Generated: embedding_positive_negative_comparison.png")


def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    print("=" * 70)
    print("Evaluating Embedding Service (SBERT all-MiniLM-L6-v2) - CORRECTED")
    print("=" * 70)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    test_csv = os.path.join(base_dir, 'test_cases', 'embedding_service_cases.csv')
    results_dir = os.path.join(base_dir, 'results')
    graphs_dir = os.path.join(base_dir, 'graphs', 'all_models')
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(graphs_dir, exist_ok=True)

    if not os.path.exists(test_csv):
        print(f"[XX] Test cases file not found: {test_csv}")
        return

    cases = load_test_cases(test_csv)
    print(f"Loaded {len(cases)} test cases from {test_csv}")

    # Show dataset composition
    from collections import Counter
    cat_counts = Counter(c['category'] for c in cases)
    for cat, count in sorted(cat_counts.items()):
        print(f"  {cat}: {count} pairs")
    pos_count = sum(1 for c in cases if c['expected_match'])
    neg_count = len(cases) - pos_count
    print(f"  Positive (semantic match): {pos_count}, Negative: {neg_count}")
    print()

    print("Running embedding evaluations...")
    eval_result = evaluate_embeddings(cases)
    if 'error' in eval_result:
        print(f"[XX] {eval_result['error']}")
        return

    results = eval_result['results']
    model_info = eval_result['model_info']

    # Compute metrics at multiple thresholds
    classification_metrics = compute_metrics(results)

    # Compute descriptive statistics
    desc_stats = compute_descriptive_stats(results)

    # Print summary
    print(f"\nModel: {model_info.get('model_name', 'unknown')}")
    print(f"Embedding dimension: {model_info.get('dimension', 'unknown')}")
    print(f"Total pairs evaluated: {len(results)}")
    print()

    # Descriptive stats
    print("--- Similarity Score Distributions ---")
    print(f"  All pairs:    mean={desc_stats['all']['mean']:.4f}, std={desc_stats['all']['std']:.4f}, "
          f"range=[{desc_stats['all']['min']:.4f}, {desc_stats['all']['max']:.4f}]")
    print(f"  Positive:     mean={desc_stats['positive_pairs']['mean']:.4f}, std={desc_stats['positive_pairs']['std']:.4f}, "
          f"range=[{desc_stats['positive_pairs']['min']:.4f}, {desc_stats['positive_pairs']['max']:.4f}] (n={desc_stats['positive_pairs']['count']})")
    print(f"  Negative:     mean={desc_stats['negative_pairs']['mean']:.4f}, std={desc_stats['negative_pairs']['std']:.4f}, "
          f"range=[{desc_stats['negative_pairs']['min']:.4f}, {desc_stats['negative_pairs']['max']:.4f}] (n={desc_stats['negative_pairs']['count']})")
    sep = desc_stats['positive_pairs']['mean'] - desc_stats['negative_pairs']['mean']
    print(f"  Positive-Negative separation: {sep:.4f}")
    print()

    # Classification metrics
    print("--- Classification Metrics at Different Thresholds ---")
    for thresh, m in classification_metrics.items():
        print(f"  {thresh}: Accuracy={m['accuracy']:.4f}, Precision={m['precision']:.4f}, "
              f"Recall={m['recall']:.4f}, F1={m['f1']:.4f} (TP={m['tp']}, TN={m['tn']}, FP={m['fp']}, FN={m['fn']})")
    print()

    # Per-case detail
    print("--- Per-Case Results ---")
    print(f"{'ID':<12} {'Category':<18} {'Sim':>6} {'Pred@0.65':>10} {'Exp':>5} {'Match':>6} {'Pred@0.78':>10} {'Pred@0.50':>10}")
    print("-" * 95)
    for r in results:
        exp_str = "YES" if r['expected_match'] else " NO"
        pred_65 = "YES" if r['pred_match_065'] else " NO"
        pred_78 = "YES" if r['pred_match_078'] else " NO"
        pred_50 = "YES" if r['pred_match_050'] else " NO"
        print(f"{r['test_case_id']:<12} {r['category']:<18} {r['cosine_similarity']:>6.4f} "
              f"{pred_65:>10} {exp_str:>5} {'Y' if r['pred_match_065'] == r['expected_match'] else 'N':>6} "
              f"{pred_78:>10} {pred_50:>10}")
    print()

    # Generate graphs
    print("Generating graphs...")
    generate_skill_similarity_chart(results, graphs_dir)
    generate_query_similarity_chart(results, graphs_dir)
    generate_comparison_chart(results, desc_stats, graphs_dir)

    # Save JSON metrics
    output = {
        'model': model_info.get('model_name'),
        'embedding_dimension': model_info.get('dimension'),
        'evaluation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'methodology': 'Corrected - reports raw cosine similarity distributions; '
                       'classification metrics at multiple thresholds; no comparison to arbitrary expected values',
        'dataset': {
            'total_pairs': len(results),
            'skill_pairs': desc_stats['skill_total'],
            'query_pairs': desc_stats['query_total'],
            'positive_pairs': desc_stats['pos_count'],
            'negative_pairs': desc_stats['neg_count'],
            'note': 'Labels are manually assigned; dataset is small (n=20); results are indicative only',
        },
        'descriptive_statistics': desc_stats,
        'classification_metrics': classification_metrics,
        'results': results,
    }

    metrics_file = os.path.join(results_dir, f'embedding_metrics_fixed_{timestamp}.json')
    with open(metrics_file, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n[META] Metrics saved to: {metrics_file}")

    # Save CSV
    csv_file = os.path.join(results_dir, f'embedding_results_fixed_{timestamp}.csv')
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['test_case_id', 'category', 'text1', 'text2', 'cosine_similarity',
                         'expected_match', 'pred_match_050', 'pred_match_065', 'pred_match_078'])
        for r in results:
            writer.writerow([
                r['test_case_id'], r['category'], r['text1'], r['text2'],
                r['cosine_similarity'], r['expected_match'],
                r['pred_match_050'], r['pred_match_065'], r['pred_match_078']
            ])
    print(f"[META] Results CSV saved to: {csv_file}")

    # Save markdown report
    report_file = os.path.join(results_dir, f'embedding_report_fixed_{timestamp}.md')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# Embedding Service Evaluation Report (Corrected Methodology)\n\n")
        f.write(f"**Model:** {model_info.get('model_name')} (SBERT all-MiniLM-L6-v2)\n")
        f.write(f"**Embedding Dimension:** {model_info.get('dimension')}\n")
        f.write(f"**Evaluation Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("## Methodology\n\n")
        f.write("The original evaluation compared SBERT cosine similarity scores against manually-assigned\n")
        f.write("\"expected_similarity\" values (e.g., 0.85, 0.80) and computed a misleading \"accuracy\" of 45%.\n")
        f.write("This is scientifically invalid because:\n\n")
        f.write("1. Expected similarities were arbitrarily assigned, not independently established ground truth\n")
        f.write("2. The threshold (0.65) was hand-waved as \"reasonable\" with no validation\n")
        f.write("3. The 45% metric conflates label quality with model quality\n\n")
        f.write("**Corrected approach:** Report raw cosine similarity distributions, compute proper\n")
        f.write("classification metrics (precision/recall/F1) at multiple validated thresholds, separate\n")
        f.write("skill pairs from query pairs, and transparently document dataset limitations.\n\n")

        f.write("## Dataset\n\n")
        f.write(f"- **Total pairs:** {len(results)} ({desc_stats['skill_total']} skill + {desc_stats['query_total']} query)\n")
        f.write(f"- **Positive pairs (semantic match):** {desc_stats['pos_count']}\n")
        f.write(f"- **Negative pairs (no semantic match):** {desc_stats['neg_count']}\n")
        f.write(f"- **Limitation:** Small dataset (n=20); labels are manually assigned\n\n")

        f.write("## Descriptive Statistics\n\n")
        f.write("### All Pairs\n\n")
        f.write(f"- Mean cosine similarity: {desc_stats['all']['mean']:.4f}\n")
        f.write(f"- Std deviation: {desc_stats['all']['std']:.4f}\n")
        f.write(f"- Range: [{desc_stats['all']['min']:.4f}, {desc_stats['all']['max']:.4f}]\n\n")

        f.write("### Positive Pairs (Expected Match)\n\n")
        f.write(f"- Mean: {desc_stats['positive_pairs']['mean']:.4f}, Std: {desc_stats['positive_pairs']['std']:.4f}\n")
        f.write(f"- Range: [{desc_stats['positive_pairs']['min']:.4f}, {desc_stats['positive_pairs']['max']:.4f}]\n\n")

        f.write("### Negative Pairs (Expected No-Match)\n\n")
        f.write(f"- Mean: {desc_stats['negative_pairs']['mean']:.4f}, Std: {desc_stats['negative_pairs']['std']:.4f}\n")
        f.write(f"- Range: [{desc_stats['negative_pairs']['min']:.4f}, {desc_stats['negative_pairs']['max']:.4f}]\n\n")

        f.write(f"**Positive-Negative separation:** {sep:.4f}\n\n")

        f.write("### Skill Pairs\n\n")
        f.write(f"- Positive (n={desc_stats['skill_positive']['count']}): mean={desc_stats['skill_positive']['mean']:.4f}, std={desc_stats['skill_positive']['std']:.4f}\n")
        f.write(f"- Negative (n={desc_stats['skill_negative']['count']}): mean={desc_stats['skill_negative']['mean']:.4f}, std={desc_stats['skill_negative']['std']:.4f}\n\n")

        f.write("### Query Pairs\n\n")
        f.write(f"- Positive (n={desc_stats['query_positive']['count']}): mean={desc_stats['query_positive']['mean']:.4f}, std={desc_stats['query_positive']['std']:.4f}\n")
        f.write(f"- Negative (n={desc_stats['query_negative']['count']}): mean={desc_stats['query_negative']['mean']:.4f}, std={desc_stats['query_negative']['std']:.4f}\n\n")

        f.write("## Classification Metrics at Multiple Thresholds\n\n")
        f.write("| Threshold | Accuracy | Precision | Recall | F1 | TP | TN | FP | FN |\n")
        f.write("|-----------|----------|-----------|--------|-----|----|----|----|----|\n")
        for thresh, m in classification_metrics.items():
            f.write(f"| {thresh} | {m['accuracy']:.4f} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} | {m['tp']} | {m['tn']} | {m['fp']} | {m['fn']} |\n")
        f.write("\n")

        f.write("## Per-Case Results\n\n")
        f.write("| Case ID | Category | Cosine Sim | Expected | Pred@0.65 | Pred@0.78 | Pred@0.50 |\n")
        f.write("|---------|----------|------------|----------|-----------|-----------|-----------|\n")
        for r in results:
            f.write(f"| {r['test_case_id']} | {r['category']} | {r['cosine_similarity']:.4f} | ")
            f.write(f"{'Yes' if r['expected_match'] else 'No'} | ")
            f.write(f"{'Yes' if r['pred_match_065'] else 'No'} | ")
            f.write(f"{'Yes' if r['pred_match_078'] else 'No'} | ")
            f.write(f"{'Yes' if r['pred_match_050'] else 'No'} |\n")
        f.write("\n")

        f.write("## Limitations\n\n")
        f.write("1. **Small dataset (n=20):** Statistical significance is limited. Results are indicative.\n")
        f.write("2. **Manually assigned labels:** Expected match labels were subjectively assigned, not independently validated.\n")
        f.write("3. **No held-out validation set:** Threshold selection (0.65, 0.78) is based on production usage, not cross-validation.\n")
        f.write("4. **Domain specificity:** Pairs are education/skill-domain specific; general STS benchmarks (e.g., STSbenchmark) may show different performance.\n")
        f.write("5. **No ranking evaluation:** The dataset does not support ranking metrics (Recall@K, NDCG) as there are no relevance hierarchies.\n\n")

        f.write("## Conclusion\n\n")
        f.write(f"The SBERT all-MiniLM-L6-v2 embedding service produces cosine similarity scores in the range\n")
        f.write(f"[{desc_stats['all']['min']:.4f}, {desc_stats['all']['max']:.4f}] with mean {desc_stats['all']['mean']:.4f}.\n")
        f.write(f"Positive pairs (expected semantic match) average {desc_stats['positive_pairs']['mean']:.4f}\n")
        f.write(f"while negative pairs average {desc_stats['negative_pairs']['mean']:.4f}, giving a separation of {sep:.4f}.\n")
        f.write(f"At the production threshold of 0.78, the model achieves F1={classification_metrics['threshold_0.78']['f1']:.4f}.\n")
        f.write(f"At the evaluation threshold of 0.65, the model achieves F1={classification_metrics['threshold_0.65']['f1']:.4f}.\n")
        f.write(f"These metrics should be interpreted with caution due to the small dataset (n=20).\n")

    print(f"[META] Report saved to: {report_file}")
    print("[OK] Evaluation complete (corrected methodology)")


if __name__ == '__main__':
    main()
