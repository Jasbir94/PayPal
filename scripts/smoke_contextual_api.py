"""Exercise the running contextual endpoint with optional text and legitimate counterexamples."""
import json
from time import perf_counter
from urllib.request import Request, urlopen
from backend.app.config.context_config import SCENARIO_REPORT_DIR

SUSPICIOUS_PAYMENT = dict(sender_id='A0001', receiver_id='A1006', amount=85000,
    timestamp='2026-01-30T23:31:50+00:00', device_id='D0001', payment_type='bank_transfer')
NORMAL_PAYMENT = dict(sender_id='A0242', receiver_id='A0928', amount=2381.48,
    timestamp='2026-01-30T23:31:49+00:00', device_id='D0242', payment_type='bank_transfer')


def post(path: str, payload: dict) -> tuple[dict, float]:
    body = json.dumps(payload).encode('utf-8')
    start = perf_counter()
    with urlopen(Request('http://127.0.0.1:8000' + path, data=body,
                         headers={'Content-Type': 'application/json'}), timeout=20) as response:
        result = json.load(response)
    return result, (perf_counter() - start) * 1000


def main() -> None:
    government = dict(transaction=SUSPICIOUS_PAYMENT, context=dict(payment_reason='government',
        contacted_by_unknown_person=True, contact_channel='phone', claimed_authority=True,
        authority_type='police', urgent_payment_requested=True, threatened_consequences=True,
        requested_secrecy=True, fund_transfer_requested=True),
        message='Cyber Crime Department said my Aadhaar was involved in money laundering. Transfer the funds immediately to avoid legal action.')
    investment = dict(transaction=NORMAL_PAYMENT, context=dict(payment_reason='investment',
        contacted_by_unknown_person=False, promised_profit=False, guaranteed_returns_promised=False,
        urgent_payment_requested=False, threatened_consequences=False),
        message='I voluntarily pay my registered investment fund. There are no guaranteed returns or urgent instructions.')
    job_without_text = dict(transaction=SUSPICIOUS_PAYMENT, context=dict(payment_reason='job',
        contacted_by_unknown_person=True, asked_to_pay_fee=True))
    examples = {}
    for name, request in (('government', government), ('legitimate_investment', investment), ('job_without_text', job_without_text)):
        result, latency = post('/api/v1/risk/contextual', request)
        examples[name] = {'request': request, 'response': result, 'latency_ms': latency}
    assert examples['government']['response']['scenario']['type'] == 'government_impersonation'
    assert examples['government']['response']['risk_level'] == 'CRITICAL'
    assert examples['government']['response']['context_risk']['score'] >= 80
    assert examples['legitimate_investment']['response']['context_risk']['score'] == 0
    assert examples['legitimate_investment']['response']['risk_level'] != 'CRITICAL'
    assert examples['job_without_text']['response']['scenario']['type'] == 'fake_job_scam'
    day2, _ = post('/api/v1/risk/preliminary', SUSPICIOUS_PAYMENT)
    assert 'preliminary_risk' in day2 and 'extended_preliminary_risk' not in day2
    report = {'examples': examples, 'day2_endpoint_compatible': True,
              'latency_note': 'Single localhost HTTP measurements include transport and are not a production benchmark'}
    SCENARIO_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (SCENARIO_REPORT_DIR / 'contextual_api_examples.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    for name, example in examples.items():
        response = example['response']
        print(f"{name}: scenario={response['scenario']['type']}, context={response['context_risk']['score']}, "
              f"extended={response['extended_preliminary_risk']}, level={response['risk_level']}, "
              f"latency={example['latency_ms']:.1f} ms")
    print('Day 2 preliminary endpoint remains compatible')


if __name__ == '__main__':
    main()
