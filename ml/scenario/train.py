"""Compare TF-IDF logistic regression and linear SVM on unseen template families."""
import hashlib
import json
import joblib
import pandas as pd
import sklearn
from backend.app.features.text_features import make_text_vectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from backend.app.config.context_config import SCENARIO_DATA_PATH, SCENARIO_MODEL_PATH, SCENARIO_REPORT_DIR, SCENARIO_SEED
from backend.app.utils.scenario_labels import get_scenario_labels
from ml.scenario.data_quality import validate_messages
from ml.scenario.metrics import evaluate_pipeline


def make_pipeline(classifier) -> Pipeline:
    return Pipeline([('tfidf', make_text_vectorizer()), ('classifier', classifier)])


def train() -> dict:
    data = pd.read_csv(SCENARIO_DATA_PATH)
    quality = validate_messages(data)
    print(f"Validated {len(data)} unique messages, {quality['template_families']} disjoint template families")
    train_data, validation, test = (data[data.split == role] for role in ('train', 'validation', 'test'))
    models = {
        'tfidf_logistic_regression': make_pipeline(LogisticRegression(C=4, max_iter=2000,
            class_weight='balanced', random_state=SCENARIO_SEED)),
        'tfidf_linear_svm': make_pipeline(LinearSVC(C=1, dual='auto', class_weight='balanced', random_state=SCENARIO_SEED)),
    }
    reports = {}
    for name, model in models.items():
        # Inputs are text only. No labels, source-template identifiers or split flags enter the pipeline.
        model.fit(train_data.text, train_data.scenario_label)
        reports[name] = {'validation': evaluate_pipeline(model, validation), 'test': evaluate_pipeline(model, test)}
    selected = max(reports, key=lambda name: reports[name]['validation']['macro_f1'])
    classifier = models[selected].named_steps['classifier']
    metadata = {'selected_model': selected, 'selected_by': 'validation macro F1', 'seed': SCENARIO_SEED,
        'sklearn_version': sklearn.__version__, 'labels': list(get_scenario_labels()), 'input_features': ['text'],
        'split_strategy': '60/20/20 class/language balanced; template families stay in one split',
        'confidence_kind': 'uncalibrated logistic output' if hasattr(classifier, 'predict_proba') else 'softmax of SVM margins; heuristic evidence',
        'dataset_sha256': hashlib.sha256(SCENARIO_DATA_PATH.read_bytes()).hexdigest(),
        'limitations': 'Synthetic narratives, only 110 source families. No real-world performance or calibrated fraud probability.'}
    SCENARIO_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCENARIO_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({'schema_version': 1, 'kind': 'scenario', 'pipeline': models[selected], 'metadata': metadata}, SCENARIO_MODEL_PATH)
    SCENARIO_MODEL_PATH.with_suffix('.metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    report = {'metadata': metadata, 'models': reports, 'dataset_quality': quality}
    (SCENARIO_REPORT_DIR / 'scenario_evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (SCENARIO_REPORT_DIR / 'dataset_quality.json').write_text(json.dumps(quality, indent=2), encoding='utf-8')
    features = models[selected].named_steps['tfidf'].get_feature_names_out()
    coefficients = classifier.coef_
    importance = {label: [str(features[index]) for index in coefficients[i].argsort()[-12:][::-1]]
                  for i, label in enumerate(classifier.classes_)}
    (SCENARIO_REPORT_DIR / 'top_class_terms.json').write_text(json.dumps(importance, indent=2), encoding='utf-8')
    for name, metrics in reports.items():
        print(f"{name}: validation macro F1={metrics['validation']['macro_f1']:.3f}, test macro F1={metrics['test']['macro_f1']:.3f}")
    print(f'Selected {selected} by validation results; saved {SCENARIO_MODEL_PATH}')
    return report


if __name__ == '__main__':
    train()
