"""Convenience entry point for the held-out fusion ablation report."""
import json
from ml.fusion.evaluate import evaluate

if __name__ == '__main__':
    report = evaluate()
    print(json.dumps(report['ablations'], indent=2))
