"""Session-isolated chat orchestration; all payment actions remain simulator/policy owned."""
from datetime import datetime,timezone
from copy import deepcopy
from hashlib import sha256
import json
import logging
import re
from threading import RLock
from time import time
from uuid import uuid4
from fastapi import HTTPException
from backend.app.schemas.context import PaymentContext
from backend.app.simulation.schemas import CreatePaymentAttempt,AnalyzePaymentAttempt,ContinuePaymentAttempt
from backend.app.services.demo_banking_service import InsufficientBalance
from backend.app.fusion.evidence_consistency_engine import merge_reported_answer

MAIN_OPTIONS=['Make Payment','Check Balance','Transaction Details']

def route_intent(text):
    value=text.casefold().strip()
    if re.search(r'\b(cancel payment|stop payment|don.t send|do not send|changed my mind|forget it)\b',value):return 'PAYMENT_CANCEL'
    if re.search(r'\b(confirm and send|confirm payment|send it now|yes,? send it)\b',value):return 'PAYMENT_CONFIRM'
    if re.search(r'\b(transaction|transactions|history|payments|debit|credit|receive|received|sent|largest|how much (?:money )?(?:did i )?(?:send|receive))\b',value):
        return 'TRANSACTION_FILTER' if re.search(r'\b(today|this week|largest|to\s+\w+|receive|received|sent|debit|credit)\b',value) else 'TRANSACTION_DETAILS'
    if re.search(r'\b(balance|how much money|available funds|how much do i have)\b',value):return 'CHECK_BALANCE'
    if re.search(r'\b(make payment|pay someone|send|transfer|pay|bhej\w*)\b',value):return 'MAKE_PAYMENT'
    return 'UNKNOWN'

_AMOUNT=re.compile(r"(?:₹|\bINR\b|\bRs\.?\s*)\s*([\d,]+(?:\.\d{1,2})?)|\b([\d,]+(?:\.\d{1,2})?)\s*(?:rupees?|rs\b)",re.I)
_BARE_AMOUNT=re.compile(r"(?<!\d)([\d,]{1,12}(?:\.\d{1,2})?)(?!\d)")
_YES={'yes','haan','ha','y','yes both','yes, both','both'}
_NO={'no','nahi','nahin','nope'}
_SECRET=re.compile(r'(?i)\b(?:otp|pin|cvv|cvc)\s*[:=]\s*[A-Za-z0-9-]{3,}|\bpassword\s*(?::|=|is)\s*\S{4,}|(?<!\d)(?:\d[ -]?){13,19}(?!\d)')
LOGGER=logging.getLogger(__name__)

def infer_payment_reason(text):
    value=text.casefold()
    for terms,reason in [(['investment','double my money','returns','profit'],'investment'),
      (['job','registration fee','recruiter'],'job'),(['government','police','officer','arrest','rbi'],'government'),
      (['bank','account block','account freeze'],'bank_support'),(['brother','sister','family','mom','dad'],'family'),
      (['friend','usual recipient','saved recipient'],'friend'),(['electricity','bill','rent','landlord'],'other'),
      (['shopping','purchase','buy'],'shopping'),
      (['hospital','medical','emergency'],'emergency'),
      (['seller','marketplace','product'],'marketplace')]:
        if any(term in value for term in terms):return reason
    return 'other'

def extract_claims(text,context):
    """Structured, explicitly unverified claims extracted from the payer's report."""
    value=text.casefold(); claims=[]
    def put(key,result):
        if result is True and context.get(key) is not True:
            context[key]=result;claims.append({'field':key,'value':result,'provenance':'user_report','verified':False})
    authority=next((name for name in ('government','police','rbi','bank','court','tax department','officer') if name in value),None)
    if authority:
        put('claimed_authority',True)
        if context.get('authority_type') is None:
            context['authority_type']='government' if authority in ('government','police','rbi','officer','court','tax department') else 'bank'
            claims.append({'field':'authority_type','value':context['authority_type'],'provenance':'user_report','verified':False})
        if context.get('who_requested_payment') is None:
            context['who_requested_payment']=authority
            claims.append({'field':'who_requested_payment','value':authority,'provenance':'user_report','verified':False})
    if any(word in value for word in ('urgent','immediately','right now','pay now','transfer now','send now','abhi','jaldi')):
        put('urgent_payment_requested',True)
    if any(word in value for word in ('arrest','block','freeze','jail','consequence','legal action','account band')):
        put('threatened_consequences',True);put('urgent_payment_requested',True)
    if any(word in value for word in ('secret','do not tell','dont tell','keep quiet','kisi ko mat')):put('requested_secrecy',True)
    if any(word in value for word in ('double my money','guaranteed return','guaranteed returns','guaranteed investment return','guaranteed profit','risk free','double your money')):
        put('promised_profit',True);put('guaranteed_returns_promised',True)
    if any(word in value for word in ('registration fee','job fee','pay a fee','onboarding fee','training fee','upfront fee')):put('asked_to_pay_fee',True)
    if any(word in value for word in ('remote access','remote app','install anydesk','install a remote','remote-control')):
        put('asked_to_install_remote_access',True)
    if any(word in value for word in ('stranger','someone online','met online','unknown person','government officer','police officer',
        'caller','recruiter','support agent','someone called','a person called','a caller')):
        put('contacted_by_unknown_person',True)
    return claims

def has_payment_context(text,catalog):
    """Return true only when the opening includes a story beyond payment fields."""
    value=_AMOUNT.sub(' ',text or '')
    value=_BARE_AMOUNT.sub(' ',value)
    for row in catalog.get('recipients',[]):
        for candidate in (row.get('alias',''),row.get('display_name','')):
            if candidate:
                value=re.sub(r'(?<!\w)'+re.escape(candidate)+r'(?!\w)',' ',value,flags=re.I)
    value=re.sub(r'[^\w]+',' ',value,flags=re.UNICODE).casefold()
    ignored={'i','me','my','need','want','would','like','please','someone','to','send','pay','paid',
        'transfer','bhejna','bhej','money','payment','make','a','an','the','new','saved','usual',
        'known','recipient','rupee','rupees','rs','inr','for','this','that','who'}
    return any(token not in ignored for token in value.split())

class PaymentConversationAgent:
    MAX_SESSIONS=500
    SESSION_TTL=1800
    MAX_MESSAGES=40
    MAX_TOTAL_CHARS=6000
    def __init__(self,simulator,retriever,banking_service=None):
        self.simulator=simulator;self.retriever=retriever;self.banking=banking_service;self._sessions={};self._lock=RLock();self._request_cache={}

    def idempotent_request(self, *, scope, owner, key, payload, operation):
        """Return a cached result for a replay; reject a key reused for new input."""
        if not key:
            return operation()
        cache_key=f"{owner['account_id']}:{scope}:{key}"
        fingerprint=sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        with self._lock:
            cached=self._request_cache.get(cache_key)
            if cached is not None:
                if cached['fingerprint']!=fingerprint:
                    raise HTTPException(409,'This request key was already used for different chat input.')
                if cached['result'] is None:
                    raise HTTPException(409,'This chat request is already being processed. Retry with the same request key.')
                else:
                    return deepcopy(cached['result'])
            self._request_cache[cache_key]={'fingerprint':fingerprint,'result':None,'created_at':time()}
        try:
            result=operation()
        except Exception:
            with self._lock:
                self._request_cache.pop(cache_key,None)
            raise
        with self._lock:
            self._request_cache[cache_key]['result']=deepcopy(result)
            if len(self._request_cache)>2000:
                for old_key,entry in list(self._request_cache.items()):
                    if entry['result'] is not None:
                        self._request_cache.pop(old_key,None)
                        if len(self._request_cache)<=1800:break
        return result

    def start(self,message,owner):
        self._validate_message(message)
        with self._lock:
            self._purge()
            if len(self._sessions)>=self.MAX_SESSIONS:raise HTTPException(503,'Chat is busy. Please start again shortly.')
            session={'session_id':str(uuid4()),'created_at':datetime.now(timezone.utc).isoformat(),
                'updated':time(),'messages':[],'initial_text':message,'payment_attempt_id':None,
                'amount':None,'recipient_alias':None,'payment_reason':'other','payment_detail_version':1,
                'context':{},'claims':[],
                'current_question':None,'question_count':0,'retrieved_evidence':[],'payment':None,'closed':False,
                'account_id':owner['account_id'],'account_alias':owner['account_alias'],
                'display_name':owner['display_name'],'collecting_payment':False,'balance':None,
                'transactions':None,'transaction_detail':None}
            session['messages'].append({'role':'user','text':message})
            self._sessions[session['session_id']]=session
        intent=route_intent(message)
        if intent=='CHECK_BALANCE':return self._show_balance(session)
        if intent in ('TRANSACTION_DETAILS','TRANSACTION_FILTER'):return self._show_transactions(session,message)
        if intent!='MAKE_PAYMENT':return self._prompt(session,'Hello! How can I help you today?','MAIN_MENU',main_options=MAIN_OPTIONS)
        session['collecting_payment']=True
        if re.fullmatch(r'\s*(make payment|pay someone|send money)\s*[.!]?\s*',message,re.I):
            return self._prompt(session,'Who would you like to pay, and how much?','COLLECTING_DETAILS')
        return self._advance_details(session,message)

    def message(self,session_id,message,owner):
        self._validate_message(message)
        with self._lock:
            session=self._get(session_id);session['updated']=time()
            self._assert_owner(session,owner)
            if session['closed']:
                if route_intent(message) not in ('CHECK_BALANCE','TRANSACTION_DETAILS','TRANSACTION_FILTER','MAKE_PAYMENT'):
                    raise HTTPException(409,'This chat payment is already closed.')
                session['payment_attempt_id']=None;session['payment']=None;session['closed']=False
                session['amount']=None;session['recipient_alias']=None;session['context']={};session['claims']=[]
                session['current_question']=None;session['question_count']=0;session['collecting_payment']=False
            if len(session['messages'])>=self.MAX_MESSAGES or sum(len(row['text']) for row in session['messages'])+len(message)>self.MAX_TOTAL_CHARS:
                raise HTTPException(413,'This conversation reached its safety-check limit. Cancel the current attempt or start a new chat.')
            session['messages'].append({'role':'user','text':message})
        intent=route_intent(message)
        if not session['payment_attempt_id']:
            if intent=='CHECK_BALANCE':return self._show_balance(session)
            if intent in ('TRANSACTION_DETAILS','TRANSACTION_FILTER'):return self._show_transactions(session,message)
            if intent=='MAKE_PAYMENT':
                session['collecting_payment']=True
                session['initial_text']=message
                return self._advance_details(session,message)
            if not session.get('collecting_payment'):
                return self._prompt(session,'Try “Send ₹500 to Riya Sen,” “Check Balance,” or “Transaction Details.”','MAIN_MENU',main_options=MAIN_OPTIONS)
            session['initial_text']+=' '+message
            return self._advance_details(session,message)
        payment=self.simulator.get(session['payment_attempt_id'])
        if payment['state'] in ('SIMULATED_COMPLETED','CANCELLED','SIMULATED_HELD','ERROR'):
            if intent=='CHECK_BALANCE':return self._show_balance(session)
            if intent in ('TRANSACTION_DETAILS','TRANSACTION_FILTER'):return self._show_transactions(session,message)
            if intent=='MAKE_PAYMENT':
                session['payment_attempt_id']=None;session['payment']=None;session['closed']=False
                session['amount']=None;session['recipient_alias']=None;session['context']={};session['claims']=[]
                session['initial_text']=message;session['collecting_payment']=True
                return self._advance_details(session,message)
        if intent=='PAYMENT_CANCEL':return self.action(session_id,'cancel',owner)
        if intent=='PAYMENT_CONFIRM':return self.action(session_id,'confirm',owner)
        if self._is_cancel_request(message):
            return self.action(session_id,'cancel')
        updated=self._payment_edit(session,message)
        if updated:
            return self._restart_after_edit(session,message,updated)
        if payment['state']=='CONTEXT_REQUIRED':return self._answer_question(session,message)
        return self._respond_with_assessment(session,payment)

    @staticmethod
    def _is_cancel_request(message):
        value=message.casefold().strip()
        if re.search(r"\b(?:don't|do not|never)\s+cancel\b",value):return False
        return bool(re.search(r"\b(?:cancel|stop|don't send|do not send|changed my mind|change my mind|rather not|forget it)\b",value))

    def _payment_edit(self,session,message):
        value=message.casefold()
        edit_intent=bool(re.search(r"\b(?:change|update|instead|switch|actually|make it|make the amount)\b",value))
        if not edit_intent:return None
        updates={}
        amount_match=_AMOUNT.search(message)
        if not amount_match:
            amount_match=re.search(r"(?i)\b(?:amount|payment|it)\s+(?:to|as)\s+([\d,]+(?:\.\d{1,2})?)\b",message)
        if amount_match:
            raw=amount_match.group(1) if amount_match.lastindex==1 else amount_match.group(1) or amount_match.group(2)
            try:
                amount=float(raw.replace(',',''))
                if 0<amount<=10_000_000:updates['amount']=amount
            except (AttributeError,ValueError):
                pass
        if re.search(r"\b(?:recipient|payee|send to|pay to)\b",value):
            for row in self.simulator.catalog()['recipients']:
                if re.search(r'(?<!\w)'+re.escape(row['alias'].casefold())+r'(?!\w)',value) or re.search(r'(?<!\w)'+re.escape(row['display_name'].casefold())+r'(?!\w)',value):
                    updates['recipient_alias']=row['alias'];break
            else:
                updates['recipient_alias']=None
        return updates or None

    def _restart_after_edit(self,session,message,updates):
        self.simulator.cancel(session['payment_attempt_id'])
        session['amount']=updates.get('amount',session['amount'])
        session['recipient_alias']=updates.get('recipient_alias',session['recipient_alias'])
        session['payment_detail_version']+=1
        session['payment_attempt_id']=None;session['payment']=None;session['closed']=False
        session['context']={};session['claims']=[];session['current_question']=None
        session['question_count']=0;session['retrieved_evidence']=[]
        if session['recipient_alias']:
            session['initial_text']=f"Send INR {session['amount']:g} to {session['recipient_alias']}"
        else:
            session['initial_text']=f"Send INR {session['amount']:g} to a new recipient"
        session['messages'].append({'role':'assistant','text':'I’ve updated the payment details and cancelled the previous attempt. I’ll run a fresh safety check; nothing has been sent.'})
        if not session['recipient_alias']:
            return self._need_recipient(session,self.simulator.catalog()['recipients'])
        return self._advance_details(session,message)

    def action(self,session_id,action,owner):
        with self._lock:session=self._get(session_id);session['updated']=time()
        self._assert_owner(session,owner)
        attempt_id=session.get('payment_attempt_id')
        if not attempt_id:raise HTTPException(409,'Complete the payment details before choosing a payment action.')
        if action=='confirm' and session.get('payment',{}).get('state')=='SIMULATED_COMPLETED':
            return self._respond_with_assessment(session,session['payment'])
        if action=='cancel':payment=self.simulator.cancel(attempt_id)
        elif action=='verify':payment=self.simulator.verify(attempt_id,'verified_independently')
        elif action=='confirm':payment=self.simulator.continue_payment(attempt_id,True)
        else:raise HTTPException(404,'Unknown payment action.')
        with self._lock:
            session['payment']=payment;session['closed']=payment['state'] in ('SIMULATED_COMPLETED','CANCELLED','SIMULATED_HELD')
        return self._respond_with_assessment(session,payment)

    def get(self,session_id,owner):
        with self._lock:session=self._get(session_id)
        self._assert_owner(session,owner)
        if session['payment_attempt_id']:
            session['payment']=self.simulator.get(session['payment_attempt_id'])
        return self._view(session)

    def _advance_details(self,session,last_message):
        parsed=session['initial_text'];catalog=self.simulator.catalog();amount=session.get('amount')
        if amount is None:
            match=_AMOUNT.search(parsed)
            standalone_amount=bool(re.fullmatch(r'\s*(?:(?:₹|INR\s*|Rs\.?\s*)\s*)?[\d,]+(?:\.\d{1,2})?\s*',last_message,re.I))
            if not match and (standalone_amount or re.search(r'(?i)\b(send|pay|transfer|bhej\w*|jama|paisa|paise)\b',parsed)):
                match=_BARE_AMOUNT.search(parsed)
            if match:
                amount=float((match.group(1) or match.group(2)).replace(',',''));session['amount']=amount
        if session.get('recipient_alias') is None:
            matches=[]
            lower=parsed.casefold()
            internal_names={item['display_name'].casefold() for item in self.simulator._scenario_data['senders'].values()}
            for row in catalog['recipients']:
                candidates=[row['alias'].casefold(),row['display_name'].casefold()]
                display_words=candidates[1].split() if candidates[1] in internal_names else []
                if any(re.search(r'(?<!\w)'+re.escape(candidate)+r'(?!\w)',lower) for candidate in candidates) or any(
                    re.search(r'(?<!\w)'+re.escape(word)+r'(?!\w)',lower) for word in display_words):matches.append(row)
            if 'new recipient' in lower or 'new person' in lower:
                matches=[row for row in catalog['recipients'] if row['alias']=='R203'] or matches
            elif any(term in lower for term in ('saved recipient','usual recipient','known recipient')):
                matches=[row for row in catalog['recipients'] if row['alias']=='R201'] or matches
            # Name mentions alone never verify an identity; only exact catalog entries can resolve.
            distinct={row['alias']:row for row in matches}
            if len(distinct)==1:session['recipient_alias']=next(iter(distinct))
            elif len(distinct)>1:
                return self._need_recipient(session,list(distinct.values()))
        session['payment_reason']=infer_payment_reason(parsed)
        if session.get('amount') is None:
            if session.get('collecting_payment') and not re.search(r'(?i)\b(send|pay|transfer|to|rupees?|rs\b|inr)\b',parsed):
                return self._prompt(session,'Who would you like to pay, and how much?','COLLECTING_DETAILS')
            return self._prompt(session,'What amount would you like to send? Include the amount in rupees.',
                'COLLECTING_DETAILS',quick_replies=[])
        if not session.get('recipient_alias'):
            return self._need_recipient(session,catalog['recipients'],not any(
                row['alias'].casefold() in parsed.casefold() or row['display_name'].split(' · ')[0].casefold() in parsed.casefold()
                for row in catalog['recipients']))
        if not session['payment_attempt_id']:
            try:self.banking.require_sufficient_balance(session['account_id'],session['amount'])
            except InsufficientBalance:
                return self._prompt(session,'Your available balance is not enough for this payment.','INSUFFICIENT_FUNDS',main_options=MAIN_OPTIONS)
            attempt=CreatePaymentAttempt(sender_alias=session['account_alias'],recipient_alias=session['recipient_alias'],
                amount=session['amount'],payment_reason=session['payment_reason'],payment_type='upi',note='',
                idempotency_key='chat-'+uuid4().hex)
            created,_=self.simulator.create(attempt,wallet_account_id=session['account_id'],
                payment_detail_version=session['payment_detail_version']);session['payment_attempt_id']=created['payment_attempt_id']
            session['messages'].append({'role':'assistant','text':f"I’ll check ₹{session['amount']:,.0f} to {created['recipient']['display_name']} before anything is confirmed."})
            initial_claims=extract_claims(parsed,session['context'])
            session['claims'].extend(initial_claims)
            # Always pass the payer's report to the backend assessment. The
            # structured claim extractor is intentionally narrow, so using it
            # as a gate would discard useful natural-language context. A bare
            # amount and recipient still need the single targeted question.
            session['context']['payment_reason']=session['payment_reason']
            if has_payment_context(parsed,catalog):
                session['context']['user_message']=parsed[:1000]
            analysis_request=AnalyzePaymentAttempt(context=PaymentContext.model_validate(session['context']))
            result=self.simulator.analyze(session['payment_attempt_id'],analysis_request)
            session['payment']=result['payment']
            session['question_count']=len(result.get('context_questions') or [])
            if result.get('context_required'):
                selected=(result.get('context_questions') or [{'id':'contacted_by_unknown_person'}])[0]
                session['current_question']=({'id':'who_requested_payment','label':'Who asked you to make this payment?',
                    'reason_for_question':selected.get('reason_for_question','Clarifies who initiated this payment.')}
                    if selected['id']=='contacted_by_unknown_person' else selected)
                replies=(['Government officer','Bank representative','Employer or recruiter','Seller',
                    'Friend or family','Someone else','Not sure'] if session['current_question']['id']=='who_requested_payment'
                    else ['Yes','No','Not sure'])
                return self._prompt(session,session['current_question'].get('label','Who asked you to make this payment?'),
                    'NEEDS_CONTEXT',quick_replies=replies,payment=result['payment'])
            return self._respond_with_assessment(session,result['payment'])
        return self._respond_with_assessment(session,session['payment'])

    def _need_recipient(self,session,rows,not_found=False):
        options=[{'label':f"{row['display_name']} · {row['alias']}",'value':row['alias']} for row in rows]
        prompt="I couldn't find this recipient. Please check the details, or choose a listed demo account." if not_found else 'Which listed demo recipient do you mean? Please choose the exact demo account.'
        return self._prompt(session,prompt,
            'COLLECTING_DETAILS',recipient_options=options)

    def _answer_question(self,session,message):
        question=session.get('current_question') or {'id':'contacted_by_unknown_person'}
        question_id=question['id'];normalized=message.strip().casefold().strip('.,!?')
        context=session['context']
        if question_id=='who_requested_payment':
            if normalized not in ('not sure','unsure','dont know','don\'t know'):
                context['who_requested_payment']=message.strip()[:120]
                session['claims'].append({'field':'who_requested_payment','value':context['who_requested_payment'],
                    'provenance':'user_report','verified':False})
                known=any(word in normalized for word in ('friend','family','brother','sister','saved','usual'))
                merge_reported_answer(context,'contacted_by_unknown_person',not known)
                session['claims'].append({'field':'contacted_by_unknown_person','value':not known,
                    'provenance':'user_report','verified':False})
                session['claims'].extend(extract_claims(message,context))
                context['user_message']=((context.get('user_message')+'\n') if context.get('user_message') else '')+message[:1000]
            else:
                uncertainty='The payer is unsure who requested this payment.'
                context['user_message']=((context.get('user_message')+'\n') if context.get('user_message') else '')+uncertainty
        elif normalized in _YES or normalized in _NO:
            answer=normalized in _YES
            # Preserve any earlier positive pressure/unknown-contact evidence.
            # A later denial is another unverified report, not a deletion.
            merge_reported_answer(context,question_id,answer)
            session['claims'].append({'field':question_id,'value':answer,
                'provenance':'user_report','verified':False})
        elif normalized in ('not sure','unsure','dont know','don\'t know'):
            session['claims'].append({'field':question_id,'value':'not_sure',
                'provenance':'user_report','verified':False})
        else:
            session['claims'].extend(extract_claims(message,context))
            context['user_message']=((context.get('user_message')+'\n') if context.get('user_message') else '')+message[:1000]
        if normalized in ('yes both','yes, both','both') and question_id=='urgent_payment_requested':
            context['threatened_consequences']=True;context['requested_secrecy']=True
        self.simulator._safe_message(context.get('user_message') or '')
        if context.get('claimed_authority') and any(word in message.casefold() for word in ('arrest','block','freeze','abhi','immediately','now')):
            context['threatened_consequences']=True;context['urgent_payment_requested']=True
        self.simulator._safe_message(context.get('user_message') or '')
        if self.simulator.feedback:
            try:
                self.simulator.feedback.repository.append_audit(session['payment_attempt_id'],
                    'CONVERSATION_EVIDENCE_UPDATED',{'question_id':question_id,
                    'evidence_fields':sorted({item['field'] for item in session['claims']}),
                    'claim_count':len(session['claims']),'conversation_message_count':len(session['messages'])})
            except (OSError,ValueError,RuntimeError) as error:
                LOGGER.warning('conversation_audit_unavailable type=%s',type(error).__name__)
        session['current_question']=None
        context['payment_reason']=session['payment_reason']
        if context.get('claimed_authority') and context.get('authority_type')=='government' and context['payment_reason']=='other':
            context['payment_reason']='government'
            session['payment_reason']='government'
        request=AnalyzePaymentAttempt(context=PaymentContext.model_validate(context))
        result=self.simulator.analyze(session['payment_attempt_id'],request)
        session['payment']=result['payment']
        session['messages'].append({'role':'assistant','text':self._explanation(result['payment'])})
        return self._respond_with_assessment(session,result['payment'])

    @staticmethod
    def _assert_owner(session,owner):
        if session['account_id']!=owner['account_id']:
            raise HTTPException(403,'This chat belongs to a different simulated account.')

    def _show_balance(self,session):
        session['balance']=self.banking.balance(session['account_id'])
        balance=session['balance']
        message=f"Your available balance is ₹{balance['available_balance']:,.2f}."
        if balance['held_balance']:
            message+=f" ₹{balance['held_balance']:,.2f} is currently held."
        session['transactions']=None;session['transaction_detail']=None
        return self._prompt(session,message,'BALANCE',balance=balance,main_options=MAIN_OPTIONS)

    def _show_transactions(self,session,query):
        value=query.casefold();direction=None;period=None;largest='largest' in value
        id_match=re.search(r'\b(?:details?\s+(?:for|of)\s+)?([0-9a-f]{8}-[0-9a-f-]{27,})\b',query,re.I)
        if id_match:
            detail=self.banking.transaction(session['account_id'],id_match.group(1))
            session['transactions']=None;session['transaction_detail']=detail;session['balance']=None
            return self._prompt(session,f"Transaction {detail['transaction_id']} was {detail['status'].lower()}.",
                'TRANSACTION_DETAIL',transaction_detail=detail,main_options=MAIN_OPTIONS)
        if any(word in value for word in ('received','receive','credit','money in')):direction='CREDIT'
        elif any(word in value for word in ('sent','send','debit','paid','money out')):direction='DEBIT'
        if 'today' in value:period='today'
        elif 'this week' in value or 'this month' in value:period='week'
        payee_match=re.search(r"\b(?:to|from)\s+([A-Za-z][A-Za-z .'-]{1,40})",query,re.I)
        payee=payee_match.group(1).strip(' .') if payee_match else None
        limit=20 if 'view more' in value else 5
        result=self.banking.transactions(session['account_id'],limit=limit,direction=direction,
            payee=payee,start=None,end=None,largest=largest)
        # Date windows use the API's deterministic India-time implementation.
        if period:
            from backend.app.api.banking_routes import period_bounds
            start,end=period_bounds(period)
            result=self.banking.transactions(session['account_id'],limit=limit,direction=direction,
                payee=payee,start=start,end=end,largest=largest)
        session['transactions']=result['transactions'];session['transaction_detail']=None;session['balance']=None
        if re.search(r'\b(?:how much|total)\b',value):
            verb='received' if direction=='CREDIT' else 'sent' if direction=='DEBIT' else 'moved'
            message=f"You {verb} ₹{result['total_amount']:,.2f} across {result['total_count']} matching transactions."
        elif result['transactions']:
            message='Here are your recent transactions.' if not direction and not payee and not period else 'Here are the matching transactions.'
        else:message='There are no matching transactions in this simulated account yet.'
        return self._prompt(session,message,'TRANSACTIONS',transactions=result['transactions'],
            main_options=MAIN_OPTIONS,view_more=result['total_count']>len(result['transactions']))

    def _respond_with_assessment(self,session,payment):
        reason=session.get('payment_reason','other')
        context=session.get('context') or {}
        query=' '.join([reason,session.get('initial_text',''),payment.get('message',''),
            context.get('user_message') or '',context.get('who_requested_payment') or '',
            ' '.join(item['field']+' '+str(item['value']) for item in session.get('claims',[]))])
        category=('bank_impersonation' if context.get('authority_type')=='bank' else 'government_impersonation'
            if context.get('claimed_authority') else {'government':'government_impersonation',
            'bank_support':'bank_impersonation','investment':'investment_scam'}.get(reason,'legitimate_payment'))
        try:
            evidence=self.retriever.retrieve(query,category=category,limit=2) if self.retriever else []
        except Exception as error:
            LOGGER.warning('payment_guidance_retrieval_unavailable type=%s',type(error).__name__)
            evidence=[]
        session['retrieved_evidence']=evidence
        if self.simulator and session.get('payment_attempt_id') and evidence:
            try:
                references=[]
                for item in evidence:
                    meta=item.get('metadata') or {}
                    if meta.get('trust_level') in ('official','internal_policy'):
                        references.append({'source_reference':meta.get('url') or meta.get('id'),
                            'title':meta.get('title'),'supported_interpretation':meta.get('title'),
                            'confidence':0.95})
                self.simulator.attach_trusted_references(session['payment_attempt_id'],references)
            except (AttributeError,KeyError,TypeError,ValueError,HTTPException) as error:
                LOGGER.warning('payment_reference_provenance_unavailable type=%s',type(error).__name__)
        message=self._explanation(payment)
        state=payment['state'];actions=self._available_actions(payment)
        if state=='READY':
            message=f"Safety check complete. Review ₹{payment['amount']:,.0f} to {payment['recipient']['display_name']}. No payment has been made yet."
        elif state=='SIMULATED_COMPLETED':
            receipt=payment.get('receipt') or {}
            message=(f"Payment successful. ₹{payment['amount']:,.2f} paid to {payment['recipient']['display_name']}. "
                f"Transaction ID: {receipt.get('transaction_id',payment['payment_attempt_id'])}. Status: Completed.")
            # Settlement has already committed. A display refresh failure must
            # never hide the successful receipt or make the client retry it.
            try:
                session['balance']=self.banking.balance(session['account_id'])
            except Exception as error:
                LOGGER.warning('post_payment_balance_refresh_failed type=%s',type(error).__name__)
                session['balance']=None
        elif state=='VERIFICATION_REQUIRED' and payment.get('verification_claimed'):
            message=('Thanks for telling me you checked. This demo has no trusted identity check, '
                     'so I cannot verify the recipient independently and the payment remains paused. Cancel the payment or verify through a trusted channel.')
        elif state=='CANCELLED':message='Payment cancelled. No simulated payment was completed.'
        elif state=='CONTEXT_REQUIRED':
            question=session.get('current_question') or (payment.get('context_questions') or [{}])[0]
            return self._prompt(session,question.get('label','Can you share a little more about this payment?'),'NEEDS_CONTEXT',quick_replies=['Yes','No','Not sure'],payment=payment)
        options=MAIN_OPTIONS if state in ('SIMULATED_COMPLETED','CANCELLED','SIMULATED_HELD','ERROR') else None
        return self._prompt(session,message,state,actions=actions,knowledge=evidence,payment=payment,main_options=options)

    @staticmethod
    def _available_actions(payment):
        state=payment.get('state');actions=[]
        if state=='READY':actions=['confirm','cancel']
        elif state=='WARNING':
            actions=['cancel']
            if payment.get('decision')!='BLOCK_AND_ESCALATE':actions.append('confirm')
        elif state=='VERIFICATION_REQUIRED':actions=['cancel'] if payment.get('verification_claimed') else ['cancel','verify']
        elif state=='SIMULATED_HELD':actions=['cancel']
        elif state=='CONTEXT_REQUIRED':actions=['cancel']
        return actions

    def _explanation(self,payment):
        decision=payment.get('decision')
        if decision=='BLOCK_AND_ESCALATE':
            return (payment.get('intervention') or {}).get('message') or 'APP Shield has paused this simulated payment. Please independently verify the request through an official channel.'
        if decision in ('WARN_AND_REVIEW','ALLOW_WITH_WARNING'):
            return (payment.get('intervention') or {}).get('message') or 'Please review this payment and verify the recipient independently before continuing.'
        if decision=='STEP_UP_VERIFICATION':return (payment.get('intervention') or {}).get('message') or 'APP Shield requires independent verification before this payment can be reviewed for continuation.'
        if decision=='ALLOW':return 'The backend assessment found no current policy warning. Please still review the recipient and amount before confirming.'
        return 'The safety assessment is not available yet. No payment has been made.'

    @staticmethod
    def _state_message(payment):
        return {'SIMULATED_COMPLETED':'The simulated payment is complete. No real money moved.',
            'CANCELLED':'Payment cancelled. No simulated payment was completed.',
            'READY':'Payment remains ready for explicit confirmation.'}.get(payment['state'],'Payment state updated by the APP Shield policy.')

    def _prompt(self,session,message,state,*,quick_replies=None,recipient_options=None,actions=None,knowledge=None,payment=None,
                balance=None,transactions=None,transaction_detail=None,main_options=None,view_more=False):
        session['messages'].append({'role':'assistant','text':message});session['updated']=time();session['last_state']=state
        return {'session_id':session['session_id'],'payment_attempt_id':session.get('payment_attempt_id'),
            'message':message,'interaction_type':state,'payment_state':payment['state'] if payment else state,
            'payment_action_allowed':bool(actions),'available_actions':actions or [],
            'current_question':session.get('current_question'),
            'question_count':session.get('question_count',0),'question_limit':1,
            'quick_replies':quick_replies or [],'recipient_options':recipient_options or [],
            'payment':payment,'claims':list(session['claims']),'knowledge':[self._public_evidence(item) for item in (knowledge or [])],
            'balance':balance,'transactions':transactions,'transaction_detail':transaction_detail,
            'main_options':main_options or [],'view_more':view_more,
            'messages':list(session['messages'][-24:])}

    @staticmethod
    def _public_evidence(item):
        meta=item['metadata']
        return {'document_id':meta['id'],'chunk_id':meta['chunk_id'],'content_hash':item['content_hash'],
            'title':meta['title'],'source':meta['source'],'url':meta['url'],
            'category':meta['category'],'publication_date':meta['publication_date'],
            'retrieval_date':meta['retrieval_date'],'language':meta['language'],
            'version':meta['version'],'trust_level':meta['trust_level'],'excerpt':item['content'][:420]}

    def _view(self,session):
        payment=self.simulator.get(session['payment_attempt_id']) if session.get('payment_attempt_id') else session.get('payment')
        current=session.get('current_question')
        return {'session_id':session['session_id'],'payment_attempt_id':session.get('payment_attempt_id'),
            'interaction_type':'NEEDS_CONTEXT' if current else (payment['state'] if payment else session.get('last_state','MAIN_MENU')),
            'payment_state':payment['state'] if payment else session.get('last_state','MAIN_MENU'),
            'payment_action_allowed':bool(payment and self._available_actions(payment)),
            'available_actions':self._available_actions(payment) if payment else [],
            'current_question':current,'question_count':session.get('question_count',0),'question_limit':1,
            'quick_replies':(['Government officer','Bank representative','Employer or recruiter','Seller',
                'Friend or family','Someone else','Not sure'] if current and current['id']=='who_requested_payment' else
                ['Yes','No','Not sure'] if current else []),
            'recipient_options':[],'payment':payment,
            'claims':list(session['claims']),'knowledge':[self._public_evidence(item) for item in session.get('retrieved_evidence',[])],
            'account':{'alias':session['account_alias'],'display_name':session['display_name']},
            'balance':session.get('balance'),'transactions':session.get('transactions'),
            'transaction_detail':session.get('transaction_detail'),
            'main_options':MAIN_OPTIONS if session.get('closed') or not payment else [],
            'messages':list(session['messages'][-24:])}

    def _get(self,session_id):
        session=self._sessions.get(session_id)
        if not session:raise HTTPException(404,'Chat session not found or expired.')
        if time()-session['updated']>self.SESSION_TTL:
            self._sessions.pop(session_id,None);raise HTTPException(410,'Chat session expired. No payment was completed.')
        return session

    def _purge(self):
        now=time()
        for key in [key for key,value in self._sessions.items() if now-value['updated']>self.SESSION_TTL]:self._sessions.pop(key,None)

    @staticmethod
    def _validate_message(message):
        if _SECRET.search(message):raise HTTPException(422,'Do not enter passwords, PINs, OTPs, CVVs, or card details.')
