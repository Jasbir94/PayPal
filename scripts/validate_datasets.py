"""Audit local APP Shield datasets and write a machine-readable validation report."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.data_validation import audit_repository


def main() -> None:
    report = audit_repository(ROOT)
    output = ROOT / 'reports' / 'dataset_validation.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + '\n',
                      encoding='utf-8', newline='\n')
    print(json.dumps({'output': output.relative_to(ROOT).as_posix(),
        'files_inventoried': len(report['inventory']),
        'frozen_benchmark_hashes_valid': all(report['frozen_benchmark']['canonical_hashes_valid'].values()),
        'leakage_checks': report['leakage_checks'], 'findings': report['findings']},
        indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
