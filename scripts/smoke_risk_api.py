"""Verify the running localhost API and measure end-to-end HTTP latency."""
import json
from time import perf_counter
from urllib.request import Request, urlopen
import numpy as np
from backend.app.config.risk_config import REPORT_DIR


def main() -> None:
    example = json.loads((REPORT_DIR / 'latency_and_example.json').read_text(encoding='utf-8'))
    body = json.dumps(example['suspicious_request']).encode('utf-8')
    url = 'http://127.0.0.1:8000/api/v1/risk/preliminary'
    with urlopen('http://127.0.0.1:8000/ready', timeout=10) as ready:
        assert json.load(ready)['status'] == 'ready'
    samples = []
    result = None
    for index in range(25):
        start = perf_counter()
        with urlopen(Request(url, data=body, headers={'Content-Type': 'application/json'}), timeout=10) as response:
            result = json.load(response)
        if index >= 5:
            samples.append((perf_counter() - start) * 1000)
    assert result['risk_level'] == 'CRITICAL', result
    report = {'method': '20 warmed localhost HTTP requests; startup excluded; transport included',
              'median_ms': float(np.median(samples)), 'p95_ms': float(np.percentile(samples, 95)),
              'mean_ms': float(np.mean(samples)), 'request': example['suspicious_request'], 'response': result}
    (REPORT_DIR / 'http_smoke.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
