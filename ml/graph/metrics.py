"""Rare-positive binary metrics and validation-only decision thresholds."""
import numpy as np
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score, average_precision_score, confusion_matrix

def binary_metrics(actual, probabilities, threshold):
    actual = np.asarray(actual, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    prediction = probabilities >= threshold
    matrix = confusion_matrix(actual, prediction, labels=[0, 1])
    tn, fp, fn, tp = matrix.ravel()
    return {'samples': len(actual), 'positive_count': int(actual.sum()), 'threshold': float(threshold),
        'precision': float(precision_score(actual, prediction, zero_division=0)),
        'recall': float(recall_score(actual, prediction, zero_division=0)),
        'f1': float(f1_score(actual, prediction, zero_division=0)),
        'roc_auc': float(roc_auc_score(actual, probabilities)) if len(np.unique(actual)) == 2 else None,
        'pr_auc_average_precision': float(average_precision_score(actual, probabilities)) if actual.sum() else None,
        'false_positive_rate': float(fp / (fp + tn)) if fp + tn else 0.0,
        'confusion_matrix': matrix.tolist(), 'confusion_matrix_order': ['negative', 'positive']}

def validation_threshold(actual, probabilities):
    comparisons = [binary_metrics(actual, probabilities, value) for value in (.2, .3, .4, .5, .6, .7, .8)]
    best = max(comparisons, key=lambda item: (item['f1'], item['recall'], -item['false_positive_rate'], -abs(item['threshold'] - .5)))
    return best['threshold'], comparisons
