"""Fit a structural-only, account-disjoint earlier-to-later logistic baseline."""
import hashlib
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from backend.app.config.graph_config import GRAPH_FEATURE_PATH, GRAPH_MODEL_PATH, GRAPH_ML_FEATURES, GRAPH_REPORT_DIR
from backend.app.config.risk_config import SEED
from ml.graph.metrics import validation_threshold, binary_metrics

def feature_frame(data):
    return data[GRAPH_ML_FEATURES].replace([np.inf, -np.inf], np.nan)

def train():
    data = pd.read_csv(GRAPH_FEATURE_PATH)
    if data.account_id.duplicated().any():
        raise ValueError('Repeated target accounts across graph splits')
    train, validation, test = [data[data.split.eq(role)] for role in ('train', 'validation', 'test')]
    if not (pd.to_datetime(train['at'], utc=True).max() < pd.to_datetime(validation['at'], utc=True).min() <
            pd.to_datetime(test['at'], utc=True).min()):
        raise ValueError('Graph temporal partition ordering violated')
    pipeline = Pipeline([('imputer', SimpleImputer(strategy='median', add_indicator=True)),
        ('scaler', StandardScaler()),
        ('classifier', LogisticRegression(C=1, class_weight='balanced', max_iter=2000, random_state=SEED))])
    pipeline.fit(feature_frame(train), train.is_known_mule)
    threshold, comparisons = validation_threshold(validation.is_known_mule, pipeline.predict_proba(feature_frame(validation))[:, 1])
    metadata = {'seed': SEED, 'target': 'is_known_mule', 'positive_unlabeled_limit': True,
        'training_accounts': train.account_id.tolist(), 'validation_accounts': validation.account_id.tolist(),
        'test_accounts': test.account_id.tolist(), 'threshold_selection': 'validation F1 only',
        'dataset_sha256': hashlib.sha256(GRAPH_FEATURE_PATH.read_bytes()).hexdigest(),
        'prohibited_features': ['is_known_mule', 'is_suspicious', 'fraud_type',
            'known_mule_neighbors', 'distance_to_known_mule', 'fraud_reported_neighbors', 'account_age_days'],
        'limitations': 'Original graph crosses target partitions. Only 18 known positives; 22 suspicious unlabeled accounts are treated negative. Synthetic overlays are designed using suspicious profiles. Uncalibrated probabilities.'}
    artifact = {'kind': 'graph', 'schema_version': 1, 'features': GRAPH_ML_FEATURES,
                'pipeline': pipeline, 'threshold': threshold, 'metadata': metadata}
    GRAPH_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, GRAPH_MODEL_PATH)
    GRAPH_MODEL_PATH.with_suffix('.schema.json').write_text(json.dumps(
        {'features': GRAPH_ML_FEATURES, 'threshold': threshold, 'metadata': metadata}, indent=2), encoding='utf-8')
    report = {'metadata': metadata, 'threshold_grid': comparisons,
        'validation': binary_metrics(validation.is_known_mule, pipeline.predict_proba(feature_frame(validation))[:, 1], threshold),
        'test': binary_metrics(test.is_known_mule, pipeline.predict_proba(feature_frame(test))[:, 1], threshold),
        'coefficients': dict(zip(GRAPH_ML_FEATURES, pipeline.named_steps['classifier'].coef_[0][:len(GRAPH_ML_FEATURES)].tolist()))}
    GRAPH_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (GRAPH_REPORT_DIR / 'training_evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'validation': report['validation'], 'test': report['test']}, indent=2))
    return report

if __name__ == '__main__':
    train()
