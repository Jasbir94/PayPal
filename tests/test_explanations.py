from backend.app.fusion.explanation import rank_reasons
from backend.app.fusion.evidence import canonicalize

def test_explanations_include_cross_layer_and_protective_items():
    rows=rank_reasons(canonicalize(['first_time_recipient']),
        {'patterns':['new_recipient_authority_scam_pattern']},
        {'items':['KNOWN_RECIPIENT_LONG_TERM']}, {})
    assert rows[0]['evidence_family']=='cross_layer'
    assert any(row['code']=='TX_NEW_RECIPIENT' for row in rows)
    assert any(row['impact']=='risk_reducing' for row in rows)
