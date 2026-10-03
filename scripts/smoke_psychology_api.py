"""Verify the running Day 4 API and preserve complete request/response examples."""
import json
from backend.app.config.psychology_config import PSYCHOLOGY_REPORT_DIR
from scripts.smoke_contextual_api import post, SUSPICIOUS_PAYMENT
CASES = [
    ('I am from police. Transfer now or you will be arrested.', {'authority', 'fear', 'urgency'}),
    ('Guaranteed 30% return. Only two slots remain. Invest today.', {'reward', 'scarcity', 'urgency'}),
    ('Do not tell your bank or family. This investigation is confidential.', {'secrecy'}),
    ('If you really care about me, please send money for my emergency.', {'trust', 'emotional_pressure'}),
    ('Main RBI se bol raha hu. Abhi transfer karo warna account freeze ho jayega.', {'authority', 'urgency', 'fear'}),
    ('Sir ye investment guaranteed hai, aaj last opportunity hai.', {'reward', 'scarcity', 'urgency'}),
    ('Kisi ko mat batana, ye confidential police investigation hai.', {'secrecy', 'authority'}),
    ("You've already invested 50000. Pay 10000 more to unlock withdrawal.", {'commitment'}),
    ('Thousands of users have already earned profits.', {'social_proof'}),
]

def main():
    examples = {}
    for index, (message, expected) in enumerate(CASES):
        payload = {'message': message}
        response, latency = post('/api/v1/analyze/psychology', payload)
        assert expected <= set(response['detected_techniques'])
        examples[f'techniques_{index + 1}'] = {'request': payload, 'response': response, 'latency_ms': latency}
    for index, message in enumerate([
        'RBI announced a new policy today.', 'My bank account is frozen.',
        'Your bank statement for September is available.', 'Your electricity bill is due tomorrow.',
        'Please make the payment today if convenient.']):
        response, latency = post('/api/v1/analyze/psychology', {'message': message})
        assert response['psychology_risk'] < 30
        examples[f'neutral_{index + 1}'] = {'request': {'message': message}, 'response': response, 'latency_ms': latency}
    message = 'I am from Cyber Crime. Your Aadhaar is involved in money laundering. Transfer 80000 immediately or you will be arrested. Do not tell anyone.'
    payload = {'transaction': SUSPICIOUS_PAYMENT, 'context': {
        'payment_reason': 'government', 'contacted_by_unknown_person': True,
        'contact_channel': 'phone', 'claimed_authority': True, 'authority_type': 'police',
        'urgent_payment_requested': True, 'threatened_consequences': True,
        'requested_secrecy': True, 'fund_transfer_requested': True}, 'message': message}
    response, latency = post('/api/v1/risk/contextual', payload)
    assert response['scenario']['type'] == 'government_impersonation'
    assert response['psychology']['psychology_risk'] >= 90
    assert response['scenario_psychology_alignment'] >= .75
    examples['full_contextual'] = {'request': payload, 'response': response, 'latency_ms': latency}
    missing, _ = post('/api/v1/risk/contextual', dict(transaction=SUSPICIOUS_PAYMENT, context={}))
    assert missing['extended_risk'] == missing['extended_preliminary_risk']
    legacy, _ = post('/api/v1/risk/preliminary', SUSPICIOUS_PAYMENT)
    assert 'psychology' not in legacy
    report = {'examples': examples, 'missing_message_preserves_day3': True,
              'day2_endpoint_compatible': True,
              'latency_note': 'Single localhost requests include transport; not production benchmarks.'}
    PSYCHOLOGY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (PSYCHOLOGY_REPORT_DIR / 'psychology_api_examples.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"Verified {len(examples)} live examples; psychology={response['psychology']['psychology_risk']}, "
          f"alignment={response['scenario_psychology_alignment']}, extended={response['extended_risk']}, "
          f"extended_level={response['extended_risk_level']}, legacy_level={response['risk_level']}")

if __name__ == '__main__':
    main()
