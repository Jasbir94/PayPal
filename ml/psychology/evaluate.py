"""Print all per-label metrics and export 25 FP/FN messages for review when available."""
import json
import pandas as pd
from backend.app.models.psychology_model import PsychologyModel
from backend.app.utils.psychology_labels import get_psychology_labels
from backend.app.config.psychology_config import PSYCHOLOGY_DATA_PATH, PSYCHOLOGY_REPORT_DIR
from ml.psychology.data_quality import validate_psychology_data
from ml.psychology.metrics import multi_label_metrics, review_errors


def evaluate() -> dict:
    model = PsychologyModel()
    data = pd.read_csv(PSYCHOLOGY_DATA_PATH)
    quality = validate_psychology_data(data)
    labels = list(get_psychology_labels())
    test = data[data.split == 'test'].reset_index(drop=True)
    probabilities = model.pipeline.predict_proba(test.text)
    report = {'test': multi_label_metrics(test[labels].to_numpy(dtype=int), probabilities, model.thresholds),
              'dataset_quality': quality, 'language_slices': {}}
    for language in test.language.unique():
        mask = test.language.eq(language).to_numpy()
        report['language_slices'][language] = multi_label_metrics(test.loc[mask, labels].to_numpy(dtype=int), probabilities[mask], model.thresholds)
    errors = review_errors(test, probabilities, model.thresholds)
    for rows in errors.values():
        for row in rows:
            row['split'] = 'test'
    test_review_counts = {kind: len(rows) for kind, rows in errors.items()}
    # Supplement scarce test false positives with clearly marked validation errors.
    validation = data[data.split == 'validation'].reset_index(drop=True)
    validation_errors = review_errors(validation, model.pipeline.predict_proba(validation.text), model.thresholds)
    for kind, rows in errors.items():
        for row in validation_errors[kind][:max(0, 25 - len(rows))]:
            row['split'] = 'validation'
            rows.append(row)
    # Training errors are review material only, never held-out performance evidence.
    training = data[data.split == 'train'].reset_index(drop=True)
    training_errors = review_errors(training, model.pipeline.predict_proba(training.text), model.thresholds)
    for kind, rows in errors.items():
        for row in training_errors[kind][:max(0, 25 - len(rows))]:
            row['split'] = 'train'
            rows.append(row)
    report['test_review_counts'] = test_review_counts
    report['review_note'] = 'Test errors first; insufficient test FP examples supplemented by marked validation then training errors. No test threshold tuning.'
    report['review_counts'] = {kind: len(rows) for kind, rows in errors.items()}
    report['weak_labels'] = sorted(report['test']['per_label'], key=lambda label: report['test']['per_label'][label]['f1'])[:3]
    PSYCHOLOGY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (PSYCHOLOGY_REPORT_DIR / 'saved_model_evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (PSYCHOLOGY_REPORT_DIR / 'error_review.json').write_text(json.dumps(errors, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2))
    print('False-positive and false-negative review examples:')
    print(json.dumps(errors, indent=2, ensure_ascii=True))
    return report


if __name__ == '__main__':
    evaluate()
