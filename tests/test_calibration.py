from backend.app.fusion.calibration import FusionCalibrator

def test_calibrator_falls_back_when_training_modalities_do_not_match():
    class Model:
        def predict_proba(self, row): return [[.2,.8]]
    model=FusionCalibrator(Model(),None,['x'],'test',{'graph_available':0,'context_available':0,'scenario_available':0,'psychology_available':0})
    assert model.predict({'x':1,'graph_available':1}) is None
    assert model.predict({'x':1,'graph_available':0})==.8

def test_isotonic_calibrator_uses_predict_interface():
    class Model:
        def predict_proba(self, row): return [[.4,.6]]
    class Isotonic:
        def predict(self, row): return [.25]
    model=FusionCalibrator(Model(),Isotonic(),['x'],'test',{})
    assert model.predict({'x':1})==.25
