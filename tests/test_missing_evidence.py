from backend.app.fusion.grouping import group_signals
from backend.app.fusion.protective_evidence import assess_protective_evidence

def test_sparse_signal_availability_does_not_treat_missing_as_safe():
    tx={'score':60,'confidence':.5,'available':True}
    missing={'score':None,'confidence':0,'available':False}
    context={'score':0,'confidence':0,'available':False}
    scenario={'score':0,'confidence':0,'available':False}
    psych={'score':0,'confidence':0,'available':False}
    groups,score,_=group_signals(tx,missing,missing,context,scenario,psych)
    assert score==60
    assert groups['recipient_side']['available'] is False
    protective=assess_protective_evidence({'evidence':{}},{'evidence':{}},context)
    assert protective['reduction']==0
