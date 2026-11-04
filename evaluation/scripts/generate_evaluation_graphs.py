"""
Phase 6 AI Chat Analyzer - Evaluation Visualization
Generates professional graphs from evaluation metrics using matplotlib.
"""
import json
import os
import glob
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Color palette (EduMatrix brand colors)
COLORS = {
    'intent': '#6366f1',       # indigo
    'sentiment': '#8b5cf6',    # violet
    'background': '#0f172a',   # dark slate
    'grid': '#334155',         # slate-700
    'text': '#f8fafc',         # slate-50
    'muted': '#94a3b8',        # slate-400
    'green': '#22c55e',
    'red': '#ef4444',
    'blue': '#3b82f6',
    'yellow': '#eab308',
}

def load_latest_metrics():
    """Load latest v2 evaluation metrics from results file (preferred)
    or metrics file as fallback."""
    results_dir = os.path.join(os.path.dirname(__file__), '..', 'results')

    # Prefer results_v2 (has full per-case details + confidence)
    pattern_results = os.path.join(results_dir, 'ai_chat_analyzer_results_v2_*.json')
    files_results = sorted(glob.glob(pattern_results), key=os.path.getmtime, reverse=True)

    if files_results:
        try:
            with open(files_results[0], 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load results: {e}")

    # Fallback to metrics_v2
    pattern_metrics = os.path.join(results_dir, 'ai_chat_analyzer_metrics_v2_*.json')
    files_metrics = sorted(glob.glob(pattern_metrics), key=os.path.getmtime, reverse=True)
    if not files_metrics:
        print("ERROR: No evaluation metrics found")
        return None
    with open(files_metrics[0], 'r') as f:
        return json.load(f)


def plot_accuracy_comparison(metrics, output_path):
    """Intent vs Sentiment Accuracy bar chart."""
    fig, ax = plt.subplots(figsize=(8, 5), facecolor=COLORS['background'])
    ax.set_facecolor(COLORS['background'])

    categories = ['Accuracy']
    intent_values = [metrics['intent_accuracy'] * 100]
    sentiment_values = [metrics['sentiment_accuracy'] * 100]

    x = np.arange(len(categories))
    width = 0.35

    bars1 = ax.bar(x - width/2, intent_values, width, label='Intent',
                   color=COLORS['intent'], edgecolor='white', alpha=0.9)
    bars2 = ax.bar(x + width/2, sentiment_values, width, label='Sentiment',
                   color=COLORS['sentiment'], edgecolor='white', alpha=0.9)

    # Add value labels on bars
    for bar in bars1:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'{bar.get_height():.0f}%', ha='center', va='bottom',
                fontsize=12, fontweight='bold', color=COLORS['text'])
    for bar in bars2:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'{bar.get_height():.0f}%', ha='center', va='bottom',
                fontsize=12, fontweight='bold', color=COLORS['text'])

    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=12, color=COLORS['text'])
    ax.set_ylabel('Accuracy (%)', fontsize=11, color=COLORS['text'])
    ax.set_title('Intent vs Sentiment Accuracy', fontsize=14, fontweight='bold', color=COLORS['text'])
    ax.legend(facecolor='#1e293b', edgecolor='#334155', fontsize=11,
              labelcolor=COLORS['text'])
    ax.set_ylim(0, 110)
    ax.yaxis.set_major_locator(plt.MaxNLocator(6))
    ax.grid(axis='y', linestyle='--', alpha=0.3, color=COLORS['grid'])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=COLORS['background'])
    plt.close()
    print(f"Saved: {output_path}")


def plot_f1_comparison(metrics, output_path):
    """Intent vs Sentiment F1 Score comparison."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), facecolor=COLORS['background'])

    for idx, (ax, label, data_key) in enumerate([
        (axes[0], 'Macro F1', 'macro_f1'),
        (axes[1], 'Weighted F1', 'weighted_f1')
    ]):
        ax.set_facecolor(COLORS['background'])
        categories = ['Intent', 'Sentiment']
        values = [metrics[f'intent_{data_key}'] * 100,
                  metrics[f'sentiment_{data_key}'] * 100]

        bars = ax.barh(categories, values, color=[COLORS['intent'], COLORS['sentiment']],
                       edgecolor='white', alpha=0.9)

        for bar, val in zip(bars, values):
            ax.text(val + 1, bar.get_y() + bar.get_height()/2,
                    f'{val:.1f}%', va='center', fontsize=11, fontweight='bold',
                    color=COLORS['text'])

        ax.set_xlim(0, max(values) * 1.15)
        ax.set_title(label, fontsize=12, fontweight='bold', color=COLORS['text'])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.tick_params(colors=COLORS['text'])

    fig.suptitle('Intent vs Sentiment F1 Scores', fontsize=14, fontweight='bold',
                 color=COLORS['text'], y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=COLORS['background'])
    plt.close()
    print(f"Saved: {output_path}")


def plot_all_metrics_radar(metrics, output_path):
    """Radar/spider chart showing all key metrics."""
    categories = ['Intent Acc', 'Sent Acc', 'Intent F1', 'Sent F1', 'Intent Conf', 'Sent Conf']
    values = [
        metrics['intent_accuracy'] * 100,
        metrics['sentiment_accuracy'] * 100,
        metrics['intent_macro_f1'] * 100,
        metrics['sentiment_macro_f1'] * 100,
        metrics['intent_avg_confidence'] * 100,
        metrics['sentiment_avg_confidence'] * 100,
    ]

    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    values += values[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True),
                           facecolor=COLORS['background'])
    ax.set_facecolor(COLORS['background'])

    ax.plot(angles, values, 'o-', linewidth=2, color=COLORS['intent'],
            markerfacecolor=COLORS['sentiment'], markersize=8)
    ax.fill(angles, values, alpha=0.25, color=COLORS['intent'])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=11, color=COLORS['text'])
    ax.set_title('AI Chat Analyzer Performance Profile', fontsize=14,
                 fontweight='bold', color=COLORS['text'], pad=20)
    ax.set_ylim(0, 110)

    # Add grid
    ax.yaxis.grid(True, color=COLORS['grid'], linestyle='--', alpha=0.5)
    ax.spines['polar'].set_color(COLORS['grid'])

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=COLORS['background'])
    plt.close()
    print(f"Saved: {output_path}")


def plot_summary_dashboard(metrics, output_path):
    """Combined evaluation summary with all major metrics."""
    fig = plt.figure(figsize=(14, 10), facecolor='#0f172a')

    # Title
    fig.suptitle('AI Chat Analyzer — Evaluation Summary (Phase 6)',
                 fontsize=16, fontweight='bold', color='#f8fafc', y=0.98)

    gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)

    # --- Top Left: Accuracy Comparison ---
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor('#0f172a')
    cats = ['Accuracy']
    vals = [metrics['intent_accuracy']*100, metrics['sentiment_accuracy']*100]
    cols = [COLORS['intent'], COLORS['sentiment']]
    labels = ['Intent', 'Sentiment']
    bars = ax1.barh(cats, vals, color=cols, edgecolor='white', alpha=0.85)
    for bar, val, label in zip(bars, vals, labels):
        ax1.text(val + 1.5, bar.get_y() + bar.get_height()/2,
                 f'{label}: {val:.0f}%', va='center', fontsize=11,
                 fontweight='bold', color='#f8fafc')
    ax1.set_xlim(0, 110)
    ax1.set_title('Model Accuracy', fontsize=11, fontweight='bold', color='#f8fafc')
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.tick_params(colors='#94a3b8')

    # --- Top Right: F1 Scores ---
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_facecolor('#0f172a')
    f1_cats = ['Macro F1', 'Weighted F1']
    intent_f1 = [metrics['intent_macro_f1']*100, metrics['intent_weighted_f1']*100]
    sentiment_f1 = [metrics['sentiment_macro_f1']*100, metrics['sentiment_weighted_f1']*100]
    x = np.arange(len(f1_cats))
    w = 0.35
    ax2.bar(x - w/2, intent_f1, w, label='Intent', color=COLORS['intent'], alpha=0.85)
    ax2.bar(x + w/2, sentiment_f1, w, label='Sentiment', color=COLORS['sentiment'], alpha=0.85)
    for bars, values in [(ax2.containers[0], intent_f1), (ax2.containers[1], sentiment_f1)]:
        for bar, val in zip(bars, values):
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                     f'{val:.1f}%', ha='center', fontsize=10, fontweight='bold', color='#f8fafc')
    ax2.set_xticks(x)
    ax2.set_xticklabels(f1_cats, color='#94a3b8')
    ax2.set_title('F1 Scores', fontsize=11, fontweight='bold', color='#f8fafc')
    ax2.legend(facecolor='#1e293b', edgecolor='#334155', labelcolor='#f8fafc', fontsize=9)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.tick_params(colors='#94a3b8')
    ax2.yaxis.set_major_locator(plt.MaxNLocator(5))

    # --- Bottom Left: Confidence Levels ---
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.set_facecolor('#0f172a')
    conf_cats = ['Avg Confidence']
    intent_conf = [metrics['intent_avg_confidence']*100]
    sentiment_conf = [metrics['sentiment_avg_confidence']*100]
    bars3 = ax3.bar(conf_cats, intent_conf, width=0.4, label='Intent',
                    color=COLORS['intent'], alpha=0.85)
    bars4 = ax3.bar(conf_cats, sentiment_conf, width=0.4, label='Sentiment',
                    color=COLORS['sentiment'], alpha=0.85, bottom=intent_conf)
    total_h = intent_conf[0] + sentiment_conf[0]
    ax3.text(0, total_h + 2, f'Intent: {intent_conf[0]:.1f}%\nSentiment: {sentiment_conf[0]:.1f}%',
             ha='center', fontsize=10, color='#f8fafc', fontweight='bold')
    ax3.set_title('Classification Confidence', fontsize=11, fontweight='bold', color='#f8fafc')
    ax3.spines['top'].set_visible(False)
    ax3.spines['right'].set_visible(False)
    ax3.tick_params(colors='#94a3b8')
    ax3.set_ylim(0, 140)
    ax3.legend(facecolor='#1e293b', edgecolor='#334155', labelcolor='#f8fafc', fontsize=9)

    # --- Bottom Right: Test Coverage ---
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.set_facecolor('#0f172a')
    eval_total = metrics['total_cases']
    eval_passed = sum(1 for r in metrics.get('per_case_results', []) if r['intent_correct'] and r['sentiment_correct'])
    eval_failed = eval_total - eval_passed

    colors_pie = ['#22c55e', '#ef4444']
    wedges, texts, autotexts = ax4.pie([eval_passed, eval_failed],
                                        labels=[f'PASS ({eval_passed})', f'FAIL ({eval_failed})'],
                                        colors=colors_pie, autopct='%1.0f%%',
                                        startangle=90, textprops={'color': '#f8fafc', 'fontsize': 11})
    for at in autotexts:
        at.set_fontweight('bold')
        at.set_fontsize(13)
    ax4.set_title(f'Test Case Results ({eval_total} cases)', fontsize=11, fontweight='bold', color='#f8fafc')

    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='#0f172a')
    plt.close()
    print(f"Saved: {output_path}")


def main():
    print("=" * 60)
    print("Generating Evaluation Visualizations")
    print("=" * 60)

    metrics = load_latest_metrics()
    if not metrics:
        return 1

    output_dir = os.path.join(os.path.dirname(__file__), '..', 'graphs')
    os.makedirs(output_dir, exist_ok=True)

    # Load from results file to get the filename for display
    results_dir = os.path.join(os.path.dirname(__file__), '..', 'results')
    pattern_results = os.path.join(results_dir, 'ai_chat_analyzer_results_v2_*.json')
    files_results = sorted(glob.glob(pattern_results), key=os.path.getmtime, reverse=True)
    print(f"\nLoaded metrics from: {os.path.basename(files_results[0]) if files_results else 'metrics file'}")
    print(f"\nMetrics loaded:")
    print(f"  Intent Accuracy:     {metrics['intent_accuracy']*100:.1f}%")
    print(f"  Sentiment Accuracy:  {metrics['sentiment_accuracy']*100:.1f}%")
    print(f"  Intent Macro F1:     {metrics['intent_macro_f1']*100:.1f}%")
    print(f"  Sentiment Macro F1:  {metrics['sentiment_macro_f1']*100:.1f}%")
    print(f"  Total Cases:         {metrics['total_cases']}")
    print()

    # Generate individual charts
    plot_accuracy_comparison(metrics, os.path.join(output_dir, 'ai_chat_analyzer_accuracy.png'))
    plot_f1_comparison(metrics, os.path.join(output_dir, 'ai_chat_analyzer_macro_f1.png'))
    plot_all_metrics_radar(metrics, os.path.join(output_dir, 'ai_chat_analyzer_weighted_f1.png'))

    # Generate combined dashboard
    plot_summary_dashboard(metrics, os.path.join(output_dir, 'ai_chat_analyzer_evaluation_summary.png'))

    print("\nAll visualizations generated successfully!")
    print(f"Output directory: {output_dir}")


if __name__ == '__main__':
    main()
