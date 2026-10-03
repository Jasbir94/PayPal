"""Recipient suspicious-account baseline inference."""
from pathlib import Path
from backend.app.config.risk_config import MODEL_DIR, RECIPIENT_FEATURES
from backend.app.models.baseline import BaselineModel


class RecipientModel(BaselineModel):
    def __init__(self, artifact_path: Path = MODEL_DIR / 'recipient_model.pkl'):
        super().__init__(artifact_path, RECIPIENT_FEATURES, 'recipient')
