"""Optional learned probability and validation-fitted calibration adapter."""
import joblib
import numpy as np
import pandas as pd
from backend.app.config.risk_config import FUSION_CALIBRATION_PATH, FUSION_MODEL_PATH,PROJECT_ROOT

class FusionCalibrator:
    def __init__(self, model=None, calibrator=None, feature_names=None, version='manual-grouped-v1', modality_profile=None):
        self.model, self.calibrator = model, calibrator
        self.feature_names = list(feature_names or [])
        self.version = version
        self.modality_profile = dict(modality_profile or {})

    @classmethod
    def load(cls):
        model_path,calibration_path=FUSION_MODEL_PATH,FUSION_CALIBRATION_PATH
        version='fusion-logistic-platt-v1'
        registry_path=PROJECT_ROOT/'models'/'registry'/'registry.json'
        if registry_path.exists():
            try:
                import json
                registry=json.loads(registry_path.read_text(encoding='utf-8'))
                version=registry['models']['fusion']['active_version']
                entry=registry['models']['fusion']['versions'][version]
                model_path=(PROJECT_ROOT/entry['artifact_path']).resolve()
                calibration_path=(PROJECT_ROOT/entry['calibration_path']).resolve()
                if PROJECT_ROOT.resolve() not in model_path.parents or PROJECT_ROOT.resolve() not in calibration_path.parents:
                    raise ValueError('Registry artifacts must stay inside the project directory.')
            except (KeyError,ValueError,TypeError,OSError):
                model_path,calibration_path=FUSION_MODEL_PATH,FUSION_CALIBRATION_PATH
                version='fusion-logistic-platt-v1'
        artifact = joblib.load(model_path) if model_path.exists() else None
        cal = joblib.load(calibration_path) if calibration_path.exists() else None
        if isinstance(artifact, dict):
            model, names = artifact.get('estimator'), artifact.get('features', [])
            profile = artifact.get('modality_profile', {})
        else:
            model, names, profile = artifact, list(getattr(artifact, 'feature_names_in_', [])), {}
        calibrator = cal.get(cal.get('method')) if isinstance(cal, dict) else cal
        return cls(model, calibrator, names,
                   version if model is not None else 'manual-grouped-v1', profile)

    def predict(self, features):
        if self.model is None:
            return None
        live_profile = {'graph_available': int(features.get('graph_available', 0)),
                        'context_available': int(features.get('context_available', 0)),
                        'scenario_available': int(features.get('scenario_available', 0)),
                        'psychology_available': int(features.get('psychology_available', 0))}
        if self.modality_profile and live_profile != self.modality_profile:
            return None
        row = pd.DataFrame([[float(features.get(name, 0.0)) for name in self.feature_names]],
                           columns=self.feature_names)
        raw = float(np.asarray(self.model.predict_proba(row))[0, 1])
        if self.calibrator is None:
            return raw
        if hasattr(self.calibrator, 'predict_proba'):
            return float(self.calibrator.predict_proba([[raw]])[0, 1])
        return float(self.calibrator.predict([raw])[0])
