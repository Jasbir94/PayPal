"""Train Logistic Regression and validation-only Platt/isotonic calibrators."""
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, precision_recall_curve
from backend.app.config.risk_config import PROJECT_ROOT, MODEL_DIR
from ml.fusion.build_dataset import FEATURES, OUT

REPORT = PROJECT_ROOT / 'data' / 'processed' / 'day6'
META = MODEL_DIR / 'fusion_metadata.json'
CAL_PATH = MODEL_DIR / 'calibration_model.pkl'
MODEL_PATH = MODEL_DIR / 'fusion_model.pkl'

def _platt(raw, y):
    model = LogisticRegression(C=1e6, random_state=42).fit(np.asarray(raw).reshape(-1, 1), y)
    return model

def train():
    data = pd.read_csv(OUT).sort_values('timestamp')
    n = len(data); train_end, val_end = int(n * .6), int(n * .8)
    train, val, test = data.iloc[:train_end], data.iloc[train_end:val_end], data.iloc[val_end:]
    x_train, y_train = train[FEATURES], train.is_fraud.astype(int)
    x_val, y_val = val[FEATURES], val.is_fraud.astype(int)
    x_test, y_test = test[FEATURES], test.is_fraud.astype(int)
    estimator = LogisticRegression(max_iter=2000, class_weight='balanced', random_state=42)
    estimator.fit(x_train, y_train)
    raw_val = estimator.predict_proba(x_val)[:, 1]
    raw_test = estimator.predict_proba(x_test)[:, 1]
    platt = _platt(raw_val, y_val)
    iso = IsotonicRegression(out_of_bounds='clip').fit(raw_val, y_val)
    calibrated = {'platt': platt.predict_proba(raw_test.reshape(-1, 1))[:, 1],
                  'isotonic': iso.predict(raw_test)}
    val_cal = {'platt': platt.predict_proba(raw_val.reshape(-1, 1))[:, 1],
               'isotonic': iso.predict(raw_val)}
    selected = min(val_cal, key=lambda name: brier_score_loss(y_val, val_cal[name]))
    test_probability = calibrated[selected]
    # Threshold is selected on validation F1; test remains untouched until this point.
    thresholds = np.arange(.10, .91, .025)
    scored = []
    for threshold in thresholds:
        pred = val_cal[selected] >= threshold
        tp = int(((pred) & (y_val.to_numpy() == 1)).sum())
        fp = int(((pred) & (y_val.to_numpy() == 0)).sum())
        fn = int(((~pred) & (y_val.to_numpy() == 1)).sum())
        precision = tp / (tp + fp) if tp + fp else 0
        recall = tp / (tp + fn) if tp + fn else 0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
        scored.append({'threshold': round(float(threshold), 4), 'precision': precision,
                       'recall': recall, 'f1': f1, 'false_positive_rate': fp / max(1, (y_val == 0).sum()),
                       'false_negative_rate': fn / max(1, (y_val == 1).sum())})
    best = max(scored, key=lambda item: (item['f1'], item['precision']))
    MODEL_DIR.mkdir(parents=True, exist_ok=True); REPORT.mkdir(parents=True, exist_ok=True)
    joblib.dump({'estimator': estimator, 'features': FEATURES,
                 'modality_profile': {key: int(data[key].max()) for key in
                     ('graph_available','context_available','scenario_available','psychology_available')}}, MODEL_PATH)
    joblib.dump({'method': selected, 'platt': platt, 'isotonic': iso}, CAL_PATH)
    metadata = {'version':'fusion-logistic-v1', 'features': FEATURES, 'split': {'train':len(train),'validation':len(val),'test':len(test),
                'time_ordered':True}, 'positive_counts': {'train':int(y_train.sum()),'validation':int(y_val.sum()),'test':int(y_test.sum())},
                'selected_calibrator': selected, 'calibration_validation_brier': {
                    key:float(brier_score_loss(y_val, val_cal[key])) for key in val_cal},
                'test_brier':float(brier_score_loss(y_test, test_probability)), 'selected_threshold':best,
                'threshold_grid':scored, 'limitations':'Synthetic labels; graph, context, scenario and psychology are unlinked and excluded.'}
    META.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(json.dumps(metadata, indent=2))
    return metadata

if __name__ == '__main__': train()
