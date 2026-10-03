"""Multi-label metrics, validation-only threshold choice and reviewable error examples."""
import numpy as np
from sklearn.metrics import (precision_recall_fscore_support, hamming_loss,
                             average_precision_score, f1_score, recall_score)
from backend.app.utils.psychology_labels import get_psychology_labels
from backend.app.config.psychology_config import THRESHOLD_GRID


def select_thresholds(actual: np.ndarray, probabilities: np.ndarray) -> tuple[dict, dict]:
    selected, comparison = {}, {}
    for index, label in enumerate(get_psychology_labels()):
        candidates = []
        for threshold in THRESHOLD_GRID:
            predicted = probabilities[:, index] >= threshold
            candidates.append({'threshold': threshold,
                'f1': float(f1_score(actual[:, index], predicted, zero_division=0)),
                'recall': float(recall_score(actual[:, index], predicted, zero_division=0))})
        best = max(candidates, key=lambda row: (row['f1'], row['recall'], -abs(row['threshold']-.5)))
        selected[label], comparison[label] = best['threshold'], candidates
    return selected, comparison


def multi_label_metrics(actual: np.ndarray, probabilities: np.ndarray, thresholds: dict) -> dict:
    labels = list(get_psychology_labels())
    cutoffs = np.array([thresholds[label] for label in labels])
    predicted = probabilities >= cutoffs
    per_p, per_r, per_f1, support = precision_recall_fscore_support(actual, predicted, average=None, zero_division=0)
    result = {'sample_count': len(actual), 'hamming_loss': float(hamming_loss(actual, predicted))}
    for average in ('micro', 'macro'):
        precision, recall, f1, _ = precision_recall_fscore_support(actual, predicted, average=average, zero_division=0)
        result[f'{average}_precision'] = float(precision)
        result[f'{average}_recall'] = float(recall)
        result[f'{average}_f1'] = float(f1)
    result['per_label'] = {label: {'precision': float(per_p[i]), 'recall': float(per_r[i]),
        'f1': float(per_f1[i]), 'average_precision': float(average_precision_score(actual[:, i], probabilities[:, i])),
        'support': int(support[i]), 'threshold': thresholds[label],
        'false_positives': int(((actual[:, i] == 0) & predicted[:, i]).sum()),
        'false_negatives': int(((actual[:, i] == 1) & ~predicted[:, i]).sum())}
        for i, label in enumerate(labels)}
    result['macro_average_precision'] = float(np.mean([row['average_precision'] for row in result['per_label'].values()]))
    return result


def review_errors(data, probabilities: np.ndarray, thresholds: dict, count: int = 25) -> dict:
    labels = list(get_psychology_labels())
    actual = data[labels].to_numpy(dtype=int)
    predicted = probabilities >= np.array([thresholds[label] for label in labels])
    examples = {}
    for name, mask in (('false_positives', (actual == 0) & predicted), ('false_negatives', (actual == 1) & ~predicted)):
        positions = np.where(mask.any(axis=1))[0]
        # Rank by number of errors and model confidence; one entry per message.
        positions = sorted(positions, key=lambda i: int(mask[i].sum()), reverse=True)[:count]
        examples[name] = [{'message_id': str(data.iloc[i].message_id), 'text': data.iloc[i].text,
            'true_labels': [label for j, label in enumerate(labels) if actual[i, j]],
            'predicted_labels': [label for j, label in enumerate(labels) if predicted[i, j]],
            'error_labels': [label for j, label in enumerate(labels) if mask[i, j]],
            'probabilities': {label: float(probabilities[i, j]) for j, label in enumerate(labels)}} for i in positions]
    return examples
