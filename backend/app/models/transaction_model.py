"""Transaction baseline inference; training is an explicit CLI step."""
from pathlib import Path
from backend.app.config.risk_config import MODEL_DIR, TRANSACTION_FEATURES
from backend.app.models.baseline import BaselineModel


class TransactionModel(BaselineModel):
    def __init__(self, artifact_path: Path = MODEL_DIR / 'transaction_model.pkl'):
        super().__init__(artifact_path, TRANSACTION_FEATURES, 'transaction')
