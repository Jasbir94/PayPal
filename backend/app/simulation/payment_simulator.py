"""Local-only simulated payment attempts routed through the existing APP Shield core."""
from collections import Counter
from datetime import timedelta
from threading import RLock
from time import perf_counter
from uuid import uuid4
import hashlib
import json
import re
import pandas as pd
from fastapi import HTTPException
from backend.app.schemas.context import PaymentContext
from backend.app.services.fraud_engine import FraudEngine
from backend.app.simulation.payment_state import PaymentState, transition, InvalidPaymentTransition
from backend.app.graph.graph_features import calculate_graph_features
from backend.app.features.recipient_features import calculate_account_age
from backend.app.conversation.adaptive_question_engine import select_critical_questions
from backend.app.fusion.evidence_consistency_engine import (
    build_evidence_records, compare_claims, evidence_record,
)

_CREDENTIAL_VALUE = re.compile(
    r'(?i)\b(?:otp|pin|cvv|cvc)\s*[:=]\s*[A-Za-z0-9-]{3,}|'
    r'\bpassword\s*(?::|=|is)\s*\S{4,}|(?<!\d)(?:\d[ -]?){13,19}(?!\d)')
_REASON_MAP={'marketplace':'shopping','emergency':'family','tech_support':'bank_support'}


class PaymentSimulator:
    """Bounded in-memory simulator. It never calls an external payment provider."""
    MAX_ATTEMPTS=500

    def __init__(self, risk_service, feedback_service=None, review_service=None):
        self.risk=risk_service
        self.engine=FraudEngine(risk_service)
        self.feedback=feedback_service
        self.review=review_service
        self.banking_service=None
        self._lock=RLock()
        self._attempts={}
        self._idempotency={}
        self._scenario_data,self._accounts=self._build_demo_catalog()

    def _build_demo_catalog(self):
        repo=self.risk.repository
        tx=repo.transactions
        sender_counts=tx.sender_id.value_counts()
        # Stable synthetic profiles provide representative baseline behavior for
        # the demo: regular payment history and a known device. All risk results
        # still come from the actual models at runtime.
        preferred=['A0069','A0361','A0191']
        sender_ids=[account for account in preferred if account in repo.accounts.index and account in sender_counts.index]
        for account in sender_counts.index:
            if len(sender_ids)>=3: break
            if str(account) not in sender_ids: sender_ids.append(str(account))
        while len(sender_ids)<3: sender_ids.append(str(repo.accounts.account_id.iloc[len(sender_ids)]))
        senders={}
        for index,account_id in enumerate(sender_ids):
            profile=repo.account(account_id)
            senders[f'U{101+index}']={'account_id':account_id,'display_name':['Alex Morgan','Riya Sen','Sam Patel'][index],
                'device_id':str(profile['usual_device']),'typical_amount':float(profile['average_transaction_amount'])}

        counts=tx.receiver_id.value_counts()
        first_sender=senders['U101']['account_id']
        prior=set(tx.loc[tx.sender_id==first_sender,'receiver_id'].astype(str))
        familiar=next((str(row.receiver_id) for row in tx[tx.sender_id==first_sender].itertuples()
                       if str(row.receiver_id) in repo.accounts.index),None)
        all_accounts=set(repo.accounts.index.astype(str))
        activity=set(tx.sender_id.astype(str))|set(tx.receiver_id.astype(str))
        quiet=sorted(all_accounts-activity)
        known_receiver=next((str(account_id) for account_id in counts.index
            if str(account_id) not in prior and not bool(repo.accounts.loc[account_id,'is_known_mule'])
            and not bool(repo.accounts.loc[account_id,'is_suspicious'])), familiar)
        merchant=next((str(account_id) for account_id in counts.index
            if str(account_id)!=familiar and not bool(repo.accounts.loc[account_id,'is_known_mule'])
            and not bool(repo.accounts.loc[account_id,'is_suspicious'])),known_receiver)
        suspicious=next((str(account_id) for account_id in repo.accounts.index
                         if bool(repo.accounts.loc[account_id,'is_suspicious'])),known_receiver)
        mule=next((str(account_id) for account_id in repo.accounts.index
                   if bool(repo.accounts.loc[account_id,'is_known_mule'])), suspicious)
        raw_recipients=[familiar or known_receiver,merchant,known_receiver,
            suspicious,mule,quiet[0] if quiet else suspicious]
        recipient_aliases=['R201','R202','R203','R204','R205','R206']
        labels=['Known friend','Established merchant','New recipient','Limited history','New contact','Another new recipient']
        raw_recipients.append(senders['U102']['account_id'])
        recipient_aliases.append('R207')
        labels.append(senders['U102']['display_name'])
        recipients={alias:{'account_id':str(account_id),'display_name':label}
                    for alias,account_id,label in zip(recipient_aliases,raw_recipients,labels)}
        accounts={'senders':[{'alias':alias,'display_name':v['display_name']} for alias,v in senders.items()],
          'recipients':[{'alias':alias,'account_id':v['account_id'],'display_name':v['display_name']} for alias,v in recipients.items()]}
        return {'senders':senders,'recipients':recipients},accounts

    @property
    def repository(self): return self.risk.repository

    def catalog(self):
        return {'environment':'SIMULATED PAYMENT ENVIRONMENT — no real money moves',**self._accounts}

    def scenarios(self):
        return [{'id':item['id'],'title':item['title'],'description':item['description'],
                 'difficulty':item['difficulty']} for item in _SCENARIOS]

    def scenario(self, scenario_id):
        item=next((entry for entry in _SCENARIOS if entry['id']==scenario_id),None)
        if item is None: raise HTTPException(404,'Demo scenario not found')
        return {k:v for k,v in item.items() if k!='id'} | {'scenario_id':item['id']}

    def create(self, request, *, wallet_account_id=None, payment_detail_version=1):
        self._safe_message(request.note)
        with self._lock:
            fingerprint=hashlib.sha256(json.dumps(
                request.model_dump(exclude={'idempotency_key'}),sort_keys=True,
                separators=(',',':')).encode('utf-8')).hexdigest()
            existing_id=self._idempotency.get(request.idempotency_key)
            if existing_id:
                existing=self._attempts[existing_id]
                if existing['request_fingerprint']!=fingerprint:
                    raise HTTPException(409,'This idempotency key was already used for a different payment request.')
                return self.user_view(existing),False
            if len(self._attempts)>=self.MAX_ATTEMPTS:
                evictable=next((key for key,item in self._attempts.items()
                    if item['state'] not in (PaymentState.ANALYZING.value,)),None)
                if evictable is None:
                    raise HTTPException(503,'The local attempt store is full; retry after an attempt finishes.')
                old=self._attempts.pop(evictable)
                self._idempotency.pop(old['idempotency_key'],None)
            sender=self._scenario_data['senders'].get(request.sender_alias)
            recipient=self._scenario_data['recipients'].get(request.recipient_alias)
            if sender is None or recipient is None: raise HTTPException(422,'Choose a listed simulated account.')
            if wallet_account_id is not None and sender['account_id']!=wallet_account_id:
                raise HTTPException(403,'This chat session cannot use a different sender account.')
            attempt_id=str(uuid4())
            reason=request.payment_reason
            context_reason=reason
            attempt={'payment_attempt_id':attempt_id,'idempotency_key':request.idempotency_key,
                'sender_alias':request.sender_alias,'sender_name':sender['display_name'],
                'sender_id':sender['account_id'],'recipient_alias':request.recipient_alias,
                'recipient_name':recipient['display_name'],'recipient_id':recipient['account_id'],
                'amount':float(request.amount),'currency':'INR','payment_reason':reason,
                'payment_detail_version':int(payment_detail_version),
                'note':request.note.strip(),
                'request_fingerprint':fingerprint,
                'context_reason':context_reason,'payment_type':request.payment_type,
                'device_id':sender['device_id'],'timestamp':(
                    self.repository.end.normalize()+pd.Timedelta(days=1,hours=12)).isoformat(),
                'wallet_account_id':wallet_account_id,'ledger_receipt':None,
                'state':PaymentState.DRAFT.value,'created_at':pd.Timestamp.now(tz='UTC').isoformat(),
                'passive':None,'assessment':None,'contextual_result':None,'context':None,'conversation_evidence':None,
                'context_questions':[],
                'user_action':None,'simulated_status':'NOT_EXECUTED','latency_ms':{},'verified':False,
                'verification_claimed':False,'evidence_records':[],
                'payment_fingerprint':None,'assessment_fingerprint':None}
            attempt['payment_fingerprint']=self._payment_fingerprint(attempt)
            self._attempts[attempt_id]=attempt
            self._idempotency[request.idempotency_key]=attempt_id
            if self.feedback:
                self.feedback.repository.append_audit(attempt_id,'PAYMENT_CREATED',{
                    'amount':attempt['amount'],'currency':attempt['currency'],
                    'sender_alias':attempt['sender_alias'],'recipient_alias':attempt['recipient_alias']})
            return self.user_view(attempt),True

    def _transaction(self, attempt):
        return {'transaction_id':attempt['payment_attempt_id'],'sender_id':attempt['sender_id'],
          'receiver_id':attempt['recipient_id'],'amount':attempt['amount'],'timestamp':attempt['timestamp'],
          'device_id':attempt['device_id'],'payment_type':attempt['payment_type'],
          'first_time_recipient':False,'payment_reason':_REASON_MAP.get(attempt['payment_reason'],attempt['payment_reason'])}

    @staticmethod
    def _payment_fingerprint(attempt):
        bound={key:attempt.get(key) for key in (
            'sender_id','recipient_id','amount','currency','payment_reason','payment_type',
            'note','payment_detail_version')}
        return hashlib.sha256(json.dumps(bound,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()

    @staticmethod
    def _safe_message(text):
        if _CREDENTIAL_VALUE.search(text or ''):
            raise HTTPException(422,'Do not enter passwords, PINs, OTPs, CVVs, or card credentials.')

    def analyze(self, attempt_id, request):
        for message in request.messages:
            self._safe_message(message.text)
        self._safe_message(request.context.user_message or '')
        with self._lock:
            attempt=self._get(attempt_id)
            state=PaymentState(attempt['state'])
            if state not in (PaymentState.DRAFT,PaymentState.CONTEXT_REQUIRED):
                raise HTTPException(409,f'Payment attempt cannot be analyzed from {state.value}.')
            if attempt['payment_fingerprint']!=self._payment_fingerprint(attempt):
                raise HTTPException(409,'Payment details changed; create a new attempt and run a fresh safety check.')
            initial=state==PaymentState.DRAFT
            if initial: transition(attempt,PaymentState.REVIEW)
            transition(attempt,PaymentState.ANALYZING)
        started=perf_counter()
        try:
            transaction=self._transaction(attempt)
            if initial:
                passive=self.risk.score(transaction)
                passive['graph_risk']=self.risk.graph.score_graph_risk(
                    attempt['recipient_id'],transaction['timestamp'],attempt['payment_attempt_id']) if self.risk.graph else None
                # Friction decision stays backend-owned and follows passive module
                # classifications plus first-recipient evidence; frontend has no thresholds.
                needs_context=(passive['risk_level']!='LOW' or
                    bool(passive['graph_risk'] and passive['graph_risk']['risk_level']!='LOW') or
                    bool(passive['transaction_details']['evidence'].get('first_time_recipient')))
                with self._lock:
                    attempt['passive']=passive
                    attempt['latency_ms']['passive_analysis_ms']=round((perf_counter()-started)*1000,3)
                    if self.feedback:
                        self.feedback.repository.append_audit(attempt_id,'PASSIVE_ANALYSIS_COMPLETED',{
                            'preliminary_risk':passive['preliminary_risk'],'risk_level':passive['risk_level'],
                            'graph_available':passive.get('graph_risk') is not None})
                if needs_context and not self._has_answers(request):
                    questions=self._targeted_questions(attempt,passive)
                    with self._lock:
                        transition(attempt,PaymentState.CONTEXT_REQUIRED)
                        attempt['context_questions']=questions
                        if self.feedback:
                            self.feedback.repository.append_audit(attempt_id,'CONTEXT_REQUESTED',{
                                'question_ids':[item['id'] for item in questions]})
                    return {'payment':self.user_view(attempt),'context_required':True,
                      'context_questions':questions}

            context_data=request.context.model_dump(mode='python')
            # A later, explicit context answer may clarify a purpose that was
            # initially unknown. It remains evidence, never payment authority.
            context_data['payment_reason']=(attempt['context_reason'] if context_data.get('payment_reason')=='other'
                else context_data['payment_reason'])
            context=PaymentContext.model_validate(context_data)
            if request.messages:
                conversation=self.risk.psychology
                from backend.app.services.conversation_service import ConversationService
                evidence=ConversationService(conversation).analyze(request.messages,attempt['amount'])
                message=evidence['analysis_message']
                attempt['conversation_evidence']={key:value for key,value in evidence.items()
                    if key not in ('analysis_message','turn_evidence')}
            else:
                message=context.user_message
            contextual=self.risk.score_contextual(transaction,context,message)
            assessment=self.engine.analyze_payment(transaction,context,message,contextual_result=contextual)
            try:
                history=self.repository.sender_history(attempt['sender_id'],pd.Timestamp(attempt['timestamp']),
                    attempt['payment_attempt_id'])
                history=history[history.receiver_id.astype(str)==str(attempt['recipient_id'])]
                history_available=True
            except (AttributeError,KeyError,ValueError):
                history=None;history_available=False
            consistency=compare_claims(payment_id=attempt_id,
                context=context.model_dump(mode='json'),history=history,
                backend_history_available=history_available)
            assessment['evidence_consistency']=consistency
            evidence_records=build_evidence_records(payment_id=attempt_id,transaction=transaction,
                context=context.model_dump(mode='json'),history=history,assessment=assessment,
                backend_history_available=history_available)
            elapsed=round((perf_counter()-started)*1000,3)
            # FraudEngine's own timer covers fusion only when supplied with a
            # precomputed contextual result. Report the complete stage-two time.
            assessment['latency_ms']=elapsed
            assessment['component_latency_ms']['full_engine']=elapsed
            decision=assessment['decision']
            final_state={
              'ALLOW':'READY','ALLOW_WITH_WARNING':'WARNING','WARN_AND_REVIEW':'WARNING',
              'STEP_UP_VERIFICATION':'VERIFICATION_REQUIRED','BLOCK_AND_ESCALATE':'SIMULATED_HELD'}[decision]
            with self._lock:
                attempt['assessment']=assessment
                attempt['contextual_result']=contextual
                attempt['context']=context.model_dump(mode='json')
                attempt['evidence_records']=evidence_records
                attempt['assessment_fingerprint']=attempt['payment_fingerprint']
                attempt['latency_ms']['full_analysis_ms']=elapsed
                attempt['latency_ms']['end_to_end_analysis_ms']=round(
                    attempt['latency_ms'].get('passive_analysis_ms',0)+elapsed,3)
                transition(attempt,PaymentState(final_state))
                if self.feedback:
                    self.feedback.record_prediction(attempt,attempt['passive'] or {},assessment,contextual)
                    if assessment['decision']=='ALLOW':
                        self.feedback.record_action(attempt_id,'PAYMENT_ALLOWED',{'decision':assessment['decision']})
                    if assessment['decision']!='ALLOW':
                        self.feedback.repository.append_audit(attempt_id,'WARNING_SHOWN',{
                            'intervention_type':assessment['intervention']['type'],
                            'intervention_level':assessment['intervention']['level']},
                            ','.join(sorted(set(assessment.get('model_versions',{}).values()))))
                    if assessment['decision']=='BLOCK_AND_ESCALATE':
                        self.feedback.record_action(attempt_id,'PAYMENT_HELD',{'decision':assessment['decision']})
                    if self.review:
                        review=self.review.enqueue_if_needed(attempt_id,assessment,attempt['passive'])
                        if review:
                            self.feedback.record_action(attempt_id,'MANUAL_REVIEW_REQUESTED',{'reason':review['reason']})
            return {'payment':self.user_view(attempt),'context_required':False}
        except HTTPException:
            with self._lock:
                if attempt['state']==PaymentState.ANALYZING.value:
                    transition(attempt,PaymentState.ERROR)
            raise
        except Exception as error:
            with self._lock:
                if attempt['state']==PaymentState.ANALYZING.value:
                    transition(attempt,PaymentState.ERROR)
            raise HTTPException(503,'Safety analysis is unavailable; this simulated payment was not executed.') from error

    @staticmethod
    def _has_answers(request):
        return (request.context.contacted_by_unknown_person is not None or bool(request.messages)
                or bool(request.context.user_message))

    @staticmethod
    def _targeted_questions(attempt, passive):
        selected=select_critical_questions(payment_reason=attempt.get('payment_reason'),
            passive_risk=passive.get('risk_level'),max_questions=1)
        return selected['questions']

    def continue_payment(self, attempt_id, acknowledged):
        with self._lock:
            attempt=self._get(attempt_id)
            state=PaymentState(attempt['state'])
            if state==PaymentState.SIMULATED_COMPLETED and attempt.get('payment_fingerprint')!=self._payment_fingerprint(attempt):
                raise HTTPException(409,'This completed payment has immutable details; retrieve its original transaction record.')
            if state==PaymentState.SIMULATED_COMPLETED and attempt.get('wallet_account_id') and attempt.get('ledger_receipt'):
                return self.user_view(attempt)
            if state==PaymentState.WARNING and not acknowledged:
                raise HTTPException(422,'Acknowledge the warning to continue this simulated payment.')
            if state not in (PaymentState.READY,PaymentState.WARNING):
                raise HTTPException(409,'This payment is not ready to continue. Complete verification or cancel it.')
            if state==PaymentState.WARNING and attempt['assessment']['decision']=='BLOCK_AND_ESCALATE':
                raise HTTPException(409,'The current policy does not permit continuation.')
            if (attempt.get('assessment') is None or
                    attempt.get('assessment_fingerprint')!=self._payment_fingerprint(attempt)):
                attempt['assessment']=None
                attempt['simulated_status']='NOT_EXECUTED'
                transition(attempt,PaymentState.ERROR)
                raise HTTPException(409,'The payment details no longer match this safety check. Start a new check; no payment was made.')
            decision=attempt['assessment']['decision']
            if attempt.get('wallet_account_id'):
                if self.banking_service is None:
                    raise HTTPException(503,'Simulated banking is unavailable. No payment was made.')
                attempt['ledger_receipt']=self.banking_service.settle(
                    transaction_id=attempt['payment_attempt_id'],
                    idempotency_key='chat-settlement-'+attempt['payment_attempt_id'],
                    sender_account_id=attempt['wallet_account_id'],
                    recipient_alias=attempt['recipient_alias'],amount=attempt['amount'],
                    purpose=attempt['payment_reason'])
            attempt['user_action']=('VERIFIED_AND_CONTINUED' if attempt['verified'] else
                'CONTINUED_AFTER_WARNING' if state==PaymentState.WARNING else
                'PAYMENT_ALLOWED_WITHOUT_WARNING')
            attempt['simulated_status']='SIMULATED_SUCCESS'
            transition(attempt,PaymentState.SIMULATED_COMPLETED)
            if self.feedback:
                action=('USER_VERIFIED_AND_CONTINUED' if attempt['verified'] else
                    'USER_CONTINUED_AFTER_WARNING' if state==PaymentState.WARNING else 'PAYMENT_ALLOWED')
                self.feedback.record_action(attempt['payment_attempt_id'],action,{'decision':decision})
                self.feedback.record_action(attempt['payment_attempt_id'],'PAYMENT_COMPLETED',{'simulated_only':True})
                self.feedback.repository.append_audit(attempt['payment_attempt_id'],'USER_CONTINUED',{
                    'decision':decision,'simulated_only':True})
            return self.user_view(attempt)

    def verify(self, attempt_id, action):
        with self._lock:
            attempt=self._get(attempt_id)
            if attempt['state']!=PaymentState.VERIFICATION_REQUIRED.value:
                raise HTTPException(409,'Additional verification is not required for this attempt.')
            if action=='cancel':
                return self._cancel_locked(attempt)
            if action!='verified_independently':
                raise HTTPException(422,'Choose cancellation or report that you checked independently.')
            # A button click is a customer report, not a result from an
            # authorized identity-verification service. No such service is
            # configured in this demo, so this claim cannot clear the hold.
            attempt['verification_claimed']=True
            attempt['user_action']='USER_REPORTED_INDEPENDENT_VERIFICATION'
            attempt['evidence_records'].append(evidence_record(payment_id=attempt_id,
                source_type='USER_REPORTED',source_reference='payment_action.verify',
                interpretation='Customer says they independently verified the recipient; no trusted verification result is connected.',
                confidence=0.5,verification_status='unverified'))
            return self.user_view(attempt)

    def attach_trusted_references(self, attempt_id, references):
        """Attach source-attributed approved guidance to the analyst provenance ledger."""
        with self._lock:
            attempt=self._get(attempt_id)
            existing={row['source_reference'] for row in attempt['evidence_records']
                if row['source_type']=='TRUSTED_REFERENCE'}
            for row in build_evidence_records(payment_id=attempt_id,
                    transaction=self._transaction(attempt),context={},history=None,
                    trusted_references=references,backend_history_available=False):
                if row['source_type']=='TRUSTED_REFERENCE' and row['source_reference'] not in existing:
                    attempt['evidence_records'].append(row)
                    existing.add(row['source_reference'])

    def cancel(self, attempt_id):
        with self._lock:
            return self._cancel_locked(self._get(attempt_id))

    def _cancel_locked(self, attempt):
        state=PaymentState(attempt['state'])
        if state in (PaymentState.SIMULATED_COMPLETED,PaymentState.CANCELLED,PaymentState.ERROR,
                     PaymentState.ANALYZING):
            raise HTTPException(409,'This payment attempt is already closed.')
        warned=attempt['assessment'] is not None and attempt['assessment']['decision']!='ALLOW'
        attempt['user_action']='CANCELLED_AFTER_WARNING' if warned else 'PAYMENT_CANCELLED'
        attempt['simulated_status']='CANCELLED'
        transition(attempt,PaymentState.CANCELLED)
        if self.feedback:
            self.feedback.record_action(attempt['payment_attempt_id'],'USER_CANCELLED',{
                'cancelled_after_warning':warned,'simulated_only':True})
            self.feedback.repository.append_audit(attempt['payment_attempt_id'],'USER_CANCELLED',{
                'cancelled_after_warning':warned,'simulated_only':True})
        return PaymentSimulator.user_view(attempt)

    def get(self, attempt_id):
        with self._lock: return self.user_view(self._get(attempt_id))

    def analyst(self, attempt_id):
        with self._lock:
            attempt=self._get(attempt_id)
            return {'payment':self.user_view(attempt),'attempt':self._analyst_fields(attempt)}

    def ablate_context(self, attempt_id):
        """Rerun the real engine after removing structured context and message evidence."""
        with self._lock:
            attempt=self._get(attempt_id)
            if attempt['assessment'] is None:
                raise HTTPException(409,'Analyze this payment before requesting an evidence ablation.')
            transaction=self._transaction(attempt)
            passive=attempt['passive']
            full=attempt['assessment']
            context=PaymentContext(payment_reason=attempt['context_reason'])
        contextual=self.risk.score_contextual(transaction,context,None)
        ablated=self.engine.analyze_payment(transaction,context,None,contextual_result=contextual)
        return {'payment_attempt_id':attempt_id,'method':'Rerun the APP Shield engine with structured context and message evidence unavailable; payment, recipient, and graph inputs remain unchanged.',
            'full_assessment':full,'ablated_assessment':ablated,'passive_assessment':passive,
            'removed_evidence':['structured context answers','message and conversation evidence'],
            'unchanged_evidence':['transaction inputs','recipient history','historical network']}

    def analytics(self, analyst=False, limit=30):
        with self._lock:
            attempts=list(self._attempts.values())
            actions=Counter(item['user_action'] for item in attempts if item['user_action'])
            risks=Counter(item['assessment']['risk_level'] for item in attempts if item['assessment'])
            recent=[{'payment_attempt_id':item['payment_attempt_id'],'recipient':item['recipient_name'],
              'amount':item['amount'],'currency':'INR','state':item['state'],
              'created_at':item['created_at'],'note':item.get('note',''),
              'risk_level':item['assessment']['risk_level'] if item['assessment'] else 'NOT_ANALYZED',
              'scenario':item['assessment']['likely_scam_scenario'] if item['assessment'] else 'unknown',
              'decision':item['assessment']['decision'] if item['assessment'] else 'PENDING',
              'user_action':item['user_action']} for item in reversed(attempts[-limit:])]
            if analyst:
                for row in recent:
                    item=self._attempts[row['payment_attempt_id']]
                    assessment=item['assessment']
                    row['risk_score']=assessment['app_scam_risk'] if assessment else None
                    row['confidence']=assessment['confidence'] if assessment else None
            return {'label':'SIMULATED DATA','payments_analyzed':sum(bool(i['assessment']) for i in attempts),
              'warnings_shown':sum(i['state'] in ('WARNING','VERIFICATION_REQUIRED','SIMULATED_HELD','CANCELLED','SIMULATED_COMPLETED') and i['assessment'] is not None and i['assessment']['decision']!='ALLOW' for i in attempts),
              'cancelled_after_warning':actions['CANCELLED_AFTER_WARNING'],
              'continued_after_warning':actions['CONTINUED_AFTER_WARNING'],
              'verified_and_continued':actions['VERIFIED_AND_CONTINUED'],
              'allowed_without_warning':actions['PAYMENT_ALLOWED_WITHOUT_WARNING'],
              'risk_distribution':dict(risks),'recent_attempts':recent}

    def graph_neighborhood(self, attempt_id, max_nodes=16):
        with self._lock: attempt=self._get(attempt_id)
        graph_service=self.risk.graph
        if graph_service is None:
            return {'available':False,'reason':'Graph intelligence unavailable','nodes':[],'edges':[]}
        graph=graph_service.builder.build_graph_until(pd.Timestamp(attempt['timestamp']),attempt['payment_attempt_id'])
        center=attempt['recipient_id']
        if center not in graph:
            return {'available':False,'reason':'No recipient history in the available graph window','nodes':[],'edges':[]}
        selected={center}
        frontier={center}
        for _ in range(2):
            next_frontier=set()
            for node in frontier:
                next_frontier.update(graph.predecessors(node)); next_frontier.update(graph.successors(node))
            frontier=next_frontier-selected
            for node in sorted(frontier)[:max(0,max_nodes-len(selected))]: selected.add(node)
            if len(selected)>=max_nodes: break
        selected_order=[center]+sorted(selected-{center})
        aliases={value['account_id']:alias for alias,value in self._scenario_data['recipients'].items()}
        names={value['account_id']:value['display_name'] for value in self._scenario_data['recipients'].values()}
        nodes=[]
        graph_risk=(attempt.get('passive') or {}).get('graph_risk') or {}
        for node in selected_order:
            try:
                features=calculate_graph_features(graph,node)
                account=self.repository.accounts.loc[node]
                details={'account_age_days':calculate_account_age(account['created_at'],pd.Timestamp(attempt['timestamp'])),
                    'incoming_payments':features['in_degree'],'outgoing_payments':features['out_degree'],
                    'unique_senders':features['unique_incoming_senders'],
                    'rapid_outflow_ratio':features['rapid_outflow_ratio']}
                if node==center:details['risk_indicators']=graph_risk.get('reasons',[])
            except (KeyError,ValueError,TypeError):
                details={'available':False}
            nodes.append({'id':node,'label':names.get(node,aliases.get(node,'Account '+str(node)[-4:])),
                'role':'recipient' if node==center else 'connected account','details':details})
        edges=[]
        for source,target,key,data in graph.edges(keys=True,data=True):
            if source in selected and target in selected and len(edges)<40:
                edges.append({'source':source,'target':target,'amount':float(data.get('amount',0)),
                              'timestamp':str(data.get('timestamp',''))})
        return {'available':bool(edges),'reason':None if edges else 'No observed transfers connect this recipient',
                'nodes':nodes,'edges':edges}

    def account_neighborhood(self, account_id, max_nodes=16):
        """Show bounded, past-only network evidence for a recipient without creating a payment."""
        graph_service=self.risk.graph
        if graph_service is None:
            return {'available':False,'reason':'Graph intelligence unavailable','account_id':account_id,'nodes':[],'edges':[]}
        if account_id not in self.repository.accounts.index:
            raise HTTPException(404,'Recipient account not found')
        stamp=graph_service.builder.transactions.timestamp.max()+pd.Timedelta(nanoseconds=1)
        graph=graph_service.builder.build_graph_until(stamp)
        if account_id not in graph:
            return {'available':False,'reason':'Recipient has no available network history','account_id':account_id,'nodes':[],'edges':[]}
        selected={account_id}; frontier={account_id}
        for _ in range(2):
            adjacent=set()
            for node in frontier:
                adjacent.update(graph.predecessors(node)); adjacent.update(graph.successors(node))
            frontier=adjacent-selected
            selected.update(sorted(frontier)[:max(0,max_nodes-len(selected))])
            if len(selected)>=max_nodes: break
        order=[account_id]+sorted(selected-{account_id})
        nodes=[]
        for node in order:
            try:
                features=calculate_graph_features(graph,node)
                details={'incoming_payments':features['in_degree'],'outgoing_payments':features['out_degree'],
                    'unique_senders':features['unique_incoming_senders'],'rapid_outflow_ratio':features['rapid_outflow_ratio']}
            except (KeyError,ValueError,TypeError):
                details={'available':False}
            nodes.append({'id':node,'label':'Recipient' if node==account_id else 'Connected account',
                'role':'recipient' if node==account_id else 'connected account','details':details})
        edges=[{'source':source,'target':target,'amount':float(data.get('amount',0)),
                'timestamp':str(data.get('timestamp',''))}
               for source,target,_key,data in graph.edges(keys=True,data=True)
               if source in selected and target in selected][:40]
        return {'available':bool(edges),'reason':None if edges else 'No observed transfers connect this recipient',
            'account_id':account_id,'as_of':str(stamp),'nodes':nodes,'edges':edges}

    def _get(self,attempt_id):
        attempt=self._attempts.get(attempt_id)
        if attempt is None: raise HTTPException(404,'Payment attempt not found')
        return attempt

    @staticmethod
    def _analyst_fields(attempt):
        assessment=attempt['assessment']
        return {'transaction_id':attempt['payment_attempt_id'],'sender_id':attempt['sender_id'],
          'recipient_id':attempt['recipient_id'],'passive':attempt['passive'],'assessment':assessment,
          'contextual_result':attempt['contextual_result'],
          'context':attempt['context'],'conversation_evidence':attempt['conversation_evidence'],
          'evidence_records':attempt.get('evidence_records',[]),
          'payment_detail_version':attempt.get('payment_detail_version',1),
          'payment_fingerprint':attempt.get('payment_fingerprint'),
          'assessment_fingerprint':attempt.get('assessment_fingerprint'),
          'latency_ms':attempt['latency_ms'],'user_action':attempt['user_action'],
          'simulated_status':attempt['simulated_status']}

    @staticmethod
    def user_view(attempt):
        assessment=attempt['assessment']
        return {'payment_attempt_id':attempt['payment_attempt_id'],'state':attempt['state'],
          'sender':{'alias':attempt['sender_alias'],'display_name':attempt['sender_name']},
          'recipient':{'alias':attempt['recipient_alias'],'account_id':attempt['recipient_id'],
            'display_name':attempt['recipient_name']},
          'amount':attempt['amount'],'currency':attempt['currency'],'payment_reason':attempt['payment_reason'],
          'payment_type':attempt['payment_type'],'note':attempt.get('note',''),
          'created_at':attempt['created_at'],'decision':assessment['decision'] if assessment else None,
          'payment_detail_version':attempt.get('payment_detail_version',1),
          'verification_claimed':attempt.get('verification_claimed',False),
          'intervention':assessment['intervention'] if assessment else None,
          'top_reasons':[item.get('description','Please verify this payment independently.') for item in assessment.get('top_reasons',[])[:4]] if assessment else [],
          'protective_reasons':PaymentSimulator._protective_reasons(assessment),
          'receipt':attempt.get('ledger_receipt'),
          'context_questions':attempt.get('context_questions',[]),
          'user_action':attempt['user_action'],'simulated_status':attempt['simulated_status'],
          'message':'Simulated environment only. No real money moves.'}

    @staticmethod
    def _protective_reasons(assessment):
        if not assessment:
            return []
        language={
          'KNOWN_RECIPIENT_LONG_TERM':'You have paid this recipient before.',
          'REPEATED_PRIOR_PAYMENTS':'There is a history of repeated payments to this recipient.',
          'ESTABLISHED_RECIPIENT_ACCOUNT':'This recipient has an established payment history with you.',
          'NORMAL_AMOUNT_PATTERN':'The amount is within your usual payment pattern.',
        }
        return [language[item] for item in assessment.get('protective_evidence',[]) if item in language]


_FLAGSHIP=('Sir verification department se bol raha hu. Aapke Aadhaar ke regarding suspicious activity mili hai. '
 'Aaj verification complete karna zaroori hai. ₹3,500 provided account me transfer kar dijiye. '
 'Verification complete hone tak kisi se discuss mat kariye.')
_SCENARIOS=[
 {'id':'normal_friend','title':'Normal friend payment','description':'A routine payment to a familiar recipient.',
  'difficulty':'easy','sender_alias':'U101','recipient_alias':'R201','amount':1200,'payment_reason':'friend','messages':[],'context':{}},
 {'id':'large_purchase','title':'Legitimate large purchase','description':'A high amount to an established merchant; test balanced evidence.',
  'difficulty':'hard negative','sender_alias':'U102','recipient_alias':'R202','amount':80000,'payment_reason':'shopping','messages':[],'context':{}},
 {'id':'merchant','title':'Established merchant','description':'A regular merchant payment with no unsolicited contact.',
  'difficulty':'easy','sender_alias':'U101','recipient_alias':'R202','amount':2400,'payment_reason':'shopping','messages':[],'context':{}},
 {'id':'government_impersonation','title':'Government impersonation — flagship','description':'A normal-range payment request uses authority, urgency and secrecy in Hinglish.',
  'difficulty':'flagship','sender_alias':'U101','recipient_alias':'R203','amount':3500,'payment_reason':'government',
  'context':{'contacted_by_unknown_person':True,'contact_channel':'whatsapp','claimed_authority':True,'authority_type':'government',
    'urgent_payment_requested':True,'threatened_consequences':True,'requested_secrecy':True,'fund_transfer_requested':True},
  'messages':[{'speaker':'other','text':_FLAGSHIP}]},
 {'id':'bank_impersonation','title':'Bank impersonation','description':'A caller claims to be bank support and requests urgent verification.',
  'difficulty':'hard','sender_alias':'U102','recipient_alias':'R204','amount':4200,'payment_reason':'bank_support',
  'context':{'contacted_by_unknown_person':True,'contact_channel':'phone','claimed_authority':True,'authority_type':'bank',
    'urgent_payment_requested':True,'requested_secrecy':True,'fund_transfer_requested':True},
  'messages':[{'speaker':'other','text':'I am from your bank security team. Move this payment now to protect your account; do not call the branch.'}]},
 {'id':'investment_scam','title':'Investment pressure','description':'A high-pressure investment request promises guaranteed returns.',
  'difficulty':'hard','sender_alias':'U103','recipient_alias':'R203','amount':9000,'payment_reason':'investment',
  'context':{'contacted_by_unknown_person':True,'promised_profit':True,'guaranteed_returns_promised':True,'urgent_payment_requested':True},
  'messages':[{'speaker':'other','text':'Invest today for guaranteed returns. Only a few places remain; transfer now to secure your profit.'}]},
 {'id':'fake_job','title':'Fake job fee','description':'A recruiter requests an upfront onboarding fee.',
  'difficulty':'hard','sender_alias':'U101','recipient_alias':'R206','amount':1800,'payment_reason':'job',
  'context':{'contacted_by_unknown_person':True,'contact_channel':'telegram','asked_to_pay_fee':True,'urgent_payment_requested':True},
  'messages':[{'speaker':'other','text':'Your job is confirmed. Pay a refundable training and onboarding fee today to reserve the position.'}]},
 {'id':'tech_support','title':'Tech support pressure','description':'A supposed support agent requests remote access and a transfer.',
  'difficulty':'hard','sender_alias':'U102','recipient_alias':'R204','amount':2600,'payment_reason':'tech_support',
  'context':{'contacted_by_unknown_person':True,'contact_channel':'phone','authority_type':'company_support','claimed_authority':True,
    'asked_to_install_remote_access':True,'fund_transfer_requested':True},
  'messages':[{'speaker':'other','text':'Support detected a virus. Install this remote tool and transfer a small amount to secure your account.'}]},
 {'id':'family_emergency','title':'Family emergency request','description':'An urgent request uses fear and asks for money without verification.',
  'difficulty':'hard','sender_alias':'U103','recipient_alias':'R205','amount':5000,'payment_reason':'family',
  'context':{'contacted_by_unknown_person':True,'contact_channel':'sms','urgent_payment_requested':True,'threatened_consequences':True},
  'messages':[{'speaker':'other','text':'I am in trouble and need money right away. Please send it now and do not call anyone yet.'}]},
 {'id':'legitimate_family_emergency','title':'Legitimate family emergency','description':'An urgent request to a familiar family member; urgency alone is not proof of a scam.',
  'difficulty':'hard negative','sender_alias':'U101','recipient_alias':'R201','amount':20000,'payment_reason':'family',
  'context':{'contacted_by_unknown_person':False,'urgent_payment_requested':True,
    'threatened_consequences':False,'claimed_authority':False,'requested_secrecy':False,
    'relationship_duration_days':3650},
  'messages':[{'speaker':'other','text':'Hospital emergency hai. Please abhi ₹20,000 bhej. Main tumhara bhai bol raha hoon.'}]},
 {'id':'small_investment','title':'Small initial investment scam','description':'A low payment is paired with a promised reward and limited-time pressure.',
  'difficulty':'hard','sender_alias':'U101','recipient_alias':'R203','amount':500,'payment_reason':'investment',
  'context':{'contacted_by_unknown_person':True,'promised_profit':True,'guaranteed_returns_promised':True,'urgent_payment_requested':True},
  'messages':[{'speaker':'other','text':'Start with only ₹500 today. Once your account activates you will receive ₹1,000 back. Only limited slots are available.'}]},
 {'id':'mule_network','title':'Recipient network review','description':'A recipient with unusual historical network patterns; no label is shown in the payment screen.',
  'difficulty':'network','sender_alias':'U102','recipient_alias':'R205','amount':2200,'payment_reason':'other','messages':[],'context':{}},
 {'id':'hinglish_impersonation','title':'Hinglish bank impersonation','description':'A Hinglish request claims authority, adds urgency and discourages verification.',
  'difficulty':'hard','sender_alias':'U103','recipient_alias':'R204','amount':3100,'payment_reason':'bank_support',
  'context':{'contacted_by_unknown_person':True,'contact_channel':'whatsapp','claimed_authority':True,'authority_type':'bank',
    'urgent_payment_requested':True,'requested_secrecy':True,'fund_transfer_requested':True},
  'messages':[{'speaker':'other','text':'Sir main bank verification team se hu. Aapka account temporary hold pe jane wala hai. Verification ke liye abhi payment complete kar dijiye. Kisi aur ko call mat kariye.'}]},
 {'id':'missing_context','title':'New recipient, context not provided','description':'Observe how missing evidence is represented rather than treated as safe.',
  'difficulty':'uncertain','sender_alias':'U101','recipient_alias':'R206','amount':3500,'payment_reason':'other','messages':[],'context':{}},
]
