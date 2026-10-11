from backend.app.fusion.decision_policy import recommend

def test_high_risk_uses_step_up_or_block_based_on_confidence():
    assert recommend(92,.9,3)=='BLOCK_AND_ESCALATE'
    assert recommend(75,.5,2)=='STEP_UP_VERIFICATION'

def test_sparse_uncertain_case_is_not_silently_allowed():
    assert recommend(34,.3,1)=='WARN_AND_REVIEW'

def test_established_low_risk_merchant_case_can_be_allowed():
    assert recommend(12,.9,3)=='ALLOW'

def test_urgency_alone_does_not_force_a_scam_warning():
    assert recommend(12,.9,3,context={'urgent_payment_requested':True,
        'contacted_by_unknown_person':False})=='ALLOW'

def test_authority_claim_with_pressure_requires_step_up_even_when_contact_is_uncertain():
    assert recommend(8,.9,3,context={'claimed_authority':True,
        'contacted_by_unknown_person':None,'urgent_payment_requested':True})=='STEP_UP_VERIFICATION'

def test_guaranteed_returns_and_unknown_job_fee_cannot_be_calibrated_away():
    assert recommend(5,.9,3,context={'guaranteed_returns_promised':True})=='WARN_AND_REVIEW'
    assert recommend(5,.9,3,context={'asked_to_pay_fee':True,
        'contacted_by_unknown_person':True})=='WARN_AND_REVIEW'

def test_remote_access_and_mule_network_require_review():
    assert recommend(5,.9,3,context={'asked_to_install_remote_access':True})=='STEP_UP_VERIFICATION'
    assert recommend(5,.9,3,reason_codes={'NETWORK_MULE_CONNECTION'})=='WARN_AND_REVIEW'
    assert recommend(5,.9,3,reason_codes={'RECIPIENT_PRIOR_REPORTS'})=='WARN_AND_REVIEW'

def test_unknown_urgent_contact_gets_review_without_labeling_it_a_scam():
    assert recommend(5,.9,3,context={'contacted_by_unknown_person':True,
        'urgent_payment_requested':True})=='WARN_AND_REVIEW'
