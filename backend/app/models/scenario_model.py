"""Startup-loaded, text-only scenario classifier with lightweight term evidence."""
from pathlib import Path
import joblib
import numpy as np
from backend.app.config.context_config import SCENARIO_MODEL_PATH
from backend.app.utils.scenario_labels import get_scenario_labels


class ScenarioModel:
    def __init__(self, artifact_path: Path = SCENARIO_MODEL_PATH):
        artifact = joblib.load(artifact_path)  # locally trained, trusted artifact only
        if (artifact.get('kind') != 'scenario' or artifact.get('schema_version') != 1 or
                artifact.get('metadata', {}).get('labels') != list(get_scenario_labels())):
            raise ValueError('Incompatible scenario model; retrain with the current taxonomy')
        self.pipeline = artifact['pipeline']
        self.metadata = artifact['metadata']
        self.vectorizer = self.pipeline.named_steps['tfidf']
        self.classifier = self.pipeline.named_steps['classifier']
        if set(self.classifier.classes_) != set(get_scenario_labels()):
            raise ValueError('Scenario artifact is missing taxonomy classes')
        self.feature_names = self.vectorizer.get_feature_names_out()

    def predict(self, text: str) -> dict:
        vector = self.vectorizer.transform([text])
        labels = get_scenario_labels()
        if vector.nnz == 0:
            return {'scores': {label: float(label == labels[0]) for label in labels},
                    'scenario': labels[0], 'confidence_kind': 'no_supported_text_tokens', 'support_terms': []}
        if hasattr(self.classifier, 'predict_proba'):
            weights = self.classifier.predict_proba(vector)[0]
            kind = 'uncalibrated_logistic_output'
        else:
            margins = self.classifier.decision_function(vector)[0]
            weights = np.exp(margins - np.max(margins))
            weights /= weights.sum()
            kind = 'svm_margin_softmax_evidence'
        scores = {str(label): float(weight) for label, weight in zip(self.classifier.classes_, weights)}
        best = max(scores, key=scores.get)
        class_index = list(self.classifier.classes_).index(best)
        columns = vector.indices
        contributions = vector.data * self.classifier.coef_[class_index, columns]
        order = np.argsort(contributions)[::-1]
        terms = [str(self.feature_names[columns[i]]) for i in order[:5] if contributions[i] > 0]
        return {'scores': scores, 'scenario': best, 'confidence_kind': kind, 'support_terms': terms}
