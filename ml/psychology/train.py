"""Fit a text-only TF-IDF One-vs-Rest logistic baseline with validation thresholds."""
import hashlib
import json
import joblib
import pandas as pd
import sklearn
from sklearn.pipeline import Pipeline
from sklearn.multiclass import OneVsRestClassifier
from sklearn.linear_model import LogisticRegression
from backend.app.features.text_features import make_text_vectorizer
from backend.app.utils.psychology_labels import get_psychology_labels
from backend.app.config.psychology_config import (PSYCHOLOGY_DATA_PATH, PSYCHOLOGY_MODEL_PATH,
    PSYCHOLOGY_THRESHOLDS_PATH, PSYCHOLOGY_REPORT_DIR, SEED)
from ml.psychology.data_quality import validate_psychology_data
from ml.psychology.metrics import select_thresholds, multi_label_metrics


def train() -> dict:
    data = pd.read_csv(PSYCHOLOGY_DATA_PATH)
    quality = validate_psychology_data(data)
    labels = list(get_psychology_labels())
    train_data, validation, test = (data[data.split == role] for role in ('train', 'validation', 'test'))
    pipeline = Pipeline([('tfidf', make_text_vectorizer()), ('classifier', OneVsRestClassifier(
        LogisticRegression(C=4, class_weight='balanced', max_iter=2000, random_state=SEED), n_jobs=1))])
    # Text is the sole input; taxonomy indicators, provenance and IDs are never features.
    pipeline.fit(train_data.text, train_data[labels].to_numpy(dtype=int))
    validation_probabilities = pipeline.predict_proba(validation.text)
    thresholds, comparison = select_thresholds(validation[labels].to_numpy(dtype=int), validation_probabilities)
    test_probabilities = pipeline.predict_proba(test.text)
    metadata = {'seed': SEED, 'labels': labels, 'input_features': ['text'], 'sklearn_version': sklearn.__version__,
        'threshold_selection': 'maximum validation F1 per label, recall then closeness to .5 as tie-breakers',
        'split_strategy': quality['stratification_note'], 'probabilities': 'uncalibrated per-label logistic outputs',
        'dataset_sha256': hashlib.sha256(PSYCHOLOGY_DATA_PATH.read_bytes()).hexdigest(),
        'limitations': 'Synthetic component-composed messages; source phrasing and correlations can differ substantially from real conversations.'}
    PSYCHOLOGY_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    PSYCHOLOGY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({'schema_version': 1, 'kind': 'psychology', 'pipeline': pipeline,
                 'thresholds': thresholds, 'metadata': metadata}, PSYCHOLOGY_MODEL_PATH)
    PSYCHOLOGY_THRESHOLDS_PATH.write_text(json.dumps(thresholds, indent=2), encoding='utf-8')
    PSYCHOLOGY_MODEL_PATH.with_suffix('.metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    report = {'metadata': metadata, 'thresholds': thresholds, 'threshold_comparison': comparison,
        'validation': multi_label_metrics(validation[labels].to_numpy(dtype=int), validation_probabilities, thresholds),
        'test': multi_label_metrics(test[labels].to_numpy(dtype=int), test_probabilities, thresholds),
        'test_default_0_5': multi_label_metrics(test[labels].to_numpy(dtype=int), test_probabilities, dict.fromkeys(labels, .5)),
        'dataset_quality': quality}
    (PSYCHOLOGY_REPORT_DIR / 'training_evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    features = pipeline.named_steps['tfidf'].get_feature_names_out()
    terms = {label: [str(features[i]) for i in estimator.coef_[0].argsort()[-12:][::-1]]
             for label, estimator in zip(labels, pipeline.named_steps['classifier'].estimators_)}
    (PSYCHOLOGY_REPORT_DIR / 'top_label_terms.json').write_text(json.dumps(terms, indent=2), encoding='utf-8')
    print(f"Saved {PSYCHOLOGY_MODEL_PATH}; validation micro F1={report['validation']['micro_f1']:.3f}, "
          f"test micro F1={report['test']['micro_f1']:.3f}, macro F1={report['test']['macro_f1']:.3f}")
    print(json.dumps(thresholds, indent=2))
    return report


if __name__ == '__main__':
    train()
