"""Startup-loaded structural graph model; no target/proximity/report features."""
import joblib
import numpy as np
import pandas as pd
from backend.app.config.graph_config import GRAPH_MODEL_PATH, GRAPH_ML_FEATURES

class GraphModel:
    def __init__(self, artifact_path=GRAPH_MODEL_PATH):
        artifact = joblib.load(artifact_path)
        if artifact.get('kind') != 'graph' or artifact.get('features') != GRAPH_ML_FEATURES:
            raise ValueError('Incompatible graph artifact')
        self.pipeline, self.metadata = artifact['pipeline'], artifact['metadata']
        self.threshold = float(artifact['threshold'])

    def probability(self, features):
        frame = pd.DataFrame([{key: np.nan if features[key] is None else features[key]
                               for key in GRAPH_ML_FEATURES}], columns=GRAPH_ML_FEATURES)
        probability = float(self.pipeline.predict_proba(frame)[0, 1])
        if not np.isfinite(probability):
            raise ValueError('Invalid graph prediction')
        return min(1.0, max(0.0, probability))
