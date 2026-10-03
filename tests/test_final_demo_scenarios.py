from evaluation.flagship_experiments import run


def test_all_five_final_demo_cases_use_the_real_simulator(tmp_path):
    report=run(tmp_path/'demo_scenario_results.json')
    assert len(report['cases'])==5
    by_name={case['case']:case for case in report['cases']}
    assert by_name['government_impersonation']['transaction_only_risk'] is not None
    assert by_name['large_legitimate_purchase']['full_app_shield_risk'] is not None
    assert by_name['small_initial_investment']['scenario']=='investment_scam'
    assert by_name['mule_network']['recipient_risk'] is not None
    assert by_name['legitimate_family_emergency']['decision'] not in ('BLOCK_AND_ESCALATE','STEP_UP_VERIFICATION')
