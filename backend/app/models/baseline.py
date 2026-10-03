"""Shared persisted baseline loader; trusted local artifacts only."""
from pathlib import Path
import joblib
import numpy as np
import pandas as pd


class BaselineModel:
    def __init__(self, artifact_path: Path, expected_features: list[str], expected_kind: str):
        # joblib/pickle can execute code: never load user-uploaded artifacts.
        artifact = joblib.load(artifact_path)
        if (artifact.get('features') != expected_features or
                artifact.get('kind') != expected_kind or artifact.get('schema_version') != 1):
            raise ValueError(f'Incompatible {expected_kind} model artifact; retrain the Day 2 model')
        self.model = artifact['model']
        self.features = artifact['features']
        self.threshold = float(artifact['threshold'])
        self.metadata = artifact['metadata']

    def probability(self, features: dict) -> float:
        row = pd.DataFrame([{column: features[column] for column in self.features}])
        if not np.isfinite(row.to_numpy(dtype=float)).all():
            raise ValueError('Model input contains non-finite features')
        positive = list(self.model.classes_).index(1)
        return float(self.model.predict_proba(row)[0, positive])
