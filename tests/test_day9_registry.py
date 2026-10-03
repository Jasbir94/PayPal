import pytest
from ml.retraining.registry import RegistryError,promotion_checks,promote,save_registry


def test_promotion_requires_explicit_approval_and_fingerprinted_same_holdout(tmp_path):
    path=tmp_path/'registry.json'
    registry={'models':{'fusion':{'active_version':'champion','versions':{
        'champion':{'status':'ACTIVE','metrics':{'pr_auc':.7,'recall':.7,'false_positive_rate':.01,'brier':.1,'scenario_regressions':[],'hard_negative_fpr':.01}},
        'candidate':{'status':'CHALLENGER','metrics':None}}}},
        'promotion_policy':{'minimum_pr_auc_delta':-.01,'minimum_recall_delta':-.02,
            'maximum_false_positive_rate':.05,'maximum_brier_delta':.02,'maximum_hard_negative_fpr':.05}}
    save_registry(registry,path)
    with pytest.raises(RegistryError):promote('candidate',False,path=path)
    comparison={'active_version':'champion','candidate_version':'candidate','same_holdout':True,
        'holdout_fingerprint':'abc','active_metrics':registry['models']['fusion']['versions']['champion']['metrics'],
        'challenger_metrics':{'pr_auc':.71,'recall':.72,'false_positive_rate':.02,'brier':.11,
            'scenario_regressions':[],'hard_negative_fpr':.01}}
    result=promote('candidate',True,comparison,path)
    assert result['active_version']=='candidate'


def test_promotion_rejects_missing_scenario_and_hard_negative_checks():
    policy={'minimum_pr_auc_delta':0,'minimum_recall_delta':0,'maximum_false_positive_rate':.05,
        'maximum_brier_delta':.02,'maximum_hard_negative_fpr':.05}
    checks=promotion_checks({'metrics':{'pr_auc':1,'recall':1,'false_positive_rate':0,'brier':.1}},
        {'metrics':{'pr_auc':.5,'recall':.5,'brier':.1}},policy)
    assert checks['eligible'] is False
