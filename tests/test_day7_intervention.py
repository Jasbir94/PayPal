from backend.app.intervention.intervention_service import build_intervention


def test_specific_intervention_requires_context_supported_scenario_risk():
    unsupported=build_intervention('STEP_UP_VERIFICATION','government_impersonation',{'scenario':19.9})
    supported=build_intervention('STEP_UP_VERIFICATION','government_impersonation',{'scenario':20})
    assert unsupported['type']=='GENERAL_PAYMENT_CAUTION'
    assert supported['type']=='GOVERNMENT_IMPERSONATION_WARNING'
    assert 'safe account' in supported['message']
    assert 'threshold' not in supported['message'].lower()


def test_allow_message_is_calm_and_level_zero():
    message=build_intervention('ALLOW','normal_or_unknown',{})
    assert message['level']==0
    assert message['type']=='NO_INTERVENTION'
