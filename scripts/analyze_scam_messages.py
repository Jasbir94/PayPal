"""Print and save scenario corpus integrity, diversity and split-overlap checks."""
import json
import pandas as pd
from backend.app.config.context_config import SCENARIO_DATA_PATH, SCENARIO_REPORT_DIR
from ml.scenario.data_quality import validate_messages


def main() -> None:
    report = validate_messages(pd.read_csv(SCENARIO_DATA_PATH))
    SCENARIO_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (SCENARIO_REPORT_DIR / 'dataset_quality.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
