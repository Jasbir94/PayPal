"""Startup-loaded multi-label pipeline and its validation-selected thresholds."""
import json
from pathlib import Path
import joblib
import numpy as np
from backend.app.config.psychology_config import PSYCHOLOGY_MODEL_PATH, PSYCHOLOGY_THRESHOLDS_PATH
from backend.app.utils.psychology_labels import get_psychology_labels


class PsychologyModel:
    def __init__(self, artifact_path: Path = PSYCHOLOGY_MODEL_PATH,
                 thresholds_path: Path = PSYCHOLOGY_THRESHOLDS_PATH):
        artifact = joblib.load(artifact_path)  # only trusted, locally generated artifacts
        labels = get_psychology_labels()
        if (artifact.get('kind') != 'psychology' or artifact.get('schema_version') != 1 or
                artifact.get('metadata', {}).get('labels') != list(labels)):
            raise ValueError('Incompatible psychology artifact; retrain the current taxonomy')
        self.pipeline, self.metadata = artifact['pipeline'], artifact['metadata']
        self.thresholds = json.loads(thresholds_path.read_text(encoding='utf-8'))
        if (set(self.thresholds) != set(labels) or self.thresholds != artifact.get('thresholds') or
                not all(0 < float(value) < 1 for value in self.thresholds.values())):
            raise ValueError('Psychology thresholds are missing, invalid or incompatible with the model')

    def predict_manipulation(self, text: str | None) -> dict[str, float]:
        labels = get_psychology_labels()
        if not text or not text.strip():
            return dict.fromkeys(labels, 0.0)
        vectorizer = self.pipeline.named_steps['tfidf']
        if vectorizer.transform([text]).nnz == 0:
            return dict.fromkeys(labels, 0.0)
        probabilities = self.pipeline.predict_proba([text])[0]
        if len(probabilities) != len(labels) or not np.isfinite(probabilities).all():
            raise ValueError('Invalid psychology model output')
        return {label: float(np.clip(probability, 0, 1)) for label, probability in zip(labels, probabilities)}
