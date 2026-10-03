"""Narrative rules, real NLP inference, template leakage and risk/confidence separation."""
import pandas as pd
import pytest
from backend.app.models.scenario_model import ScenarioModel
from backend.app.schemas.context import PaymentContext
from backend.app.services.scenario_service import ScenarioService, calculate_scenario_risk
from backend.app.utils.scenario_labels import get_scenario_labels
from backend.app.config.context_config import SCENARIO_DATA_PATH
from ml.scenario.data_quality import validate_messages
from scripts.generate_scam_messages import generate_messages


@pytest.fixture(scope='module')
def scenario_service():
    return ScenarioService(ScenarioModel())


@pytest.mark.parametrize('context,expected', [
    (dict(payment_reason='government', claimed_authority=True, authority_type='police', threatened_consequences=True), 'government_impersonation'),
    (dict(payment_reason='bank_support', claimed_authority=True, authority_type='bank', fund_transfer_requested=True), 'bank_impersonation'),
    (dict(payment_reason='investment', promised_profit=True, contacted_by_unknown_person=True), 'investment_scam'),
    (dict(payment_reason='job', asked_to_pay_fee=True), 'fake_job_scam'),
    (dict(payment_reason='tech_support', asked_to_install_remote_access=True, fund_transfer_requested=True), 'tech_support_scam'),
    (dict(payment_reason='romance', online_relationship=True, urgent_payment_requested=True), 'romance_scam'),
    (dict(payment_reason='family', urgent_payment_requested=True, contacted_by_unknown_person=True), 'family_emergency_scam'),
    (dict(payment_reason='marketplace', fund_transfer_requested=True, contacted_by_unknown_person=True), 'marketplace_scam'),
    (dict(payment_reason='loan', asked_to_pay_fee=True), 'loan_scam'),
    (dict(payment_reason='refund', fund_transfer_requested=True), 'refund_scam'),
    (dict(payment_reason='family'), 'normal_or_unknown'),
])
def test_rule_only_taxonomy(context, expected):
    result = ScenarioService().predict_scenario(None, PaymentContext(**context))
    assert result['type'] == expected
    assert len(result['top_scenarios']) == 3
    assert result['reason_codes']
    assert all(item['scenario'] in get_scenario_labels() for item in result['top_scenarios'])


def test_text_plus_authority_context(scenario_service):
    context = PaymentContext(payment_reason='government', contacted_by_unknown_person=True,
        claimed_authority=True, authority_type='police', urgent_payment_requested=True, threatened_consequences=True)
    result = scenario_service.predict_scenario('Police said my Aadhaar is linked to money laundering and demanded an immediate transfer.', context)
    assert result['type'] == 'government_impersonation'
    assert 0 <= result['confidence'] <= 1
    assert len(result['top_scenarios']) == 3
    assert result['evidence']['text_model_available']
    assert 'text_classifier_evidence' in result['reason_codes']


def test_text_normal_and_out_of_vocabulary(scenario_service):
    result = scenario_service.predict_scenario('I am sending money for family groceries to the account we always use. No stranger contacted me.', PaymentContext())
    assert result['type'] == 'normal_or_unknown'
    unknown = scenario_service.predict_scenario('zzqxxvv ppqqzzzx', PaymentContext())
    assert unknown['type'] == 'normal_or_unknown'


def test_context_only_with_model_available(scenario_service):
    result = scenario_service.predict_scenario(None, PaymentContext(payment_reason='job', asked_to_pay_fee=True,
                                                                   contacted_by_unknown_person=True))
    assert result['type'] == 'fake_job_scam'
    assert result['confidence_kind'] == 'structured_rule_evidence'


def test_confidence_is_not_fraud_risk():
    assert calculate_scenario_risk('normal_or_unknown', .99, PaymentContext())['score'] == 0
    assert calculate_scenario_risk('investment_scam', .99, PaymentContext(payment_reason='investment',
        contacted_by_unknown_person=False, promised_profit=False))['score'] == 0
    assert calculate_scenario_risk('government_impersonation', .99, PaymentContext())['score'] == 0
    context = PaymentContext(payment_reason='government', contacted_by_unknown_person=True,
        claimed_authority=True, threatened_consequences=True, urgent_payment_requested=True)
    assert calculate_scenario_risk('government_impersonation', .9, context)['score'] >= 60


def test_missing_model_uses_rules_and_discloses_fallback():
    result = ScenarioService().predict_scenario('My recruiter wants a registration fee',
        PaymentContext(payment_reason='job', asked_to_pay_fee=True))
    assert result['type'] == 'fake_job_scam'
    assert 'text_model_unavailable_rule_fallback' in result['reason_codes']


def test_disjoint_and_nontrivial_corpus():
    data = pd.read_csv(SCENARIO_DATA_PATH)
    report = validate_messages(data)
    assert report['rows'] >= 5000
    assert min(report['classes'].values()) >= 300
    assert report['train_test_message_overlap'] == 0
    assert report['train_test_template_overlap'] == 0
    assert set(data.language) == {'English', 'Hinglish'}
    assert report['average_text_length'] > 80
    bad = data.copy()
    family = bad.template_id.iloc[0]
    indices = bad.index[bad.template_id == family][:2]
    bad.loc[indices, 'split'] = ['train', 'test']
    with pytest.raises(ValueError, match='Template-family leakage'):
        validate_messages(bad)


def test_generator_is_reproducible():
    pd.testing.assert_frame_equal(generate_messages(samples_per_template=2), generate_messages(samples_per_template=2))


@pytest.mark.parametrize('context,text,expected', [
    (dict(payment_reason='investment', contacted_by_unknown_person=True, contact_channel='social_media', promised_profit=True),
     'This new advisor guarantees twenty percent every month if I transfer an initial investment.', 'investment_scam'),
    (dict(payment_reason='job', asked_to_pay_fee=True, contacted_by_unknown_person=True),
     'The recruiter offered work after I pay five thousand rupees for registration and security.', 'fake_job_scam'),
    (dict(payment_reason='tech_support', asked_to_install_remote_access=True, fund_transfer_requested=True, contacted_by_unknown_person=True),
     'An unknown support caller wants remote access to my screen and then a money transfer.', 'tech_support_scam'),
])
def test_required_structured_plus_text_examples(scenario_service, context, text, expected):
    result = scenario_service.predict_scenario(text, PaymentContext(**context))
    assert result['type'] == expected


def test_strong_structured_evidence_survives_conflicting_text():
    class ConflictingTextModel:
        def predict(self, text):
            labels = get_scenario_labels()
            return {'scores': {label: float(label == 'tech_support_scam') for label in labels},
                    'scenario': 'tech_support_scam', 'support_terms': ['remote access'], 'confidence_kind': 'test_evidence'}
    context = PaymentContext(payment_reason='investment', promised_profit=True, contacted_by_unknown_person=True)
    result = ScenarioService(ConflictingTextModel()).predict_scenario('remote repair message', context)
    assert result['type'] == 'investment_scam'
    assert 'text_context_disagreement' in result['reason_codes']
