"""Run a registered challenger beside the active fusion model on an immutable holdout."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, precision_score, recall_score
from backend.app.config.risk_config import PROJECT_ROOT
from backend.app.fusion.calibration import FusionCalibrator
from ml.fusion.build_dataset import FEATURES, OUT
from ml.retraining.registry import load_registry


def fingerprint(frame: pd.DataFrame) -> str:
    stable=frame.sort_values('timestamp',kind='mergesort').reset_index(drop=True)
    return hashlib.sha256(stable.to_csv(index=False,lineterminator='\n').encode('utf-8')).hexdigest()


def _predict(record: dict, candidate: dict) -> float:
    artifact=PROJECT_ROOT/candidate['artifact_path']
    import joblib
    model=joblib.load(artifact)
    vector=np.asarray([[float(record.get(name,0) or 0) for name in candidate.get('features',FEATURES)]])
    probability=float(model.predict_proba(vector)[0,1])
    calibration=candidate.get('calibration_path')
    if calibration:
        calibrator=joblib.load(PROJECT_ROOT/calibration)
        probability=float(calibrator.predict_proba([[probability]])[0,1])
    return probability


def run(version: str, input_path=OUT, output_dir=PROJECT_ROOT/'reports') -> dict:
    registry=load_registry();fusion=registry['models']['fusion'];candidate=fusion['versions'].get(version)
    if not candidate or candidate.get('status')!='CHALLENGER':
        raise ValueError('Shadow mode requires a registered CHALLENGER version.')
    data=pd.read_csv(input_path).sort_values('timestamp',kind='mergesort').reset_index(drop=True)
    if len(data)<100:raise ValueError('Shadow evaluation requires at least 100 rows.')
    holdout=data.iloc[int(len(data)*.8):].copy();records=holdout[FEATURES].to_dict('records')
    active=FusionCalibrator.load();champion=np.asarray([active.predict(row) for row in records])
    challenger=np.asarray([_predict(row,candidate) for row in records]);y=holdout.is_fraud.to_numpy(dtype=int)
    cutoff=float(json.loads((PROJECT_ROOT/'data/processed/day6/evaluation.json').read_text(encoding='utf-8')).get('threshold',.5))
    report={'active_version':fusion['active_version'],'candidate_version':version,'same_holdout':True,
        'holdout_fingerprint':fingerprint(holdout),'holdout_samples':len(holdout),
        'active':{'pr_auc':float(average_precision_score(y,champion)),'brier':float(brier_score_loss(y,champion)),
            'precision':float(precision_score(y,champion>=cutoff,zero_division=0)),
            'recall':float(recall_score(y,champion>=cutoff,zero_division=0))},
        'challenger':{'pr_auc':float(average_precision_score(y,challenger)),'brier':float(brier_score_loss(y,challenger)),
            'precision':float(precision_score(y,challenger>=cutoff,zero_division=0)),
            'recall':float(recall_score(y,challenger>=cutoff,zero_division=0))},
        'threshold':cutoff,'status':'SHADOW_ONLY','notice':'Synthetic temporal holdout; this report does not authorize or perform promotion.'}
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    (output_dir/f'shadow_{version}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--version',required=True)
    args=parser.parse_args();print(json.dumps(run(args.version),indent=2))
