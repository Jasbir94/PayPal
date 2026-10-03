"""Multiclass metrics, per-language diagnostics and commonly confused narratives."""
import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
from backend.app.utils.scenario_labels import get_scenario_labels


def classification_metrics(actual, predicted) -> dict:
    labels = list(get_scenario_labels())
    precision, recall, f1, support = precision_recall_fscore_support(actual, predicted, labels=labels, zero_division=0)
    matrix = confusion_matrix(actual, predicted, labels=labels)
    confusions = [{'actual': labels[i], 'predicted': labels[j], 'count': int(matrix[i, j])}
                  for i in range(len(labels)) for j in range(len(labels)) if i != j and matrix[i, j] > 0]
    confusions.sort(key=lambda item: item['count'], reverse=True)
    return {'accuracy': float(accuracy_score(actual, predicted)),
            'macro_precision': float(np.mean(precision)), 'macro_recall': float(np.mean(recall)),
            'macro_f1': float(np.mean(f1)), 'sample_count': len(actual),
            'per_class': {label: {'precision': float(precision[i]), 'recall': float(recall[i]),
                                 'f1': float(f1[i]), 'support': int(support[i])} for i, label in enumerate(labels)},
            'confusion_matrix_labels': labels, 'confusion_matrix': matrix.tolist(),
            'most_common_confusions': confusions[:12]}


def evaluate_pipeline(model, data) -> dict:
    predictions = model.predict(data.text)
    result = classification_metrics(data.scenario_label, predictions)
    result['by_language'] = {}
    for language in data.language.unique():
        mask = data.language.eq(language).to_numpy()
        result['by_language'][language] = classification_metrics(data.scenario_label[mask], predictions[mask])
    return result
