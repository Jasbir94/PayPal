"""Saved model contracts and leakage-resistant dataset checks."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from backend.app.models.psychology_model import PsychologyModel
from backend.app.config.psychology_config import PSYCHOLOGY_DATA_PATH, PSYCHOLOGY_THRESHOLDS_PATH
from backend.app.utils.psychology_labels import get_psychology_labels
from ml.psychology.data_quality import validate_psychology_data
from ml.psychology.metrics import select_thresholds
from backend.app.schemas.psychology import ManipulationScores

@pytest.fixture(scope='module')
def model():
    return PsychologyModel()

def test_real_multilabel_output_and_missing_text(model):
    scores = model.predict_manipulation('I am from police. Transfer now or you will be arrested.')
    assert set(scores) == set(get_psychology_labels())
    assert all(0 <= score <= 1 for score in scores.values())
    assert all(score == 0 for score in model.predict_manipulation(None).values())
    assert model.thresholds == json.loads(PSYCHOLOGY_THRESHOLDS_PATH.read_text())
    assert model.metadata['input_features'] == ['text']

def test_family_disjoint_data():
    data = pd.read_csv(PSYCHOLOGY_DATA_PATH)
    quality = validate_psychology_data(data)
    assert len(data) == 6000
    assert data.split.value_counts().to_dict() == {'train': 4200, 'validation': 900, 'test': 900}
    assert quality
    assert data.groupby('split').language.nunique().eq(2).all()

def test_invalid_score_contract():
    with pytest.raises(ValueError):
        ManipulationScores({'fear': 1})
    with pytest.raises(ValueError):
        ManipulationScores(dict.fromkeys(get_psychology_labels(), float('nan')))

def test_threshold_selection_uses_supplied_validation_targets():
    actual = np.tile([[0], [1]], (1, 10))
    probabilities = np.tile([[.1], [.4]], (1, 10))
    thresholds, comparison = select_thresholds(actual, probabilities)
    assert set(thresholds) == set(get_psychology_labels())
    assert all(value in (.3, .4) for value in thresholds.values())
    assert all(len(values) == 5 for values in comparison.values())

def test_missing_artifact():
    with pytest.raises(FileNotFoundError):
        PsychologyModel(Path('nonexistent_psychology_artifact.pkl'))
