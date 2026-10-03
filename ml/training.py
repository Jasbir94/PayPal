"""Compare two baselines on validation data and persist the selected model."""
import json
import joblib
import sklearn
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from backend.app.config.risk_config import SEED, MODEL_DIR, REPORT_DIR
from ml.metrics import evaluate_probabilities, choose_threshold


def assign_splits(frame: pd.DataFrame, kind: str) -> pd.DataFrame:
    result = frame.copy()
    result['split'] = 'train'
    if kind == 'transaction':
        # Timestamp cutoffs put ties in the same partition; history is strictly earlier.
        first = result.timestamp.iloc[int(len(result) * .6)]
        second = result.timestamp.iloc[int(len(result) * .8)]
        result.loc[result.timestamp >= first, 'split'] = 'validation'
        result.loc[result.timestamp >= second, 'split'] = 'test'
    else:
        train, remaining = train_test_split(result.index, test_size=.4,
            stratify=result.target, random_state=SEED)
        validation, test = train_test_split(remaining, test_size=.5,
            stratify=result.loc[remaining, 'target'], random_state=SEED)
        result.loc[validation, 'split'] = 'validation'
        result.loc[test, 'split'] = 'test'
    for split in ('train', 'validation', 'test'):
        if result.loc[result.split == split, 'target'].nunique() != 2:
            raise ValueError(f'{kind} {split} split requires both target classes')
    return result


def feature_importance(model, features: list[str]) -> dict[str, float]:
    if hasattr(model, 'feature_importances_'):
        weights = model.feature_importances_
    else:
        # Signed coefficients are for standardized inputs, not causal explanations.
        weights = model.steps[-1][1].coef_[0]
    return {name: float(value) for name, value in sorted(zip(features, weights),
                                                        key=lambda item: abs(item[1]), reverse=True)}


def train_baselines(frame: pd.DataFrame, features: list[str], kind: str, target_description: str) -> dict:
    data = assign_splits(frame, kind)
    if not np.isfinite(data[features].to_numpy(dtype=float)).all():
        raise ValueError('Training features must be finite')
    train = data[data.split == 'train']
    validation = data[data.split == 'validation']
    test = data[data.split == 'test']
    candidates = {
        'logistic_regression': make_pipeline(StandardScaler(), LogisticRegression(
            max_iter=2000, class_weight='balanced', C=.5, random_state=SEED)),
        'random_forest': RandomForestClassifier(n_estimators=200, max_depth=8,
            min_samples_leaf=4, class_weight='balanced', random_state=SEED, n_jobs=1),
    }
    reports = {}
    for name, model in candidates.items():
        model.fit(train[features], train.target)
        validation_probabilities = model.predict_proba(validation[features])[:, 1]
        threshold = choose_threshold(validation.target, validation_probabilities)
        reports[name] = {
            'validation': evaluate_probabilities(validation.target, validation_probabilities, threshold),
            'test': evaluate_probabilities(test.target, model.predict_proba(test[features])[:, 1], threshold),
            'feature_importance': feature_importance(model, features),
        }
    # Test metrics are reported, never used for model/threshold selection.
    selected = max(reports, key=lambda name: reports[name]['validation']['pr_auc_average_precision'])
    threshold = reports[selected]['validation']['threshold']
    metadata = {
        'seed': SEED, 'sklearn_version': sklearn.__version__, 'selected_model': selected,
        'target': target_description, 'selected_by': 'validation average precision',
        'split_strategy': 'chronological 60/20/20' if kind == 'transaction' else 'account-disjoint stratified 60/20/20',
        'feature_window': 'strictly before scoring timestamp; 24h recipient snapshot',
        'probabilities': 'uncalibrated synthetic baseline outputs; not APP fraud probabilities',
        'split_counts': data.groupby('split').target.agg(['size', 'sum']).to_dict('index'),
        'feature_columns': features,
    }
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({'schema_version': 1, 'kind': kind, 'model': candidates[selected],
                 'features': features, 'threshold': threshold, 'metadata': metadata},
                MODEL_DIR / f'{kind}_model.pkl')
    report = {'metadata': metadata, 'models': reports}
    (MODEL_DIR / f'{kind}_model.metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    (REPORT_DIR / f'{kind}_evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    data.to_csv(REPORT_DIR / f'{kind}_features.csv', index=False)
    print(json.dumps(report, indent=2))
    return report


def evaluate_saved_model(kind: str) -> dict:
    artifact = joblib.load(MODEL_DIR / f'{kind}_model.pkl')
    frame = pd.read_csv(REPORT_DIR / f'{kind}_features.csv')
    test = frame[frame.split == 'test']
    probabilities = artifact['model'].predict_proba(test[artifact['features']])[:, 1]
    report = {'kind': kind, 'selected_model': artifact['metadata']['selected_model'],
              'test': evaluate_probabilities(test.target, probabilities, artifact['threshold']),
              'feature_importance': feature_importance(artifact['model'], artifact['features'])}
    print(json.dumps(report, indent=2))
    return report
