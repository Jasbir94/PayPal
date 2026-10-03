"""Imbalance-aware metrics and validation-only operating threshold selection."""
import numpy as np
from sklearn.metrics import (precision_score, recall_score, f1_score, roc_auc_score,
                             average_precision_score, confusion_matrix)


def evaluate_probabilities(labels, probabilities, threshold: float = .5) -> dict:
    predictions = np.asarray(probabilities) >= threshold
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[0, 1]).ravel()
    return {
        'threshold': float(threshold),
        'precision': float(precision_score(labels, predictions, zero_division=0)),
        'recall': float(recall_score(labels, predictions, zero_division=0)),
        'f1': float(f1_score(labels, predictions, zero_division=0)),
        'roc_auc': float(roc_auc_score(labels, probabilities)),
        'pr_auc_average_precision': float(average_precision_score(labels, probabilities)),
        'false_positive_rate': float(fp / (fp + tn)) if fp + tn else 0.0,
        'confusion_matrix': [[int(tn), int(fp)], [int(fn), int(tp)]],
        'positive_count': int(sum(labels)), 'sample_count': int(len(labels)),
        'always_legitimate_accuracy': float(1 - np.mean(labels)),
    }


def choose_threshold(labels, probabilities) -> float:
    """Prefer recall under a 10% validation FPR cap; do not inspect test labels."""
    candidates = [evaluate_probabilities(labels, probabilities, threshold)
                  for threshold in np.linspace(.05, .95, 91)]
    feasible = [result for result in candidates if result['false_positive_rate'] <= .1]
    best = max(feasible or candidates, key=lambda result: (result['recall'], result['f1'],
                                                          -result['false_positive_rate']))
    return best['threshold']
