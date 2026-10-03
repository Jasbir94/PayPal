import numpy as np
from backend.app.monitoring.drift import population_stability_index,categorical_jsd
from backend.app.monitoring.calibration import calibration_report


def test_drift_waits_for_minimum_window_and_detects_shift():
    assert population_stability_index(list(range(10)),list(range(10))) is None
    score=population_stability_index(np.linspace(0,1,100),np.linspace(3,4,100))
    assert score is not None and score>.2
    assert categorical_jsd(['A']*40,['B']*40)>.15


def test_calibration_requires_trusted_mature_labels():
    assert calibration_report([])['status']=='INSUFFICIENT_MATURE_LABELS'
