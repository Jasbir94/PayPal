from backend.app.fusion.decision_policy import recommend

def test_high_risk_uses_step_up_or_block_based_on_confidence():
    assert recommend(92,.9,3)=='BLOCK_AND_ESCALATE'
    assert recommend(75,.5,2)=='STEP_UP_VERIFICATION'

def test_sparse_uncertain_case_is_not_silently_allowed():
    assert recommend(34,.3,1)=='WARN_AND_REVIEW'

def test_established_low_risk_merchant_case_can_be_allowed():
    assert recommend(12,.9,3)=='ALLOW'
