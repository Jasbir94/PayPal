"""Saved-model test metrics, language slices and separate manually written Hinglish evaluation."""
import json
import pandas as pd
from backend.app.models.scenario_model import ScenarioModel
from backend.app.config.context_config import SCENARIO_DATA_PATH, SCENARIO_REPORT_DIR
from ml.scenario.data_quality import validate_messages
from ml.scenario.metrics import evaluate_pipeline
from ml.scenario.hinglish_examples import HINGLISH_HOLDOUT


def evaluate() -> dict:
    model = ScenarioModel()
    data = pd.read_csv(SCENARIO_DATA_PATH)
    validate_messages(data)
    test = data[data.split == 'test']
    manual = pd.DataFrame([{'text': text, 'scenario_label': label, 'language': 'Hinglish'}
                           for label, messages in HINGLISH_HOLDOUT.items() for text in messages])
    generated_texts = set(data.text.str.casefold().str.strip())
    if any(text.casefold().strip() in generated_texts for text in manual.text):
        raise ValueError('Manual Hinglish holdout overlaps with generated corpus')
    report = {'selected_model': model.metadata['selected_model'],
              'test': evaluate_pipeline(model.pipeline, test),
              'manual_hinglish': evaluate_pipeline(model.pipeline, manual),
              'manual_holdout_used_for_training': False}
    predictions = model.pipeline.predict(manual.text)
    errors = [{'text': text, 'actual': actual, 'predicted': predicted}
              for text, actual, predicted in zip(manual.text, manual.scenario_label, predictions) if actual != predicted]
    report['manual_hinglish_errors'] = errors
    SCENARIO_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (SCENARIO_REPORT_DIR / 'saved_model_evaluation.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    manual.to_csv(SCENARIO_REPORT_DIR / 'manual_hinglish_holdout.csv', index=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


if __name__ == '__main__':
    evaluate()
