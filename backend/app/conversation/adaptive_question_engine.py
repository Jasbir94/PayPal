"""Backend-owned, low-friction selection of one useful missing-evidence question."""

QUESTIONS={
 'contacted_by_unknown_person':('Did someone you do not know ask you to make this payment?',
     'Clarifies whether an unfamiliar person initiated this payment.'),
 'promised_profit':('Did anyone promise guaranteed or unusually high returns?',
     'Clarifies whether this may involve an investment-return promise.'),
 'asked_to_pay_fee':('Are you being asked to pay a fee to get a job or benefit?',
     'Clarifies whether an advance-fee pattern may be present.'),
 'urgent_payment_requested':('Did they tell you to act immediately or threaten a consequence?',
     'Clarifies pressure signals relevant to the current recipient and payment.'),
}

def select_critical_questions(*,payment_reason,passive_risk,previously_asked=(),max_questions=1):
    """Use documented relevance heuristics; scores are ranks, not information-gain claims."""
    reason=str(payment_reason or 'other')
    if reason=='investment': candidates=['promised_profit','contacted_by_unknown_person','urgent_payment_requested']
    elif reason=='job': candidates=['asked_to_pay_fee','contacted_by_unknown_person','urgent_payment_requested']
    elif reason in ('government','bank_support'): candidates=['contacted_by_unknown_person','urgent_payment_requested']
    else: candidates=['contacted_by_unknown_person','urgent_payment_requested']
    if passive_risk in ('HIGH','CRITICAL') and candidates[0]!='urgent_payment_requested':
        candidates.insert(1,'urgent_payment_requested')
    selected=[]
    for question_id in candidates:
        if question_id in previously_asked:continue
        label,reason_for_question=QUESTIONS[question_id]
        selected.append({'id':question_id,'label':label,'question':label,
            'answer_options':['Yes','No','Not sure'],'reason_for_question':reason_for_question,
            'expected_information_gain':None})
        if len(selected)>=max(1,min(3,int(max_questions))):break
    primary=selected[0] if selected else {}
    return {'ask_question':bool(selected),'questions':selected,
        'question_id':primary.get('id'),'question':primary.get('question'),
        'answer_options':primary.get('answer_options',[]),
        'reason_for_question':primary.get('reason_for_question'),
        'expected_information_gain':None,
        'reason':'Selected by payment-purpose relevance and backend passive risk; no model information-gain estimate is claimed.'}
