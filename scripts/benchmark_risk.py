"""Measure warmed local API pipeline latency and save a reproducible example."""
import json
from time import perf_counter
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config.risk_config import REPORT_DIR


def main() -> None:
    with TestClient(app) as client:
        if client.get('/ready').status_code != 200:
            raise RuntimeError('Train both models before benchmarking')
        row = app.state.risk_service.repository.transactions.iloc[-1]
        payment = {key: (row[key].isoformat() if key == 'timestamp' else row[key])
                   for key in ('sender_id', 'receiver_id', 'amount', 'timestamp', 'device_id', 'payment_type')}
        for _ in range(5):
            client.post('/api/v1/risk/preliminary', json=payment).raise_for_status()
        samples = []
        for _ in range(30):
            start = perf_counter()
            response = client.post('/api/v1/risk/preliminary', json=payment)
            response.raise_for_status()
            samples.append((perf_counter() - start) * 1000)
        repository = app.state.risk_service.repository
        timestamp = repository.end + pd.Timedelta(seconds=1)
        candidates = repository.accounts[repository.accounts.is_suspicious].account_id
        receiver = max(candidates, key=lambda account_id:
            app.state.risk_service.recipient.score_recipient(account_id, timestamp)['score'])
        sender = 'A0001'
        sender_history = repository.sender_history(sender, timestamp)
        average = float(sender_history.amount.mean()) if len(sender_history) else float(
            repository.account(sender)['average_transaction_amount'])
        suspicious_payment = dict(sender_id=sender, receiver_id=receiver, amount=round(average * 30, 2),
            timestamp=timestamp.isoformat(), device_id=repository.account(sender)['usual_device'], payment_type='bank_transfer')
        suspicious = client.post('/api/v1/risk/preliminary', json=suspicious_payment)
        suspicious.raise_for_status()
        report = {'suspicious_request': suspicious_payment, 'suspicious_response': suspicious.json(), 'method': '30 warm FastAPI TestClient requests, excludes startup and network transport',
                  'median_ms': float(np.median(samples)), 'p95_ms': float(np.percentile(samples, 95)),
                  'mean_ms': float(np.mean(samples)), 'request': payment, 'response': response.json()}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / 'latency_and_example.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
