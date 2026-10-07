from backend.app.fusion.evidence import canonicalize
from backend.app.fusion.grouping import group_signals
from backend.app.fusion.cross_layer_rules import score_cross_layer
from backend.app.fusion.protective_evidence import assess_protective_evidence, apply_protective_evidence

def test_overlapping_reasons_are_canonicalized_once():
    result = canonicalize(['first_time_recipient', 'new_recipient', 'unknown_contact', 'authority_claim'])
    ids = [row['id'] for row in result]
    assert ids.count('TX_NEW_RECIPIENT') == 1
    assert ids.count('CTX_UNKNOWN_CONTACT') == 1

def test_missing_modules_are_renormalized_and_high_manipulation_stands_alone():
    tx={'score':10,'confidence':.8,'available':True}
    absent={'score':None,'confidence':0,'available':False}
    context={'score':85,'confidence':.8,'available':True}
    scenario={'score':70,'confidence':.5,'available':True}
    psychology={'score':90,'confidence':.8,'available':True}
    groups, score, weights=group_signals(tx,absent,absent,context,scenario,psychology,.8)
    assert groups['recipient_side']['available'] is False
    assert groups['manipulation_side']['score'] >= 70
    assert score > 50

def test_small_amount_social_engineering_pattern_gets_cross_layer_support():
    tx={'score':5,'evidence':{'first_time_recipient':1}}
    recipient={'score':65}
    graph={'score':10}
    context={'evidence':{'contacted_by_unknown_person':True,'urgent_payment_requested':True,
                         'guaranteed_returns_promised':True}}
    scenario={'type':'investment_scam'}
    psychology={'detected_techniques':['reward','urgency']}
    result=score_cross_layer(tx,recipient,graph,context,scenario,psychology)
    assert result['bonus']>0
    assert 'new_recipient_guaranteed_investment_pattern' in result['patterns']

def test_observed_legitimate_relationship_reduces_risk():
    tx={'evidence':{'recipient_seen_before':True,'prior_payments_to_recipient':5,
                    'baseline_available':1,'amount_ratio':1.1}}
    recipient={'evidence':{'account_age_days':900}}
    context={'available':True,'evidence':{'contacted_by_unknown_person':False,
        'urgent_payment_requested':False,'threatened_consequences':False,'claimed_authority':False,
        'requested_secrecy':False,'asked_to_install_remote_access':False}}
    protective=assess_protective_evidence(tx,recipient,context)
    assert protective['reduction']>0
    assert apply_protective_evidence(50,protective)<50

def test_old_recipient_account_alone_is_not_trusted_relationship_evidence():
    tx={'evidence':{'recipient_seen_before':False,'prior_payments_to_recipient':0}}
    recipient={'evidence':{'account_age_days':900}}
    protective=assess_protective_evidence(tx,recipient,{'available':False,'evidence':{}})
    assert 'ESTABLISHED_RECIPIENT_ACCOUNT' not in protective['items']
    assert protective['reduction']==0

def test_integer_relationship_evidence_from_feature_pipeline_is_recognized():
    protective=assess_protective_evidence(
        {'evidence':{'recipient_seen_before':1}},
        {'evidence':{'account_age_days':900}},
        {'available':False,'evidence':{}})
    assert 'KNOWN_RECIPIENT_LONG_TERM' in protective['items']
    assert 'ESTABLISHED_RECIPIENT_ACCOUNT' in protective['items']
