"""Generate Phase 9 summary visualization."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os

results_dir = r'D:\Edumatrix-Institutional-Academic-and-Placement-Intelligence\evaluation\graphs'
os.makedirs(results_dir, exist_ok=True)

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('AI Chat Analyzer — Phase 9 Final Evaluation Summary', fontsize=16, fontweight='bold')

# --- Chart 1: Accuracy Comparison (Phase 7 vs Phase 8 vs Independent) ---
ax1 = axes[0, 0]
categories = ['Sentiment\nAccuracy', 'Intent\nAccuracy']
phase7_vals = [81.82, 76.36]
phase8_vals = [96.36, 76.36]
independent_vals = [91.67, 66.67]

x = np.arange(len(categories))
width = 0.25
bars1 = ax1.bar(x - width, phase7_vals, width, label='Phase 7 (DistilBERT)', color='#94a3b8')
bars2 = ax1.bar(x, phase8_vals, width, label='Phase 8 (SBERT+LR)', color='#10b981')
bars3 = ax1.bar(x + width, independent_vals, width, label='Phase 9 (60 unseen)', color='#f59e0b')

ax1.set_ylabel('Accuracy (%)')
ax1.set_title('Sentiment & Intent Accuracy Comparison')
ax1.set_xticks(x)
ax1.set_xticklabels(categories)
ax1.legend(loc='lower right')
ax1.set_ylim(0, 105)
ax1.axhline(y=80, color='red', linestyle='--', alpha=0.5, label='80% threshold')

for bar in bars1:
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
             f'{bar.get_height():.1f}%', ha='center', va='bottom', fontsize=9)
for bar in bars2:
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
             f'{bar.get_height():.1f}%', ha='center', va='bottom', fontsize=9)
for bar in bars3:
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
             f'{bar.get_height():.1f}%', ha='center', va='bottom', fontsize=9)

# --- Chart 2: Confusion Matrix ---
ax2 = axes[0, 1]
confusion_matrix = [
    [5, 0, 0],
    [0, 46, 2],
    [0, 0, 2]
]
labels = ['negative', 'neutral', 'positive']
im = ax2.imshow(confusion_matrix, cmap='RdYlGn', aspect='auto', vmin=0, vmax=5)
ax2.set_xticks(range(3))
ax2.set_yticks(range(3))
ax2.set_xticklabels(labels, rotation=45, ha='right')
ax2.set_yticklabels(labels)
ax2.set_title('Phase 8 Sentiment Confusion Matrix\n(55 test cases)')
ax2.set_xlabel('Predicted')
ax2.set_ylabel('Actual')

for i in range(3):
    for j in range(3):
        text = ax2.text(j, i, str(confusion_matrix[i][j]),
                       ha='center', va='center', color='black', fontsize=14, fontweight='bold')

plt.colorbar(im, ax=ax2, shrink=0.8)

# --- Chart 3: Inference Performance ---
ax3 = axes[1, 0]
models = ['Phase 7\n(DistilBERT)', 'Phase 8\n(SBERT+LR)']
intent_times = [156.0, 20.2]
sentiment_times = [156.0, 22.7]

x3 = np.arange(len(models))
width3 = 0.35
bars_i = ax3.bar(x3 - width3/2, intent_times, width3, label='Intent', color='#6366f1')
bars_s = ax3.bar(x3 + width3/2, sentiment_times, width3, label='Sentiment', color='#ec4899')

ax3.set_ylabel('Mean Inference Time (ms)')
ax3.set_title('Inference Performance Comparison')
ax3.set_xticks(x3)
ax3.set_xticklabels(models)
ax3.legend()

for bar in bars_i:
    ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
             f'{bar.get_height():.1f}ms', ha='center', va='bottom', fontsize=9)
for bar in bars_s:
    ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
             f'{bar.get_height():.1f}ms', ha='center', va='bottom', fontsize=9)

# --- Chart 4: Key Metrics Summary ---
ax4 = axes[1, 1]
ax4.axis('off')

summary_data = [
    ['METRIC', 'PHASE 7', 'PHASE 8', 'IMPROVEMENT'],
    ['Sentiment Accuracy', '81.82%', '96.36%', '+14.54pp'],
    ['Sentiment Macro F1', '67.22%', '88.18%', '+20.96pp'],
    ['Neutral Recall', '79.17%', '95.83%', '+16.66pp'],
    ['Intent Accuracy', '76.36%', '76.36%', '0.00pp'],
    ['Inference Time', '156ms', '44ms', '-71%'],
    ['Errors (55 cases)', '10/55 (18.2%)', '2/55 (3.6%)', '-80%'],
    ['Independent Acc.', '—', '—', 'Senti: 91.67%'],
]

table = ax4.table(cellText=summary_data[1:], colLabels=summary_data[0],
                  cellLoc='center', loc='center',
                  colWidths=[0.25, 0.2, 0.2, 0.2])
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1, 2)

# Style header
for i in range(4):
    table[(0, i)].set_facecolor('#10b981')
    table[(0, i)].set_text_props(color='white', fontweight='bold')

# Color code improvement column
for i in range(1, len(summary_data)):
    cell = table[(i, 3)]
    val = summary_data[i][3]
    if val.startswith('+'):
        cell.set_facecolor('#d1fae5')
    elif val.startswith('-'):
        cell.set_facecolor('#dbeafe')
    elif val.startswith('Senti:'):
        cell.set_facecolor('#fef3c7')
    else:
        cell.set_facecolor('#f1f5f9')

ax4.set_title('Phase 7 → Phase 8 Performance Summary', pad=20)

plt.tight_layout()
output_path = os.path.join(results_dir, 'ai_chat_analyzer_phase9_final_summary.png')
plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f'Visualization saved to: {output_path}')
