# Day 3 — file-by-file implementation



## Day 3 — payment context and scam scenarios

Implemented: payment-context schema, explainable context rules, centralized scenario taxonomy, diverse synthetic English/Hinglish narratives, TF-IDF logistic regression and linear SVM comparison, structured-plus-text inference, top-three scenario candidates, contextual risk API, and Day 2/Day 3 integration. Psychological manipulation classification and graph-network intelligence are not implemented yet. All outputs remain preliminary evidence scores, not a final APP fraud probability.

### Generate, train, evaluate and run

Run these commands from app-shield with the existing environment and Day 2 models:

~~~powershell
.venv\Scripts\python -m scripts.generate_scam_messages
.venv\Scripts\python -m scripts.analyze_scam_messages
.venv\Scripts\python -m ml.scenario.train
.venv\Scripts\python -m ml.scenario.evaluate
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
# In another terminal while the API is running:
.venv\Scripts\python -m scripts.smoke_contextual_api
~~~

Restart the API after training. The TF-IDF vectorizer and classifier are saved together in saved_models/scenario_pipeline.pkl; taxonomy/version metadata is adjacent. Model, vocabulary and taxonomy are cached at startup. No per-request training, CSV reads, or LLM calls occur. If only the text artifact is missing, structured scenario rules and both Day 2 risk engines continue working; the response reports text_model_unavailable_rule_fallback when a message was supplied.

### Context and input semantics

POST /api/v1/risk/contextual accepts transaction, context, and optional message. The transaction block reuses the Day 2 request/schema. Put the expanded Day 3 payment_reason in context (romance, marketplace, tech_support, emergency and existing Day 1 reasons, including legacy relationship). Use actual synthetic account IDs and an explicit timezone, as in the example below. Unknown accounts return 404; invalid fields, naive timestamps, unsupported reasons and conflicting message sources return 422.

All circumstance booleans are optional and strict: missing/null means unknown, not false. user_message inside context is an alternative to the top-level message; if both are supplied they must match. Empty/whitespace text is treated as missing. Text is capped at 4,000 characters. Additional explicit fields fund_transfer_requested, guaranteed_returns_promised and online_relationship allow evidence to be reported without guessing it from a vague payment reason. promised_profit alone does not imply a guaranteed return. Context scoring treats new-recipient status as server-derived Day 2 evidence, never as a client assertion.

Context rules stack signals and combinations. Unknown contact, authority, urgency and threats together produce high scores; single signals do not yield maximum risk. Ordinary family payments and voluntary registered investment-like payments with no reported pressure stay low. Remote access plus a transfer instruction, job fees and unsolicited profit promises add interpretable reason codes. Missing circumstances yield insufficient_context_information and context_available=false; a zero context score in that case is not proof of safety.

### Scenario evidence and fusion

The only taxonomy list is ml/scenario/labels.json. Rule mappings, templates, model artifacts and response validators check that taxonomy. The text pipeline consumes text only; labels, message IDs, template IDs, language and split fields never enter predictors.

Without a message, structured rules infer scenarios such as fake_job_scam. With both text and a matching structured pattern, evidence scores use 65% structured rules and 35% text. Explicit structured patterns take priority because the text baseline generalizes imperfectly; disagreements are reported as text_context_disagreement. Without a structured match, the text model supplies the narrative evidence; low-confidence/low-margin text can abstain to normal_or_unknown. Top-three scores and confidence are MVP evidence strengths and need not sum to one. They are not calibrated probabilities. Text-support terms are linear model associations, not independent factual verification.

calculate_scenario_risk requires a non-normal scenario, matching structured evidence strength >=0.55 and context score >=20. Its provisional score is context_score × (0.65 + 0.35 × scenario_confidence). Normal/unknown or unsupported text-only predictions get scenario risk zero; high narrative confidence alone cannot produce high fraud risk.

extended_preliminary_risk = 0.25×transaction + 0.30×recipient + 0.25×context + 0.20×scenario_risk. These temporary hand-tuned weights are not production-calibrated. When structured circumstances are missing, existing Day 2 preliminary risk is retained as a minimum, with day2_risk_retained_missing_context; absent answers cannot erase known evidence. All thresholds/weights are in backend/app/config/context_config.py and the existing risk_config.py.

The original /api/v1/risk/preliminary contract remains unchanged. The new endpoint returns nested transaction/recipient/context scores, a scenario object, separate scenario_risk, extended_preliminary_risk, risk_level and merged reason_codes. Each layer includes reasons and relevant evidence.

### Synthetic corpus and evaluation limits

The corpus contains **5499 unique messages** across 11 classes (499–500 per class), from **110 narrative families**. One normalized exact duplicate was removed. Amount, caller name, channel, deadlines, style and message framing vary. English and Hinglish base narratives are balanced; framing phrases may mix languages. Legitimate-like examples include bank, investment, job and marketplace wording, rather than a keyword-only normal class.

Families stay together in class/language-balanced 60/20/20 train/validation/test splits. Each language/class contributes three families to training, one to validation and one to test. This is stricter than random row stratification and prevents variants of a template leaking into the test set. Training vocabulary is fit only on training messages; model selection uses validation macro F1. No test data or the separate 55-message manual Hinglish holdout is used for model selection or training.

| Model | Validation macro F1 | Test macro F1 |
| --- | ---: | ---: |
| tfidf_logistic_regression | 0.567 | 0.630 |
| tfidf_linear_svm | 0.558 | 0.649 |

Selected **tfidf_logistic_regression** by validation macro F1, even though the SVM scores higher on this particular test partition. Selected-model test accuracy is 0.661, macro precision 0.648, macro recall 0.661, macro F1 0.630.

| Selected model language slice | Accuracy | Macro F1 |
| --- | ---: | ---: |
| English generated holdout | 0.642 | 0.608 |
| Hinglish generated holdout | 0.680 | 0.621 |
| Independently authored Hinglish, 55 messages | 0.764 | 0.761 |

| Scenario | Test precision | Test recall | Test F1 |
| --- | ---: | ---: | ---: |
| normal_or_unknown | 0.505 | 0.500 | 0.503 |
| government_impersonation | 0.660 | 0.990 | 0.792 |
| bank_impersonation | 0.375 | 0.270 | 0.314 |
| investment_scam | 0.000 | 0.000 | 0.000 |
| fake_job_scam | 1.000 | 1.000 | 1.000 |
| tech_support_scam | 0.405 | 1.000 | 0.576 |
| romance_scam | 0.962 | 0.500 | 0.658 |
| family_emergency_scam | 0.574 | 0.700 | 0.631 |
| marketplace_scam | 0.667 | 0.500 | 0.571 |
| loan_scam | 0.980 | 1.000 | 0.990 |
| refund_scam | 1.000 | 0.810 | 0.895 |

The text-only baseline has substantial weaknesses. Held-out investment narratives are often confused with tech support or family emergencies; marketplace and romance narratives can also be confused with tech support. Bank/government impersonation and refund/marketplace distinctions remain difficult. Legitimate bank and shop messages can be misclassified because vocabulary alone does not reliably capture negation or intent. Failure counts often cluster by held-out template family, which is why thousands of generated variants do not equal thousands of independent real-world examples.

Reports preserve every class's precision/recall/F1, the complete labeled confusion matrix, most common confusions, English/Hinglish slices, top model terms, and manual-Hinglish errors. Dataset analysis includes class balance, text lengths, duplicates, exact overlap, template overlap and frequent words. Files are under data/processed/day3/. Review these failures before expanding data or retraining; no blind retraining was performed using the manual holdout.

Synthetic results and the small manual holdout do not establish real-world accuracy. Context is user-reported, text may be inaccurate or unrelated, and confidence is uncalibrated. The scoring pipeline does not authenticate authority claims or verify a recipient's registration status. The existing Day 2 data approximations remain applicable.

### Verified live examples

- government: scenario=government_impersonation; context=100.00; extended=90.32; level=CRITICAL.
- legitimate_investment: scenario=normal_or_unknown; context=0.00; extended=0.06; level=LOW.
- job_without_text: scenario=fake_job_scam; context=60.00; extended=72.78; level=HIGH.

All **138 tests pass** across Days 1–3. One upstream Starlette TestClient deprecation warning remains. The live HTTP smoke check confirms Day 2 compatibility and saves full request/response examples in data/processed/day3/contextual_api_examples.json.

Example request:

~~~json
{
  "transaction": {
    "sender_id": "A0001",
    "receiver_id": "A1006",
    "amount": 85000,
    "timestamp": "2026-01-30T23:31:50+00:00",
    "device_id": "D0001",
    "payment_type": "bank_transfer"
  },
  "context": {
    "payment_reason": "government",
    "contacted_by_unknown_person": true,
    "contact_channel": "phone",
    "claimed_authority": true,
    "authority_type": "police",
    "urgent_payment_requested": true,
    "threatened_consequences": true,
    "requested_secrecy": true,
    "fund_transfer_requested": true
  },
  "message": "Cyber Crime Department said my Aadhaar was involved in money laundering. Transfer the funds immediately to avoid legal action."
}
~~~

Send it to POST http://127.0.0.1:8000/api/v1/risk/contextual, or run scripts.smoke_contextual_api. Expected scenario: government_impersonation; context score: 100; extended score: 90.32; level: CRITICAL with the seeded artifacts. The complete response is in DAY3_IMPLEMENTATION.md and the example JSON report.


## Complete changed/new source files

## ml/scenario/labels.json

Single source of truth for the eleven scenario labels.

~~~json
[
  "normal_or_unknown",
  "government_impersonation",
  "bank_impersonation",
  "investment_scam",
  "fake_job_scam",
  "tech_support_scam",
  "romance_scam",
  "family_emergency_scam",
  "marketplace_scam",
  "loan_scam",
  "refund_scam"
]

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## ml/scenario/__init__.py

Empty package initializer.

~~~python

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## backend/app/config/context_config.py

Central Day 3 MVP weights and evidence thresholds, not calibrated probabilities.

~~~python
"""Central Day 3 MVP weights and evidence thresholds, not calibrated probabilities."""
from backend.app.config.risk_config import PROJECT_ROOT, MODEL_DIR

LABELS_PATH = PROJECT_ROOT / 'ml' / 'scenario' / 'labels.json'
SCENARIO_MODEL_PATH = MODEL_DIR / 'scenario_pipeline.pkl'
SCENARIO_DATA_PATH = PROJECT_ROOT / 'data' / 'synthetic' / 'scam_messages.csv'
SCENARIO_REPORT_DIR = PROJECT_ROOT / 'data' / 'processed' / 'day3'
CONTEXT_POINTS = {
    'unknown_contact': 10, 'authority_claim': 15, 'urgent_payment_request': 10,
    'threatened_consequences': 20, 'promised_profit_claim': 15,
    'guaranteed_profit_claim': 10, 'secrecy_request': 10, 'remote_access_request': 20,
    'payment_fee_request': 10, 'fund_transfer_request': 10,
    'authority_threat_urgency_combination': 30, 'unsolicited_profit_offer': 35,
    'profit_offer_new_recipient': 10, 'job_fee_request': 40,
    'bank_support_transfer_request': 25, 'remote_access_payment_instruction': 30,
    'online_relationship_money_request': 20,
}
EXTENDED_WEIGHTS = {'transaction': .25, 'recipient': .30, 'context': .25, 'scenario': .20}
TEXT_WEIGHT = .35
CONTEXT_SCENARIO_WEIGHT = .65
MIN_SCENARIO_EVIDENCE = .55
MODEL_MIN_CONFIDENCE = .40
MODEL_MIN_MARGIN = .10
MIN_CONTEXT_FOR_SCENARIO_RISK = 20
MAX_MESSAGE_LENGTH = 4000
MAX_CONTEXT_PERSON_LENGTH = 120
SCENARIO_SEED = 42
SAMPLES_PER_TEMPLATE = 50

SCENARIO_RISK_CONTEXT_FACTOR = .65
SCENARIO_RISK_CONFIDENCE_FACTOR = .35
PRESERVE_DAY2_WITHOUT_CONTEXT = True

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## backend/app/utils/scenario_labels.py

Load the scenario taxonomy once from its single JSON source of truth.

~~~python
"""Load the scenario taxonomy once from its single JSON source of truth."""
import json
from functools import lru_cache
from backend.app.config.context_config import LABELS_PATH


@lru_cache(maxsize=1)
def get_scenario_labels() -> tuple[str, ...]:
    labels = json.loads(LABELS_PATH.read_text(encoding='utf-8'))
    if not isinstance(labels, list) or not labels or len(labels) != len(set(labels)):
        raise ValueError('Scenario taxonomy must be a nonempty list of unique labels')
    if labels[0] != 'normal_or_unknown':
        raise ValueError('First taxonomy label must be normal_or_unknown')
    return tuple(labels)


def validate_scenario_label(label: str) -> str:
    if label not in get_scenario_labels():
        raise ValueError(f'Unknown scenario label: {label}')
    return label

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## backend/app/schemas/context.py

Optional structured circumstances; unknown answers remain distinct from false.

~~~python
"""Optional structured circumstances; unknown answers remain distinct from false."""
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from backend.app.schemas.transaction import PaymentReason
from backend.app.config.context_config import MAX_MESSAGE_LENGTH, MAX_CONTEXT_PERSON_LENGTH

ContextPaymentReason = PaymentReason | Literal['romance', 'marketplace', 'tech_support', 'emergency']


class ContactChannel(str, Enum):
    phone = 'phone'
    sms = 'sms'
    whatsapp = 'whatsapp'
    telegram = 'telegram'
    email = 'email'
    social_media = 'social_media'
    in_person = 'in_person'
    other = 'other'


class AuthorityType(str, Enum):
    police = 'police'
    government = 'government'
    bank = 'bank'
    rbi = 'rbi'
    tax_department = 'tax_department'
    court = 'court'
    company_support = 'company_support'
    employer = 'employer'
    none = 'none'
    other = 'other'


class PaymentContext(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    payment_reason: ContextPaymentReason = PaymentReason.other
    contacted_by_unknown_person: StrictBool | None = None
    contact_channel: ContactChannel | None = None
    who_requested_payment: str | None = Field(default=None, max_length=MAX_CONTEXT_PERSON_LENGTH)
    claimed_authority: StrictBool | None = None
    authority_type: AuthorityType | None = None
    urgent_payment_requested: StrictBool | None = None
    threatened_consequences: StrictBool | None = None
    promised_profit: StrictBool | None = None
    guaranteed_returns_promised: StrictBool | None = None
    requested_secrecy: StrictBool | None = None
    asked_to_install_remote_access: StrictBool | None = None
    asked_to_pay_fee: StrictBool | None = None
    fund_transfer_requested: StrictBool | None = None
    online_relationship: StrictBool | None = None
    relationship_duration_days: int | None = Field(default=None, ge=0, le=36500)
    user_message: str | None = Field(default=None, max_length=MAX_MESSAGE_LENGTH)

    @field_validator('user_message')
    @classmethod
    def normalize_message(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## backend/app/rules/context_rules.py

Stack structured APP-context evidence; a single signal never sets max risk.

~~~python
"""Stack structured APP-context evidence; a single signal never sets max risk."""
from backend.app.config.context_config import CONTEXT_POINTS
from backend.app.config.risk_config import clamp_score
from backend.app.schemas.context import PaymentContext


def calculate_context_risk(context: PaymentContext, new_recipient: bool = False) -> dict:
    flags = {
        'unknown_contact': context.contacted_by_unknown_person is True,
        'authority_claim': context.claimed_authority is True,
        'urgent_payment_request': context.urgent_payment_requested is True,
        'threatened_consequences': context.threatened_consequences is True,
        'promised_profit_claim': context.promised_profit is True,
        'guaranteed_profit_claim': context.guaranteed_returns_promised is True,
        'secrecy_request': context.requested_secrecy is True,
        'remote_access_request': context.asked_to_install_remote_access is True,
        'payment_fee_request': context.asked_to_pay_fee is True,
        'fund_transfer_request': context.fund_transfer_requested is True,
    }
    reason = context.payment_reason
    profit = flags['promised_profit_claim'] or flags['guaranteed_profit_claim']
    combinations = {
        'authority_threat_urgency_combination': all(flags[key] for key in (
            'unknown_contact', 'authority_claim', 'urgent_payment_request', 'threatened_consequences')),
        'unsolicited_profit_offer': reason == 'investment' and profit and flags['unknown_contact'],
        'profit_offer_new_recipient': reason == 'investment' and profit and new_recipient,
        'job_fee_request': reason == 'job' and flags['payment_fee_request'],
        'bank_support_transfer_request': reason == 'bank_support' and flags['fund_transfer_request'],
        'remote_access_payment_instruction': flags['remote_access_request'] and flags['fund_transfer_request'],
        'online_relationship_money_request': reason in ('romance', 'relationship') and
            context.online_relationship is True and (flags['fund_transfer_request'] or flags['urgent_payment_request']),
    }
    evidence = flags | combinations
    reasons = [key for key, value in evidence.items() if value]
    score = sum(CONTEXT_POINTS[key] for key in reasons)
    available = any(value is not None for key, value in context.model_dump().items()
                    if key not in ('payment_reason', 'user_message'))
    return {'score': clamp_score(score), 'reasons': reasons or (['no_reported_context_risk_signals'] if available else ['insufficient_context_information']),
            'evidence': {key: value for key, value in evidence.items() if value},
            'context_available': available}

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## backend/app/services/context_service.py

Payment context engine wrapping the independently testable rule scorer.

~~~python
"""Payment context engine wrapping the independently testable rule scorer."""
from backend.app.schemas.context import PaymentContext
from backend.app.rules.context_rules import calculate_context_risk


class ContextService:
    def calculate_context_risk(self, context: PaymentContext, new_recipient: bool = False) -> dict:
        return calculate_context_risk(context, new_recipient)

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## backend/app/rules/scenario_rules.py

Structured narrative classification. Evidence strengths are heuristic, not probabilities.

~~~python
"""Structured narrative classification. Evidence strengths are heuristic, not probabilities."""
from backend.app.schemas.context import PaymentContext
from backend.app.utils.scenario_labels import get_scenario_labels


def classify_scenario_rules(context: PaymentContext) -> dict:
    labels = get_scenario_labels()
    scores = dict.fromkeys(labels, 0.0)
    reasons: dict[str, list[str]] = {label: [] for label in labels}
    reason, authority = context.payment_reason, context.authority_type
    threat = context.threatened_consequences is True
    urgency = context.urgent_payment_requested is True
    unknown = context.contacted_by_unknown_person is True
    claim = context.claimed_authority is True
    fee = context.asked_to_pay_fee is True
    transfer = context.fund_transfer_requested is True
    profit = context.promised_profit is True or context.guaranteed_returns_promised is True
    remote = context.asked_to_install_remote_access is True
    online = context.online_relationship is True or context.contact_channel in ('social_media', 'telegram', 'whatsapp')

    def support(label: str, strength: float, codes: list[str]) -> None:
        scores[label], reasons[label] = strength, codes

    if claim and (reason == 'government' or authority in ('police', 'government', 'rbi', 'tax_department', 'court')) and (threat or urgency or transfer):
        support('government_impersonation', min(.98, .55 + .15*threat + .10*urgency + .10*unknown),
                ['authority_claim', 'government_impersonation_pattern'] + (['crime_or_legal_threat'] if threat else []))
    if (reason == 'bank_support' or authority == 'bank') and claim and (threat or transfer or urgency):
        support('bank_impersonation', min(.96, .55 + .15*threat + .15*transfer + .10*unknown),
                ['bank_authority_claim', 'bank_impersonation_pattern'])
    if reason == 'investment' and profit and (unknown or transfer or urgency):
        support('investment_scam', min(.96, .60 + .15*unknown + .10*transfer + .10*urgency),
                ['profit_offer', 'investment_payment_pattern'])
    if reason == 'job' and fee:
        support('fake_job_scam', .80 + .10*unknown, ['job_fee_request', 'fake_job_payment_pattern'])
    if remote and (reason in ('tech_support', 'bank_support') or authority == 'company_support'):
        support('tech_support_scam', min(.98, .65 + .15*transfer + .10*unknown),
                ['remote_access_request', 'support_payment_pattern'])
    if reason in ('romance', 'relationship') and online and (transfer or urgency or fee):
        support('romance_scam', .65 + .15*urgency + .10*unknown,
                ['online_relationship_money_request', 'romance_payment_pattern'])
    if reason in ('family', 'friend', 'emergency') and urgency and (unknown or context.requested_secrecy is True):
        support('family_emergency_scam', .65 + .15*unknown, ['urgent_family_request', 'family_emergency_pattern'])
    if reason in ('shopping', 'marketplace') and (fee or transfer) and (unknown or urgency):
        support('marketplace_scam', .60 + .15*unknown + .10*urgency, ['marketplace_payment_pattern'])
    if reason == 'loan' and fee:
        support('loan_scam', .75 + .10*unknown, ['advance_loan_fee_request'])
    if reason == 'refund' and (fee or transfer or remote):
        support('refund_scam', min(.95, .65 + .10*unknown + .10*remote), ['payment_to_receive_refund'])
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        scores[labels[0]] = 1.0
        best = labels[0]
        reasons[best] = ['insufficient_scenario_evidence']
    return {'scenario': best, 'confidence': scores[best], 'scores': scores,
            'reason_codes': reasons[best], 'reasons_by_label': reasons}

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## scripts/scam_templates.py

Independent English/Hinglish narrative families, including legitimate hard negatives.

Each family is kept in one dataset split. Parameters change wording details, not labels.
No real identity numbers, bank secrets, or financial credentials are generated.


~~~python
"""Independent English/Hinglish narrative families, including legitimate hard negatives.

Each family is kept in one dataset split. Parameters change wording details, not labels.
No real identity numbers, bank secrets, or financial credentials are generated.
"""
TEMPLATES = {
    'normal_or_unknown': [
        'I am sending {amount} for our family groceries to the account we always use. No stranger contacted me.',
        'The registered investment fund receives my scheduled {amount} contribution. Returns are not guaranteed and nobody is rushing me.',
        'My bank appointment is at the branch. They said verification does not require moving {amount} to another account.',
        'The shop invoice for the delivered furniture is {amount}. I know the seller and checked the bill before paying.',
        'The recruiter confirmed there is no registration fee. I will not send {amount} to obtain a job or a refund.',
        'Ghar ke ration ke liye {amount} bhej raha hu. Ye mummy ka purana account hai, koi unknown call nahi aayi.',
        'Apne registered fund me monthly {amount} jama karna hai. Guaranteed profit nahi hai aur koi jaldi nahi kara raha.',
        'Police fine official portal par verify kiya. Kisi caller ne safe account me {amount} transfer nahi manga.',
        'Loan ki EMI {amount} mere existing lender ko deni hai. Approval ke liye advance fee ka koi message nahi aaya.',
        'Dost {name} ko dinner ke {amount} wapas de raha hu. Pehle mil kar baat hui, koi threat ya secrecy nahi.',
    ],
    'government_impersonation': [
        'Officer {name} says my identity was used in an illegal transfer. The caller orders me to move {amount} to a verification account {deadline} or face arrest.',
        'A person claiming to be from the Cyber Crime office called on {channel}. They demand {amount} in a safe account and tell me not to discuss the investigation.',
        'The supposed tax investigator says my records connect to money laundering. I must send {amount} {deadline} to stop a legal notice.',
        'Someone introduced themselves as court officer {name} and insists I transfer {amount} for identity clearance before they issue a warrant.',
        'An unexpected government caller claims an inquiry against me. They say only a payment of {amount} to their nominated account can keep me out of custody.',
        'Officer {name} bol raha hai mera Aadhaar illegal transfer me use hua. {amount} verification account me {deadline} bhejo warna arrest hoga.',
        'Cyber Crime department ke naam se {channel} par call aayi. Kehte hain {amount} safe account me dalo aur investigation kisi ko mat batao.',
        'Tax officer bolkar ek aadmi keh raha hai money laundering case hai. Legal notice rokne ke liye {amount} {deadline} transfer karna padega.',
        'Court se {name} ne phone kiya bolkar bataya warrant ready hai. Identity clear karne ko unke account me {amount} mang rahe hain.',
        'Sarkari inquiry ka unknown message mila. Caller kehta hai custody se bachne ke liye nominated account me {amount} bhejna zaroori hai.',
    ],
    'bank_impersonation': [
        'Caller {name} claims to work at my bank and says my account will be frozen. They need me to transfer {amount} to another account for verification {deadline}.',
        'A supposed fraud desk agent contacted me on {channel}. They instruct me to move {amount} into a temporary secure account so my balance is not blocked.',
        'The bank support caller says suspicious activity triggered a freeze. Paying {amount} to the account they supplied is required to restore access.',
        'Someone identifying as the bank manager asks me to relocate {amount} for account validation. They insist the transfer must happen {deadline}.',
        'An unexpected banking helpline call warns that my account is compromised. The agent wants {amount} sent to a protection wallet rather than the bank branch.',
        'Main bank se bol raha hu, caller ne kaha. Aapka account freeze hoga, verification ke liye {amount} abhi dusre account me transfer karo.',
        'Bank fraud desk ke naam par {channel} se contact hua. Balance block na ho isliye {amount} temporary safe account me mang rahe hain.',
        'Support wale bol rahe suspicious transaction flag hua hai. Account access wapas lane ko diye hue account par {amount} pay karna hoga.',
        'Manager {name} kehta hai account validation pending hai. {amount} secure wallet me {deadline} dalne ko bol raha hai.',
        'Unknown helpline ne account compromise ka dar dikhaya. Branch aane ki jagah protection account me {amount} bhejne ki instruction hai.',
    ],
    'investment_scam': [
        'A stranger on {channel} promises a guaranteed twenty percent monthly return. They ask me to deposit {amount} into a private account to join the plan.',
        'Advisor {name} found me online and claims my money will double without any risk. I have to send an initial {amount} {deadline}.',
        'The trading group says every member earns fixed daily profit. Their coordinator wants {amount} paid personally before enabling withdrawals.',
        'An unknown portfolio coach guarantees returns and sends screenshots of gains. They want {amount} transferred for a special allocation outside the registered platform.',
        'A social-media contact offers a no-loss wealth plan. They demand {amount} first and say the return is assured regardless of market prices.',
        '{channel} par unknown banda guaranteed bees percent monthly return bol raha. Private account me {amount} dal kar plan join karne ko keh raha hai.',
        'Online advisor {name} bolta hai bina risk paise double honge. Shuru karne ke liye {amount} {deadline} transfer mangta hai.',
        'Trading group har roz fixed profit ka wada karta hai. Withdrawal activate karne se pehle coordinator ko {amount} personally pay karo bol rahe.',
        'Unknown portfolio coach profit ke screenshots bhej raha. Registered app ke bahar special allocation ke liye {amount} mang raha hai.',
        'Social media par no loss wealth plan mila. Market kuch bhi kare assured return bolkar pehle {amount} jama karne ko keh rahe hain.',
    ],
    'fake_job_scam': [
        'Recruiter {name} contacted me on {channel} with a job offer. They require a registration payment of {amount} before sending the appointment letter.',
        'The hiring agent says I passed the interview but must pay {amount} as security to a personal account {deadline} to keep the role.',
        'A work-from-home recruiter requests {amount} for compulsory training before I can start earning. There is no signed contract yet.',
        'Someone offers me a guaranteed placement and wants {amount} sent for document clearance before sharing the employer details.',
        'An unexpected employment message says my seat is confirmed only after an equipment deposit of {amount}. The payment goes to the recruiter.',
        'Recruiter {name} ne {channel} se job offer diya. Appointment letter dene se pehle registration ke {amount} pay karo bol raha.',
        'Interview pass bolkar hiring agent personal account me {amount} security mang raha. {deadline} pay nahi kiya to role chala jayega.',
        'Work from home recruiter earning start karne se pehle compulsory training ke {amount} maangta hai. Abhi signed contract nahi hai.',
        'Guaranteed placement ka offer hai lekin employer details se pehle document clearance ke {amount} transfer bolte hain.',
        'Unknown employment message me seat confirm karne ke liye equipment deposit {amount} recruiter ko bhejna hai.',
    ],
    'tech_support_scam': [
        'An unknown support technician claims my computer is infected. They ask me to install a remote-control app and send {amount} while they guide the repair.',
        'Support caller {name} tells me to share remote screen access. After connecting they demand {amount} to remove a security warning {deadline}.',
        'A pop-up led to a helpdesk call where the agent wants control of my device. They say a transfer of {amount} is needed to restore protection.',
        'A supposed software specialist contacted me on {channel}, requested a remote session, and then asked me to pay {amount} for cleaning the machine.',
        'The unexpected repair agent asks me to install a screen-sharing tool and open my payment app. They instruct a transfer of {amount} to finish troubleshooting.',
        'Unknown support caller kehta computer infected hai. Remote control app install karke repair ke liye {amount} bhejo bolta hai.',
        'Technician {name} screen access mang raha. Connect hote hi security warning hatane ko {amount} {deadline} pay karne ko kehta.',
        'Popup se helpdesk par call hua. Agent device control lekar protection restore karne ke naam pe {amount} transfer bol raha.',
        '{channel} se software specialist ne remote session manga. Machine clean karne ke liye personal account me {amount} dene ko bolta hai.',
        'Repair wale screen sharing tool install aur payment app kholne ko kehte. Troubleshooting complete karne ke liye {amount} transfer ki instruction hai.',
    ],
    'romance_scam': [
        'Someone I met on a dating app says they love me but we have never met. They now need {amount} urgently for hospital treatment and want this kept between us.',
        'My online partner {name} claims they are stranded overseas. They request {amount} for travel documents before we can finally meet.',
        'A person who built a relationship with me on {channel} asks for {amount} to clear a parcel of gifts. They refuse a video call but insist I help {deadline}.',
        'The person I have dated only through messages promises to visit. They say I must transfer {amount} for emergency customs charges on their luggage.',
        'An online romantic contact shares an emotional story about medical debt. They ask me to send {amount} privately even though we have never spoken in person.',
        'Dating app par mila partner pyar bolta hai par kabhi mile nahi. Hospital emergency ke liye {amount} jaldi mangta aur chup rakhne ko kehta.',
        'Online partner {name} abroad phansa bol raha. Milne aane ke travel documents ke liye {amount} transfer chahiye.',
        '{channel} par relationship bani, ab gift parcel clear karne ke {amount} mang rahe. Video call nahi karte lekin {deadline} help zaroori bolte.',
        'Sirf messages par dating hui. Visit ka wada karke luggage customs emergency ke naam par {amount} pay karne ko kehte hain.',
        'Online romantic contact medical debt ki emotional kahani bhejta hai. Kabhi face to face nahi mile phir bhi privately {amount} mang raha.',
    ],
    'family_emergency_scam': [
        'A caller says they are my cousin using a new number and need {amount} after an accident. They insist I send it {deadline} without calling the family.',
        'Someone on {channel} claims my brother is detained and only a transfer of {amount} will release him. They demand secrecy and refuse to let me speak to him.',
        'An unfamiliar number says my daughter lost her phone and urgently needs {amount}. The payment account name is different and they say not to call.',
        'A person claiming to be a family friend says my father needs immediate surgery. They request {amount} before I can confirm with the hospital.',
        'The caller pretends to be my uncle and asks for {amount} for emergency bail. They warn me not to contact other relatives {deadline}.',
        'Naye number se cousin bolkar call aayi accident hua hai. Family ko call bina {amount} {deadline} bhejo kehte hain.',
        '{channel} par bhai detained bol rahe aur release ke liye {amount} mangte. Chup rehne ko kehte aur bhai se baat nahi karate.',
        'Unknown number beti ka phone lost bolta hai. Alag account name par {amount} urgent chahiye, phone mat karo kehte hain.',
        'Family friend banke aadmi papa ki surgery emergency bol raha. Hospital confirm karne se pehle {amount} transfer mangta hai.',
        'Caller uncle banke emergency bail ke {amount} maangta. {deadline} tak dusre relatives se contact mana karta hai.',
    ],
    'marketplace_scam': [
        'A buyer on the resale app asks me to scan a QR and send {amount} to receive their payment. They say this is a compulsory seller verification step.',
        'The seller contacted me on {channel} and wants an extra {amount} deposit outside the marketplace before shipping an item they cannot show live.',
        'A person buying my furniture says the payment is stuck. They demand I transfer {amount} to activate the merchant account before they pay me.',
        'An unknown marketplace seller insists on {amount} as courier insurance to a personal wallet {deadline}. The listing disappears when I ask for an invoice.',
        'The buyer sends a collect request for {amount} and tells me approving it will credit my account. They push me to do it before checking the transaction.',
        'Resale app ka buyer payment receive karne ke liye QR scan aur {amount} bhejo bolta hai. Seller verification compulsory keh raha.',
        '{channel} par seller item ship karne se pehle marketplace ke bahar extra {amount} deposit maangta. Live item nahi dikhata.',
        'Furniture buyer payment stuck bolkar merchant account activate karne ko {amount} transfer mang raha, tab mujhe paise dega.',
        'Unknown seller courier insurance ke {amount} personal wallet me {deadline} mangta. Invoice puchne par listing gayab hai.',
        'Buyer {amount} ka collect request bhejkar approve karne se credit hoga bolta. Transaction check bina jaldi approve karwa raha.',
    ],
    'loan_scam': [
        'An unknown lender offers instant approval but asks for {amount} in processing fees before releasing the loan to me.',
        'Agent {name} says my borrowing request is approved. I must send {amount} as a refundable security payment to their personal account {deadline}.',
        'A loan contact on {channel} promises funds without paperwork. They require an advance {amount} insurance charge before any disbursement.',
        'Someone claiming to be a finance officer demands {amount} for credit clearance. They say my approved loan will stay locked until I pay.',
        'The lending app representative wants {amount} in an outside wallet to verify eligibility. The loan balance never arrives until these charges are paid.',
        'Unknown lender instant approval deta par loan release se pehle processing fee ke {amount} mangta hai.',
        'Agent {name} borrowing approved bolta hai. Personal account me refundable security {amount} {deadline} bhejne ko keh raha.',
        '{channel} par bina paperwork loan promise hua. Disbursement se pehle advance insurance charge {amount} pay karo bolte hain.',
        'Finance officer bolkar credit clearance ke {amount} mang rahe. Fee pay bina approved loan locked rahega kehte hain.',
        'Lending app representative eligibility verify karne ke {amount} outside wallet me chahta. Charges bina loan balance nahi aa raha.',
    ],
    'refund_scam': [
        'Someone claiming to handle my refund asks me to transfer {amount} first. They say the reversal cannot be released without a payment verification.',
        'Refund agent {name} contacted me on {channel}. They need an advance {amount} tax charge before returning money for a cancelled purchase.',
        'A supposed merchant refund team sends a QR and asks me to approve a debit of {amount} to receive my reimbursement {deadline}.',
        'The caller says they accidentally refunded too much and wants {amount} sent to a personal account before I check my actual balance.',
        'An unexpected customer-care message tells me to pay {amount} as a release fee for a pending refund instead of contacting the original merchant.',
        'Refund handle karne wala pehle {amount} transfer mangta. Payment verification bina reversal release nahi hoga kehta.',
        'Agent {name} ne {channel} se contact kiya. Cancelled purchase ka refund dene se pehle advance tax charge {amount} chahiye.',
        'Merchant refund team ke naam par QR aur {amount} debit approve karne ko kehte. {deadline} reimbursement receive hoga bol rahe.',
        'Caller extra refund ho gaya bolkar actual balance check se pehle personal account me {amount} wapas mangta.',
        'Unknown customer care pending refund release fee {amount} bolta. Original merchant se baat karne ki jagah unko pay karna hai.',
    ],
}

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## scripts/generate_scam_messages.py

Reproducible synthetic narrative corpus with family-disjoint, class-balanced splits.

~~~python
"""Reproducible synthetic narrative corpus with family-disjoint, class-balanced splits."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from backend.app.config.context_config import SCENARIO_SEED, SAMPLES_PER_TEMPLATE, SCENARIO_DATA_PATH
from backend.app.utils.scenario_labels import get_scenario_labels
from scripts.scam_templates import TEMPLATES

NAMES = ('Sharma', 'Patel', 'Khan', 'Mehta', 'Rao', 'Roy', 'Kapoor', 'Verma')
CHANNELS = ('phone', 'SMS', 'WhatsApp', 'Telegram', 'email', 'social media')
DEADLINES = ('immediately', 'within an hour', 'before tonight', 'today', 'abhi', 'aaj hi')
PREFIXES = ('', 'This is what they told me: ', 'Please help me understand this message. ', 'Mujhe ye message mila: ')
SUFFIXES = ('', ' Is this the right way to pay?', ' They keep asking me to respond.', ' Kya mujhe ye payment karna chahiye?')


def normalized_text(text: str) -> str:
    return ' '.join(text.casefold().split())


def generate_messages(seed: int = SCENARIO_SEED, samples_per_template: int = SAMPLES_PER_TEMPLATE) -> pd.DataFrame:
    if samples_per_template < 1:
        raise ValueError('samples_per_template must be positive')
    labels = get_scenario_labels()
    if set(TEMPLATES) != set(labels):
        raise ValueError('Template taxonomy does not match labels.json')
    rng = np.random.default_rng(seed)
    rows = []
    for label in labels:
        templates = TEMPLATES[label]
        if len(templates) != 10:
            raise ValueError('Each class needs five English and five Hinglish narrative families')
        roles = {}
        for offset in (0, 5):
            groups = rng.permutation(np.arange(offset, offset + 5))
            for index, group in enumerate(groups):
                roles[int(group)] = 'train' if index < 3 else 'validation' if index == 3 else 'test'
        for template_index, template in enumerate(templates):
            for _ in range(samples_per_template):
                amount = f'₹{int(rng.integers(10, 1500)) * 100:,}'
                text = template.format(amount=amount, name=rng.choice(NAMES), channel=rng.choice(CHANNELS),
                                       deadline=rng.choice(DEADLINES))
                text = str(rng.choice(PREFIXES)) + text + str(rng.choice(SUFFIXES))
                style = rng.random()
                if style < .04:
                    text = text.upper()
                elif style < .12:
                    text = text.lower()
                elif style < .18:
                    text = text.replace('please', 'pls').replace('immediately', 'immediatly').replace('account', 'acount')
                rows.append({'message_id': f'MSG{len(rows):06d}', 'text': text, 'scenario_label': label,
                             'template_id': f'{label}:{template_index}',
                             'language': 'English' if template_index < 5 else 'Hinglish',
                             'split': roles[template_index]})
    data = pd.DataFrame(rows)
    data['_normalized'] = data.text.map(normalized_text)
    data = data.drop_duplicates('_normalized').drop(columns='_normalized')
    return data.sample(frac=1, random_state=seed).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=SCENARIO_SEED)
    parser.add_argument('--samples-per-template', type=int, default=SAMPLES_PER_TEMPLATE)
    parser.add_argument('--output', type=Path, default=SCENARIO_DATA_PATH)
    args = parser.parse_args()
    data = generate_messages(args.seed, args.samples_per_template)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(args.output, index=False)
    print(f'Saved {len(data)} unique messages to {args.output}')
    print(data.groupby(['scenario_label', 'split']).size().unstack().to_string())


if __name__ == '__main__':
    main()

~~~

Run/check: `.venv\Scripts\python -m scripts.generate_scam_messages`.

## ml/scenario/data_quality.py

Corpus validation and transparent split/duplicate/lexical quality analysis.

~~~python
"""Corpus validation and transparent split/duplicate/lexical quality analysis."""
from collections import Counter
import re
import pandas as pd
from backend.app.utils.scenario_labels import get_scenario_labels
from scripts.generate_scam_messages import normalized_text


def validate_messages(data: pd.DataFrame) -> dict:
    required = {'message_id', 'text', 'scenario_label', 'template_id', 'language', 'split'}
    missing = required - set(data)
    if missing:
        raise ValueError(f'Missing scenario dataset columns: {sorted(missing)}')
    if data.empty or data[list(required)].isna().any().any():
        raise ValueError('Scenario dataset is empty or has missing required values')
    labels = get_scenario_labels()
    if set(data.scenario_label) != set(labels):
        raise ValueError('Dataset must contain every valid scenario class and no unknown labels')
    if data.message_id.duplicated().any():
        raise ValueError('Duplicate message IDs')
    normalized = data.text.map(normalized_text)
    if normalized.eq('').any() or normalized.duplicated().any():
        raise ValueError('Empty or duplicated normalized messages')
    if set(data.split) != {'train', 'validation', 'test'}:
        raise ValueError('Expected train, validation and test partitions')
    if data.groupby('template_id').split.nunique().max() != 1:
        raise ValueError('Template-family leakage across dataset splits')
    if data.groupby('template_id').scenario_label.nunique().max() != 1:
        raise ValueError('Template family cannot have conflicting targets')
    for role in ('train', 'validation', 'test'):
        if set(data.loc[data.split == role, 'scenario_label']) != set(labels):
            raise ValueError(f'{role} split is missing classes')
    # Reject direct label leakage in synthetic text, while allowing natural narrative words.
    if any(normalized.str.contains(re.escape(label), regex=True).any() for label in labels):
        raise ValueError('Scenario label text leaked into messages')
    common_words = {}
    for label, group in data.groupby('scenario_label'):
        tokens = re.findall(r'[a-z]{3,}', ' '.join(group.text).casefold())
        common_words[label] = dict(Counter(tokens).most_common(15))
    return {
        'rows': len(data), 'classes': data.scenario_label.value_counts().to_dict(),
        'average_text_length': float(data.text.str.len().mean()),
        'text_length_by_class': data.groupby('scenario_label').text.apply(lambda values: float(values.str.len().mean())).to_dict(),
        'duplicate_normalized_messages': int(normalized.duplicated().sum()),
        'train_test_message_overlap': len(set(normalized[data.split == 'train']) & set(normalized[data.split == 'test'])),
        'train_test_template_overlap': len(set(data.loc[data.split == 'train', 'template_id']) &
                                            set(data.loc[data.split == 'test', 'template_id'])),
        'template_families': int(data.template_id.nunique()),
        'split_counts': data.groupby(['split', 'scenario_label']).size().unstack(fill_value=0).to_dict('index'),
        'language_distribution': data.language.value_counts().to_dict(), 'most_common_words': common_words,
    }

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## ml/scenario/metrics.py

Multiclass metrics, per-language diagnostics and commonly confused narratives.

~~~python
"""Multiclass metrics, per-language diagnostics and commonly confused narratives."""
import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
from backend.app.utils.scenario_labels import get_scenario_labels


def classification_metrics(actual, predicted) -> dict:
    labels = list(get_scenario_labels())
    precision, recall, f1, support = precision_recall_fscore_support(actual, predicted, labels=labels, zero_division=0)
    matrix = confusion_matrix(actual, predicted, labels=labels)
    confusions = [{'actual': labels[i], 'predicted': labels[j], 'count': int(matrix[i, j])}
                  for i in range(len(labels)) for j in range(len(labels)) if i != j and matrix[i, j] > 0]
    confusions.sort(key=lambda item: item['count'], reverse=True)
    return {'accuracy': float(accuracy_score(actual, predicted)),
            'macro_precision': float(np.mean(precision)), 'macro_recall': float(np.mean(recall)),
            'macro_f1': float(np.mean(f1)), 'sample_count': len(actual),
            'per_class': {label: {'precision': float(precision[i]), 'recall': float(recall[i]),
                                 'f1': float(f1[i]), 'support': int(support[i])} for i, label in enumerate(labels)},
            'confusion_matrix_labels': labels, 'confusion_matrix': matrix.tolist(),
            'most_common_confusions': confusions[:12]}


def evaluate_pipeline(model, data) -> dict:
    predictions = model.predict(data.text)
    result = classification_metrics(data.scenario_label, predictions)
    result['by_language'] = {}
    for language in data.language.unique():
        mask = data.language.eq(language).to_numpy()
        result['by_language'][language] = classification_metrics(data.scenario_label[mask], predictions[mask])
    return result

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## ml/scenario/train.py

Compare TF-IDF logistic regression and linear SVM on unseen template families.

~~~python
"""Compare TF-IDF logistic regression and linear SVM on unseen template families."""
import hashlib
import json
import joblib
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from backend.app.config.context_config import SCENARIO_DATA_PATH, SCENARIO_MODEL_PATH, SCENARIO_REPORT_DIR, SCENARIO_SEED
from backend.app.utils.scenario_labels import get_scenario_labels
from ml.scenario.data_quality import validate_messages
from ml.scenario.metrics import evaluate_pipeline


def make_pipeline(classifier) -> Pipeline:
    return Pipeline([('tfidf', TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=18000,
        sublinear_tf=True, strip_accents='unicode')), ('classifier', classifier)])


def train() -> dict:
    data = pd.read_csv(SCENARIO_DATA_PATH)
    quality = validate_messages(data)
    print(f"Validated {len(data)} unique messages, {quality['template_families']} disjoint template families")
    train_data, validation, test = (data[data.split == role] for role in ('train', 'validation', 'test'))
    models = {
        'tfidf_logistic_regression': make_pipeline(LogisticRegression(C=4, max_iter=2000,
            class_weight='balanced', random_state=SCENARIO_SEED)),
        'tfidf_linear_svm': make_pipeline(LinearSVC(C=1, dual='auto', class_weight='balanced', random_state=SCENARIO_SEED)),
    }
    reports = {}
    for name, model in models.items():
        # Inputs are text only. No labels, source-template identifiers or split flags enter the pipeline.
        model.fit(train_data.text, train_data.scenario_label)
        reports[name] = {'validation': evaluate_pipeline(model, validation), 'test': evaluate_pipeline(model, test)}
    selected = max(reports, key=lambda name: reports[name]['validation']['macro_f1'])
    classifier = models[selected].named_steps['classifier']
    metadata = {'selected_model': selected, 'selected_by': 'validation macro F1', 'seed': SCENARIO_SEED,
        'sklearn_version': sklearn.__version__, 'labels': list(get_scenario_labels()), 'input_features': ['text'],
        'split_strategy': '60/20/20 class/language balanced; template families stay in one split',
        'confidence_kind': 'uncalibrated logistic output' if hasattr(classifier, 'predict_proba') else 'softmax of SVM margins; heuristic evidence',
        'dataset_sha256': hashlib.sha256(SCENARIO_DATA_PATH.read_bytes()).hexdigest(),
        'limitations': 'Synthetic narratives, only 110 source families. No real-world performance or calibrated fraud probability.'}
    SCENARIO_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCENARIO_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({'schema_version': 1, 'kind': 'scenario', 'pipeline': models[selected], 'metadata': metadata}, SCENARIO_MODEL_PATH)
    SCENARIO_MODEL_PATH.with_suffix('.metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    report = {'metadata': metadata, 'models': reports, 'dataset_quality': quality}
    (SCENARIO_REPORT_DIR / 'scenario_evaluation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (SCENARIO_REPORT_DIR / 'dataset_quality.json').write_text(json.dumps(quality, indent=2), encoding='utf-8')
    features = models[selected].named_steps['tfidf'].get_feature_names_out()
    coefficients = classifier.coef_
    importance = {label: [str(features[index]) for index in coefficients[i].argsort()[-12:][::-1]]
                  for i, label in enumerate(classifier.classes_)}
    (SCENARIO_REPORT_DIR / 'top_class_terms.json').write_text(json.dumps(importance, indent=2), encoding='utf-8')
    for name, metrics in reports.items():
        print(f"{name}: validation macro F1={metrics['validation']['macro_f1']:.3f}, test macro F1={metrics['test']['macro_f1']:.3f}")
    print(f'Selected {selected} by validation results; saved {SCENARIO_MODEL_PATH}')
    return report


if __name__ == '__main__':
    train()

~~~

Run/check: `.venv\Scripts\python -m ml.scenario.train`.

## backend/app/models/scenario_model.py

Startup-loaded, text-only scenario classifier with lightweight term evidence.

~~~python
"""Startup-loaded, text-only scenario classifier with lightweight term evidence."""
from pathlib import Path
import joblib
import numpy as np
from backend.app.config.context_config import SCENARIO_MODEL_PATH
from backend.app.utils.scenario_labels import get_scenario_labels


class ScenarioModel:
    def __init__(self, artifact_path: Path = SCENARIO_MODEL_PATH):
        artifact = joblib.load(artifact_path)  # locally trained, trusted artifact only
        if (artifact.get('kind') != 'scenario' or artifact.get('schema_version') != 1 or
                artifact.get('metadata', {}).get('labels') != list(get_scenario_labels())):
            raise ValueError('Incompatible scenario model; retrain with the current taxonomy')
        self.pipeline = artifact['pipeline']
        self.metadata = artifact['metadata']
        self.vectorizer = self.pipeline.named_steps['tfidf']
        self.classifier = self.pipeline.named_steps['classifier']
        if set(self.classifier.classes_) != set(get_scenario_labels()):
            raise ValueError('Scenario artifact is missing taxonomy classes')
        self.feature_names = self.vectorizer.get_feature_names_out()

    def predict(self, text: str) -> dict:
        vector = self.vectorizer.transform([text])
        labels = get_scenario_labels()
        if vector.nnz == 0:
            return {'scores': {label: float(label == labels[0]) for label in labels},
                    'scenario': labels[0], 'confidence_kind': 'no_supported_text_tokens', 'support_terms': []}
        if hasattr(self.classifier, 'predict_proba'):
            weights = self.classifier.predict_proba(vector)[0]
            kind = 'uncalibrated_logistic_output'
        else:
            margins = self.classifier.decision_function(vector)[0]
            weights = np.exp(margins - np.max(margins))
            weights /= weights.sum()
            kind = 'svm_margin_softmax_evidence'
        scores = {str(label): float(weight) for label, weight in zip(self.classifier.classes_, weights)}
        best = max(scores, key=scores.get)
        class_index = list(self.classifier.classes_).index(best)
        columns = vector.indices
        contributions = vector.data * self.classifier.coef_[class_index, columns]
        order = np.argsort(contributions)[::-1]
        terms = [str(self.feature_names[columns[i]]) for i in order[:5] if contributions[i] > 0]
        return {'scores': scores, 'scenario': best, 'confidence_kind': kind, 'support_terms': terms}

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## backend/app/services/scenario_service.py

Complement text evidence with structured narrative rules, without equating confidence to risk.

~~~python
"""Complement text evidence with structured narrative rules, without equating confidence to risk."""
from backend.app.config.context_config import (TEXT_WEIGHT, CONTEXT_SCENARIO_WEIGHT,
    MODEL_MIN_CONFIDENCE, MODEL_MIN_MARGIN, MIN_SCENARIO_EVIDENCE, MIN_CONTEXT_FOR_SCENARIO_RISK,
    SCENARIO_RISK_CONTEXT_FACTOR, SCENARIO_RISK_CONFIDENCE_FACTOR)
from backend.app.config.risk_config import clamp_score
from backend.app.models.scenario_model import ScenarioModel
from backend.app.schemas.context import PaymentContext
from backend.app.rules.scenario_rules import classify_scenario_rules
from backend.app.rules.context_rules import calculate_context_risk
from backend.app.utils.scenario_labels import get_scenario_labels, validate_scenario_label


class ScenarioService:
    def __init__(self, model: ScenarioModel | None = None):
        self.model = model

    def predict_scenario(self, text: str | None, structured_context: PaymentContext) -> dict:
        labels = get_scenario_labels()
        rules = classify_scenario_rules(structured_context)
        message = (text or structured_context.user_message or '').strip()
        text_result = self.model.predict(message) if message and self.model else None
        rule_matches = rules['scenario'] != labels[0]
        if text_result and rule_matches:
            context_weight = CONTEXT_SCENARIO_WEIGHT
            scores = {label: TEXT_WEIGHT * text_result['scores'][label] +
                      context_weight * rules['scores'][label] for label in labels}
            kind = 'structured_and_text_evidence'
        elif text_result:
            scores = text_result['scores'].copy()
            kind = text_result['confidence_kind']
        else:
            scores = rules['scores'].copy()
            kind = 'structured_rule_evidence' if rule_matches else 'insufficient_evidence'
        ranked = sorted(scores, key=scores.get, reverse=True)
        best = ranked[0]
        confidence = scores[best]
        codes = list(rules['reasons_by_label'][best])
        if text_result:
            codes.append('text_classifier_evidence')
            if rule_matches and rules['scenario'] != text_result['scenario']:
                codes.append('text_context_disagreement')
        if message and self.model is None:
            codes.append('text_model_unavailable_rule_fallback')
        margin = scores[ranked[0]] - scores[ranked[1]]
        if not rule_matches and best != labels[0] and (confidence < MODEL_MIN_CONFIDENCE or margin < MODEL_MIN_MARGIN):
            best = labels[0]
            confidence = max(scores[best], 1.0 - scores[ranked[0]])
            scores[best] = confidence
            codes.append('uncertain_text_scenario')
            kind = 'abstention_evidence'
        codes = list(dict.fromkeys(codes)) or ['insufficient_scenario_evidence']
        ranked = sorted(scores, key=scores.get, reverse=True)
        return {'type': best, 'confidence': round(float(confidence), 6), 'confidence_kind': kind,
                'top_scenarios': [{'scenario': label, 'score': round(float(scores[label]), 6)} for label in ranked[:3]],
                'reason_codes': codes, 'evidence': {
                    'structured_scenario': rules['scenario'], 'structured_strength': rules['confidence'],
                    'text_scenario': text_result['scenario'] if text_result else None,
                    'text_support_terms': text_result['support_terms'] if text_result else [],
                    'message_available': bool(message), 'text_model_available': self.model is not None}}


def calculate_scenario_risk(predicted_scenario: str, confidence: float, context: PaymentContext,
                            new_recipient: bool = False) -> dict:
    """High narrative confidence needs matching structured evidence to raise risk.

    Normal/unknown always yields zero. Text alone classifies a story, but cannot
    establish structured circumstances. Weights are an illustrative evidence index.
    """
    validate_scenario_label(predicted_scenario)
    context_result = calculate_context_risk(context, new_recipient)
    rules = classify_scenario_rules(context)
    support = rules['scores'][predicted_scenario]
    evidence = {'matching_structured_strength': support, 'context_score': context_result['score']}
    if predicted_scenario == get_scenario_labels()[0]:
        return {'score': 0.0, 'reasons': ['normal_or_unknown_scenario'], 'evidence': evidence}
    if context_result['score'] < MIN_CONTEXT_FOR_SCENARIO_RISK or support < MIN_SCENARIO_EVIDENCE:
        return {'score': 0.0, 'reasons': ['scenario_lacks_supporting_context'], 'evidence': evidence}
    bounded_confidence = max(0.0, min(1.0, confidence))
    score = context_result['score'] * (SCENARIO_RISK_CONTEXT_FACTOR + SCENARIO_RISK_CONFIDENCE_FACTOR * bounded_confidence)
    return {'score': clamp_score(score), 'reasons': [f'{predicted_scenario}_context_supported'], 'evidence': evidence}

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## backend/app/schemas/risk.py

Preliminary risk API contracts reuse the Day 1 payment schema.

~~~python
"""Preliminary risk API contracts reuse the Day 1 payment schema."""
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from backend.app.schemas.transaction import Transaction, PaymentReason


class PreliminaryRiskRequest(Transaction):
    transaction_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    first_time_recipient: bool = False  # recalculated from server history
    payment_reason: PaymentReason = PaymentReason.other  # excluded from Day 2 predictors


class RiskComponent(BaseModel):
    score: float = Field(ge=0, le=100)
    ml_probability: float = Field(ge=0, le=1)
    rule_score: float = Field(ge=0, le=100)
    reasons: list[str] = Field(min_length=1)


class PreliminaryRiskResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    transaction_risk: float = Field(ge=0, le=100)
    recipient_risk: float = Field(ge=0, le=100)
    preliminary_risk: float = Field(ge=0, le=100)
    risk_level: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    reasons: list[str] = Field(min_length=1)
    transaction_details: RiskComponent
    recipient_details: RiskComponent


from typing import Any
from pydantic import model_validator, field_validator
from backend.app.schemas.context import PaymentContext
from backend.app.config.context_config import MAX_MESSAGE_LENGTH
from backend.app.utils.scenario_labels import validate_scenario_label


class ContextualRiskRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    transaction: PreliminaryRiskRequest
    context: PaymentContext
    message: str | None = Field(default=None, max_length=MAX_MESSAGE_LENGTH)

    @field_validator('message')
    @classmethod
    def trim_message(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode='after')
    def unambiguous_message(self) -> 'ContextualRiskRequest':
        if self.message and self.context.user_message and self.message != self.context.user_message:
            raise ValueError('Provide one message source, or identical message/context.user_message values')
        return self


class EvidenceRiskComponent(RiskComponent):
    evidence: dict[str, float] = Field(default_factory=dict)


class ExplainedScore(BaseModel):
    score: float = Field(ge=0, le=100)
    reasons: list[str] = Field(min_length=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    context_available: bool | None = None


class ScenarioCandidate(BaseModel):
    scenario: str
    score: float = Field(ge=0, le=1)
    _valid_label = field_validator('scenario')(validate_scenario_label)


class ScenarioResult(BaseModel):
    type: str
    confidence: float = Field(ge=0, le=1)
    confidence_kind: str
    top_scenarios: list[ScenarioCandidate] = Field(min_length=1, max_length=3)
    reason_codes: list[str] = Field(min_length=1)
    evidence: dict[str, Any]
    _valid_type = field_validator('type')(validate_scenario_label)


class ContextualRiskResponse(BaseModel):
    transaction_risk: EvidenceRiskComponent
    recipient_risk: EvidenceRiskComponent
    context_risk: ExplainedScore
    scenario: ScenarioResult
    scenario_risk: ExplainedScore
    extended_preliminary_risk: float = Field(ge=0, le=100)
    risk_level: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    reason_codes: list[str] = Field(min_length=1)

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## backend/app/services/transaction_service.py

Fuse behavioral rules with a loaded synthetic transaction baseline.

~~~python
"""Fuse behavioral rules with a loaded synthetic transaction baseline."""
import pandas as pd
from backend.app.config.risk_config import MODEL_REASON_THRESHOLD, component_score
from backend.app.features.transaction_features import extract_transaction_features
from backend.app.models.transaction_model import TransactionModel
from backend.app.rules.transaction_rules import score_transaction_rules


class TransactionService:
    def __init__(self, model: TransactionModel):
        self.model = model

    def score_transaction(self, transaction: dict, history: pd.DataFrame, profile: dict) -> dict:
        features = extract_transaction_features(transaction, history, profile)
        rules = score_transaction_rules(features)
        probability = self.model.probability(features)
        reasons = list(rules['reasons'])
        if probability >= MODEL_REASON_THRESHOLD:
            reasons = [code for code in reasons if code != 'within_expected_transaction_pattern']
            reasons.append('transaction_model_elevated_risk')
        if not features['baseline_available']:
            reasons.append('sender_baseline_unavailable')
        score, guarded = component_score(probability, rules['score'])
        if guarded:
            reasons.append('strong_rule_evidence_floor')
        return {'score': score,
                'ml_probability': round(probability, 6), 'rule_score': rules['score'], 'reasons': reasons, 'evidence': features}

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## backend/app/services/recipient_service.py

Recipient risk service using cached account and past payment history.

~~~python
"""Recipient risk service using cached account and past payment history."""
import pandas as pd
from backend.app.config.risk_config import MODEL_REASON_THRESHOLD, component_score
from backend.app.database.repository import DataRepository
from backend.app.features.recipient_features import calculate_recipient_features
from backend.app.models.recipient_model import RecipientModel
from backend.app.rules.recipient_rules import score_recipient_rules


class RecipientService:
    def __init__(self, model: RecipientModel, repository: DataRepository):
        self.model, self.repository = model, repository

    def score_recipient(self, receiver_id: str, timestamp: pd.Timestamp,
                        exclude_id: str | None = None) -> dict:
        account = self.repository.account(receiver_id, timestamp)
        history = self.repository.recipient_history(receiver_id, timestamp, exclude_id)
        features = calculate_recipient_features(account, history, timestamp)
        return self.score_features(features)

    def score_features(self, features: dict) -> dict:
        rules = score_recipient_rules(features)
        probability = self.model.probability(features)
        reasons = list(rules['reasons'])
        if probability >= MODEL_REASON_THRESHOLD:
            reasons = [code for code in reasons if code != 'no_recipient_rule_signals']
            reasons.append('recipient_model_elevated_risk')
        score, guarded = component_score(probability, rules['score'])
        if guarded:
            reasons.append('strong_rule_evidence_floor')
        return {'score': score,
                'ml_probability': round(probability, 6), 'rule_score': rules['score'], 'reasons': reasons, 'evidence': features}

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## backend/app/services/risk_service.py

Preliminary fusion of two modules, not a final APP fraud probability.

~~~python
"""Preliminary fusion of two modules, not a final APP fraud probability."""
import pandas as pd
from backend.app.config.risk_config import TRANSACTION_WEIGHT, RECIPIENT_WEIGHT, clamp_score, risk_level
from backend.app.database.repository import DataRepository
from backend.app.services.transaction_service import TransactionService
from backend.app.services.recipient_service import RecipientService
from backend.app.services.context_service import ContextService
from backend.app.services.scenario_service import ScenarioService, calculate_scenario_risk
from backend.app.schemas.context import PaymentContext
from backend.app.config.context_config import EXTENDED_WEIGHTS, PRESERVE_DAY2_WITHOUT_CONTEXT


def combine_risk(transaction: dict, recipient: dict) -> dict:
    score = clamp_score(TRANSACTION_WEIGHT * transaction['score'] + RECIPIENT_WEIGHT * recipient['score'])
    reasons = list(dict.fromkeys(transaction['reasons'] + recipient['reasons']))
    return {'transaction_risk': transaction['score'], 'recipient_risk': recipient['score'],
            'preliminary_risk': score, 'risk_level': risk_level(score), 'reasons': reasons,
            'transaction_details': transaction, 'recipient_details': recipient}


class RiskService:
    def __init__(self, repository: DataRepository, transaction: TransactionService,
                 recipient: RecipientService, scenario: ScenarioService | None = None):
        self.repository, self.transaction, self.recipient = repository, transaction, recipient
        self.context = ContextService()
        self.scenario = scenario or ScenarioService()

    def score(self, payment: dict) -> dict:
        stamp = pd.Timestamp(payment['timestamp']).tz_convert('UTC')
        if stamp < self.repository.start:
            raise ValueError('Scoring before the synthetic observation window is unsupported')
        profile = self.repository.account(payment['sender_id'], stamp)
        self.repository.account(payment['receiver_id'], stamp)
        history = self.repository.sender_history(payment['sender_id'], stamp, payment['transaction_id'])
        transaction = self.transaction.score_transaction(payment, history, profile)
        recipient = self.recipient.score_recipient(payment['receiver_id'], stamp, payment['transaction_id'])
        return combine_risk(transaction, recipient)


    def score_contextual(self, payment: dict, context: PaymentContext, message: str | None = None) -> dict:
        preliminary = self.score(payment)
        transaction, recipient = preliminary['transaction_details'], preliminary['recipient_details']
        new_recipient = bool(transaction['evidence']['first_time_recipient'])
        context_result = self.context.calculate_context_risk(context, new_recipient)
        scenario = self.scenario.predict_scenario(message, context)
        scenario_risk = calculate_scenario_risk(scenario['type'], scenario['confidence'], context, new_recipient)
        score = clamp_score(EXTENDED_WEIGHTS['transaction'] * transaction['score'] +
            EXTENDED_WEIGHTS['recipient'] * recipient['score'] +
            EXTENDED_WEIGHTS['context'] * context_result['score'] +
            EXTENDED_WEIGHTS['scenario'] * scenario_risk['score'])
        retained_without_context = PRESERVE_DAY2_WITHOUT_CONTEXT and not context_result['context_available']
        if retained_without_context:
            score = max(score, preliminary['preliminary_risk'])
        codes = list(dict.fromkeys(transaction['reasons'] + recipient['reasons'] +
                                  context_result['reasons'] + scenario['reason_codes'] + scenario_risk['reasons']))
        if retained_without_context:
            codes.append('day2_risk_retained_missing_context')
        return {'transaction_risk': transaction, 'recipient_risk': recipient, 'context_risk': context_result,
                'scenario': scenario, 'scenario_risk': scenario_risk, 'extended_preliminary_risk': score,
                'risk_level': risk_level(score), 'reason_codes': codes}

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## backend/app/api/risk_routes.py

Validated preliminary scoring endpoint; no training or disk reads per request.

~~~python
"""Validated preliminary scoring endpoint; no training or disk reads per request."""
from fastapi import APIRouter, HTTPException, Request
from backend.app.schemas.risk import PreliminaryRiskRequest, PreliminaryRiskResponse, ContextualRiskRequest, ContextualRiskResponse

router = APIRouter(prefix='/api/v1/risk', tags=['preliminary risk'])


@router.post('/preliminary', response_model=PreliminaryRiskResponse)
def preliminary_risk(payment: PreliminaryRiskRequest, request: Request) -> dict:
    service = getattr(request.app.state, 'risk_service', None)
    if service is None:
        raise HTTPException(status_code=503, detail=getattr(request.app.state, 'risk_error',
            'Risk models unavailable. Run both Day 2 training commands and restart the service.'))
    try:
        return service.score(payment.model_dump())
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post('/contextual', response_model=ContextualRiskResponse)
def contextual_risk(payment: ContextualRiskRequest, request: Request) -> dict:
    service = getattr(request.app.state, 'risk_service', None)
    if service is None:
        raise HTTPException(status_code=503, detail=getattr(request.app.state, 'risk_error', 'Risk engine unavailable'))
    try:
        return service.score_contextual(payment.transaction.model_dump(), payment.context, payment.message)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## backend/app/main.py

FastAPI service with startup-cached data and trained Day 2 baselines.

~~~python
"""FastAPI service with startup-cached data and trained Day 2 baselines."""
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from backend.app.api.risk_routes import router
from backend.app.database.repository import DataRepository
from backend.app.models.transaction_model import TransactionModel
from backend.app.models.recipient_model import RecipientModel
from backend.app.services.transaction_service import TransactionService
from backend.app.services.recipient_service import RecipientService
from backend.app.services.risk_service import RiskService
from backend.app.models.scenario_model import ScenarioModel
from backend.app.services.scenario_service import ScenarioService


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.risk_service = None
    try:
        repository = DataRepository.load()
        scenario = ScenarioService()
        try:
            scenario = ScenarioService(ScenarioModel())
        except (OSError, ValueError) as error:
            logging.getLogger(__name__).warning('Scenario text model unavailable; structured rules remain active: %s', error)
        application.state.scenario_text_available = scenario.model is not None
        application.state.risk_service = RiskService(repository,
            TransactionService(TransactionModel()), RecipientService(RecipientModel(), repository), scenario)
    except (OSError, ValueError) as error:
        application.state.risk_error = f'Risk engine unavailable: {error}. Run both training commands and restart.'
        logging.getLogger(__name__).warning(application.state.risk_error)
    yield


def create_app() -> FastAPI:
    application = FastAPI(title='APP Shield', version='0.3.0', lifespan=lifespan)
    application.include_router(router)
    application.add_api_route('/', root, methods=['GET'])
    application.add_api_route('/health', health, methods=['GET'])
    application.add_api_route('/ready', ready, methods=['GET'])
    return application


def root() -> dict[str, str]:
    return {'project': 'APP Shield', 'status': 'running'}


def health() -> dict[str, str]:
    """Liveness only; readiness is exposed separately."""
    return {'status': 'healthy'}


def ready(request: Request):
    from fastapi.responses import JSONResponse
    available = getattr(request.app.state, 'risk_service', None) is not None
    return JSONResponse({'status': 'ready' if available else 'unavailable'}, status_code=200 if available else 503)


app = create_app()

~~~

Run/check: `.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`.

## ml/scenario/hinglish_examples.py

Fifty-five manually authored holdout narratives, never used for training or selection.

~~~python
"""Fifty-five manually authored holdout narratives, never used for training or selection."""
HINGLISH_HOLDOUT = {
    'normal_or_unknown': [
        'Papa ke purane beneficiary ko electricity bill ke paise de raha hu, unse saamne baat ho chuki hai.',
        'SIP apne regulated broker par khud start ki thi; return fix nahi aur aaj pay karna zaroori nahi.',
        'Bank ne branch me KYC bola hai, kisi naye account me paisa bhejne ki baat nahi hui.',
        'Dukaan se saman le liya, ab invoice ke hisab se purane seller ko payment karunga.',
        'Behen ko birthday gift ke paise dene hain, number aur account dono pehle se jaanta hu.',
    ],
    'government_impersonation': [
        'CID wala bankar phone kiya, meri ID criminal case me hai bolta; paisa unke account me nahi bheja to jail.',
        'Aadhaar pe illegal kaam hua kehkar cyber cell ka aadmi legal action rokne ko transfer karwa raha.',
        'Police officer keh raha digital arrest lagega, funds verification wallet me rakho aur ghar pe mat batao.',
        'Sarkari investigator ne WhatsApp par warrant bheja, case close ke liye abhi payment maanga.',
        'Income tax ki inquiry bolkar unknown caller custodial action se bachne ko safe account deposit mangta.',
    ],
    'bank_impersonation': [
        'Main bank se bol raha hu, aapka account freeze hone wala hai, verification ke liye abhi payment karo.',
        'Bank manager bankar balance bachane ke liye dusre secure wallet me transfer mang raha hai.',
        'KYC pending bolke helpline wala temporary account me paise shift karne ko keh raha.',
        'Fraud department ka caller account block karega jab tak verification deposit nahi bhejta.',
        'Bank support se aadmi bola suspicious entry hai, funds safe account par move karo warna access band.',
    ],
    'investment_scam': [
        'Telegram advisor har mahine pakka bees percent return dega bolta, shuru ke paise personal UPI pe mangta.',
        'Online mentor zero risk double paisa ka promise karke deposit maang raha hai.',
        'Trading group fixed daily earning kehkar unknown coordinator ko pehle amount bhejne ko kehta.',
        'Social media wala guaranteed profit deta, registered broker ke bahar account me investment mangta.',
        'Naye contact ne loss impossible bola aur private plan join karne ko aaj hi money dalne ko kaha.',
    ],
    'fake_job_scam': [
        'HR ne job pakki boli par offer letter se pehle registration charges dene hain.',
        'Recruiter security deposit apne account me mangta, tabhi joining mail aayega bolta.',
        'Ghar se kaam milega lekin training fee pehle bhejo, company details baad me denge.',
        'Interview bina selection hua, documents verify karne ke liye paise maang rahe hain.',
        'Employment agent equipment booking ke naam par personal wallet payment ke baad appointment dega.',
    ],
    'tech_support_scam': [
        'Computer virus ka dar dikhake support caller screen control app install aur payment app kholo bolta.',
        'Remote desktop ka code maangkar technician repair fee transfer karne ko keh raha.',
        'Laptop popup se number mila, helpdesk wala screen share pe aakar bank app se paise bhejwa raha.',
        'Unknown software expert device control leke security fix ka charge personal wallet par mangta.',
        'Caller bolta remote session start karo phir protection renew karne ko transfer karwa dega.',
    ],
    'romance_scam': [
        'Dating website ka partner kabhi mila nahi, ab emergency hospital bill ke paise secret me mang raha.',
        'Online girlfriend airport pe phansi bolti, milne aane ke liye travel fee abhi chahiye.',
        'Romantic chat wale ne gift bheja bolkar customs charges bharne ko kaha, video call nahi karta.',
        'Messages me pyar ka wada hua, foreign partner medical loan chukane ke liye money maangta.',
        'Dating app wala relationship pakki bolta par visit se pehle luggage clearance ka transfer chahiye.',
    ],
    'family_emergency_scam': [
        'Naya number beta banke bola accident hua hai, mummy ko bina bataye paise bhejo.',
        'Cousin bankar unknown call me urgent bail ke liye transfer maanga, dusro ko phone mana hai.',
        'Bhai custody me hai bolke stranger release money mangta, bhai se baat nahi kara raha.',
        'Daughter ka mobile toot gaya bolkar alag beneficiary ko abhi money bhejne ka message hai.',
        'Papa ki surgery ka emergency message aaya, hospital confirm karne ka time nahi de rahe.',
    ],
    'marketplace_scam': [
        'OLX buyer bolta QR scan karke paise bhejo tab mere account me sale amount aayega.',
        'Secondhand seller listing app ke bahar courier insurance ka advance maang raha hai.',
        'Buyer merchant activation ka payment mujhse chahiye tab furniture ka price dega.',
        'Online seller extra delivery security personal UPI par mangta, invoice nahi deta.',
        'Resale customer collect request approve karke credit receive hoga bolkar rush karta.',
    ],
    'loan_scam': [
        'Instant loan approved bola lekin release se pehle processing charges bhejne hain.',
        'Finance agent refundable security dekar credit disbursement unlock karo keh raha.',
        'Lender bina documents loan dega par insurance advance apne wallet pe mangta.',
        'Borrowing account locked hai, clearance fee pay kiye bina funds nahi milenge bolte.',
        'Loan company ka unknown banda eligibility verify karne ke liye pehle personal transfer chahta.',
    ],
    'refund_scam': [
        'Refund dene se pehle verification debit approve karwa raha hai, bolta paisa wapas aa jayega.',
        'Cancelled order ke refund ka tax pehle bharna padega agent keh raha.',
        'Customer care QR scan aur payment karne ko bolta tab reimbursement credit hoga.',
        'Extra refund bheja hai bolkar account check bina personal wallet par paisa wapas mang raha.',
        'Pending reversal release charge advance me bhejne ka unknown support message mila.',
    ],
}

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## ml/scenario/evaluate.py

Saved-model test metrics, language slices and separate manually written Hinglish evaluation.

~~~python
"""Saved-model test metrics, language slices and separate manually written Hinglish evaluation."""
import json
import pandas as pd
from backend.app.models.scenario_model import ScenarioModel
from backend.app.config.context_config import SCENARIO_DATA_PATH, SCENARIO_REPORT_DIR
from ml.scenario.data_quality import validate_messages
from ml.scenario.metrics import evaluate_pipeline
from ml.scenario.hinglish_examples import HINGLISH_HOLDOUT


def evaluate() -> dict:
    model = ScenarioModel()
    data = pd.read_csv(SCENARIO_DATA_PATH)
    validate_messages(data)
    test = data[data.split == 'test']
    manual = pd.DataFrame([{'text': text, 'scenario_label': label, 'language': 'Hinglish'}
                           for label, messages in HINGLISH_HOLDOUT.items() for text in messages])
    generated_texts = set(data.text.str.casefold().str.strip())
    if any(text.casefold().strip() in generated_texts for text in manual.text):
        raise ValueError('Manual Hinglish holdout overlaps with generated corpus')
    report = {'selected_model': model.metadata['selected_model'],
              'test': evaluate_pipeline(model.pipeline, test),
              'manual_hinglish': evaluate_pipeline(model.pipeline, manual),
              'manual_holdout_used_for_training': False}
    predictions = model.pipeline.predict(manual.text)
    errors = [{'text': text, 'actual': actual, 'predicted': predicted}
              for text, actual, predicted in zip(manual.text, manual.scenario_label, predictions) if actual != predicted]
    report['manual_hinglish_errors'] = errors
    SCENARIO_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (SCENARIO_REPORT_DIR / 'saved_model_evaluation.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    manual.to_csv(SCENARIO_REPORT_DIR / 'manual_hinglish_holdout.csv', index=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


if __name__ == '__main__':
    evaluate()

~~~

Run/check: `.venv\Scripts\python -m ml.scenario.evaluate`.

## scripts/analyze_scam_messages.py

Print and save scenario corpus integrity, diversity and split-overlap checks.

~~~python
"""Print and save scenario corpus integrity, diversity and split-overlap checks."""
import json
import pandas as pd
from backend.app.config.context_config import SCENARIO_DATA_PATH, SCENARIO_REPORT_DIR
from ml.scenario.data_quality import validate_messages


def main() -> None:
    report = validate_messages(pd.read_csv(SCENARIO_DATA_PATH))
    SCENARIO_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (SCENARIO_REPORT_DIR / 'dataset_quality.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

~~~

Run/check: `.venv\Scripts\python -m scripts.analyze_scam_messages`.

## tests/test_context_risk.py

Context boundaries, stacked evidence and legitimate-like counterexamples.

~~~python
"""Context boundaries, stacked evidence and legitimate-like counterexamples."""
import pytest
from pydantic import ValidationError
from backend.app.schemas.context import PaymentContext, ContactChannel, AuthorityType
from backend.app.schemas.transaction import PaymentReason
from backend.app.rules.context_rules import calculate_context_risk
from backend.app.rules.scenario_rules import classify_scenario_rules


@pytest.mark.parametrize('reason', [item.value for item in PaymentReason] + ['romance', 'marketplace', 'tech_support', 'emergency'])
def test_supported_payment_reasons(reason):
    assert PaymentContext(payment_reason=reason).payment_reason == reason


@pytest.mark.parametrize('channel', list(ContactChannel))
def test_supported_channels(channel):
    assert PaymentContext(contact_channel=channel).contact_channel == channel


@pytest.mark.parametrize('authority', list(AuthorityType))
def test_supported_authorities(authority):
    assert PaymentContext(authority_type=authority).authority_type == authority


@pytest.mark.parametrize('invalid', [{'payment_reason': 'crypto_magic'}, {'contact_channel': 'fax'},
    {'authority_type': 'unknown_agency'}, {'relationship_duration_days': -1},
    {'otp': '123456'}, {'urgent_payment_requested': 'yes'}, {'user_message': 'x'*4001}])
def test_invalid_context_rejected(invalid):
    with pytest.raises(ValidationError):
        PaymentContext(**invalid)


def test_optional_fields_and_empty_message():
    assert PaymentContext().contacted_by_unknown_person is None
    assert PaymentContext(user_message='   ').user_message is None


def test_government_stacked_evidence():
    context = PaymentContext(payment_reason='government', contacted_by_unknown_person=True,
        claimed_authority=True, authority_type='police', urgent_payment_requested=True,
        threatened_consequences=True, requested_secrecy=True)
    result = calculate_context_risk(context)
    assert 80 <= result['score'] <= 100
    assert 'authority_claim' in result['reasons']
    assert result['evidence']['threatened_consequences']
    assert classify_scenario_rules(context)['scenario'] == 'government_impersonation'


@pytest.mark.parametrize('flag', ['contacted_by_unknown_person', 'claimed_authority', 'urgent_payment_requested',
                                 'threatened_consequences', 'promised_profit', 'requested_secrecy',
                                 'asked_to_install_remote_access', 'asked_to_pay_fee'])
def test_single_signal_not_maximum(flag):
    assert calculate_context_risk(PaymentContext(**{flag: True}))['score'] < 60


def test_investment_and_legitimate_counterexample():
    suspicious = PaymentContext(payment_reason='investment', promised_profit=True, contacted_by_unknown_person=True)
    assert calculate_context_risk(suspicious)['score'] >= 60
    assert classify_scenario_rules(suspicious)['scenario'] == 'investment_scam'
    legitimate = PaymentContext(payment_reason='investment', contacted_by_unknown_person=False,
        promised_profit=False, urgent_payment_requested=False, claimed_authority=False)
    assert calculate_context_risk(legitimate)['score'] == 0
    assert classify_scenario_rules(legitimate)['scenario'] == 'normal_or_unknown'


def test_no_guarantee_inferred_from_ordinary_profit_promise():
    context = PaymentContext(payment_reason='investment', promised_profit=True)
    assert 'promised_profit_claim' in calculate_context_risk(context)['reasons']
    assert 'guaranteed_profit_claim' not in calculate_context_risk(context)['reasons']


def test_job_without_message_and_remote_access():
    job = PaymentContext(payment_reason='job', contacted_by_unknown_person=True, asked_to_pay_fee=True)
    assert classify_scenario_rules(job)['scenario'] == 'fake_job_scam'
    tech = PaymentContext(payment_reason='tech_support', contacted_by_unknown_person=True,
        asked_to_install_remote_access=True, fund_transfer_requested=True)
    assert calculate_context_risk(tech)['score'] >= 60
    assert classify_scenario_rules(tech)['scenario'] == 'tech_support_scam'


def test_family_payment_and_score_bounds():
    family = PaymentContext(payment_reason='family', contacted_by_unknown_person=False,
        urgent_payment_requested=False, threatened_consequences=False)
    assert calculate_context_risk(family)['score'] == 0
    intense = PaymentContext(**(family.model_dump() | dict(payment_reason='investment', contacted_by_unknown_person=True,
        claimed_authority=True, urgent_payment_requested=True, threatened_consequences=True,
        promised_profit=True, guaranteed_returns_promised=True, requested_secrecy=True)))
    assert calculate_context_risk(intense, new_recipient=True)['score'] == 100

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## tests/test_scenario_classifier.py

Narrative rules, real NLP inference, template leakage and risk/confidence separation.

~~~python
"""Narrative rules, real NLP inference, template leakage and risk/confidence separation."""
import pandas as pd
import pytest
from backend.app.models.scenario_model import ScenarioModel
from backend.app.schemas.context import PaymentContext
from backend.app.services.scenario_service import ScenarioService, calculate_scenario_risk
from backend.app.utils.scenario_labels import get_scenario_labels
from backend.app.config.context_config import SCENARIO_DATA_PATH
from ml.scenario.data_quality import validate_messages
from scripts.generate_scam_messages import generate_messages


@pytest.fixture(scope='module')
def scenario_service():
    return ScenarioService(ScenarioModel())


@pytest.mark.parametrize('context,expected', [
    (dict(payment_reason='government', claimed_authority=True, authority_type='police', threatened_consequences=True), 'government_impersonation'),
    (dict(payment_reason='bank_support', claimed_authority=True, authority_type='bank', fund_transfer_requested=True), 'bank_impersonation'),
    (dict(payment_reason='investment', promised_profit=True, contacted_by_unknown_person=True), 'investment_scam'),
    (dict(payment_reason='job', asked_to_pay_fee=True), 'fake_job_scam'),
    (dict(payment_reason='tech_support', asked_to_install_remote_access=True, fund_transfer_requested=True), 'tech_support_scam'),
    (dict(payment_reason='romance', online_relationship=True, urgent_payment_requested=True), 'romance_scam'),
    (dict(payment_reason='family', urgent_payment_requested=True, contacted_by_unknown_person=True), 'family_emergency_scam'),
    (dict(payment_reason='marketplace', fund_transfer_requested=True, contacted_by_unknown_person=True), 'marketplace_scam'),
    (dict(payment_reason='loan', asked_to_pay_fee=True), 'loan_scam'),
    (dict(payment_reason='refund', fund_transfer_requested=True), 'refund_scam'),
    (dict(payment_reason='family'), 'normal_or_unknown'),
])
def test_rule_only_taxonomy(context, expected):
    result = ScenarioService().predict_scenario(None, PaymentContext(**context))
    assert result['type'] == expected
    assert len(result['top_scenarios']) == 3
    assert result['reason_codes']
    assert all(item['scenario'] in get_scenario_labels() for item in result['top_scenarios'])


def test_text_plus_authority_context(scenario_service):
    context = PaymentContext(payment_reason='government', contacted_by_unknown_person=True,
        claimed_authority=True, authority_type='police', urgent_payment_requested=True, threatened_consequences=True)
    result = scenario_service.predict_scenario('Police said my Aadhaar is linked to money laundering and demanded an immediate transfer.', context)
    assert result['type'] == 'government_impersonation'
    assert 0 <= result['confidence'] <= 1
    assert len(result['top_scenarios']) == 3
    assert result['evidence']['text_model_available']
    assert 'text_classifier_evidence' in result['reason_codes']


def test_text_normal_and_out_of_vocabulary(scenario_service):
    result = scenario_service.predict_scenario('I am sending money for family groceries to the account we always use. No stranger contacted me.', PaymentContext())
    assert result['type'] == 'normal_or_unknown'
    unknown = scenario_service.predict_scenario('zzqxxvv ppqqzzzx', PaymentContext())
    assert unknown['type'] == 'normal_or_unknown'


def test_context_only_with_model_available(scenario_service):
    result = scenario_service.predict_scenario(None, PaymentContext(payment_reason='job', asked_to_pay_fee=True,
                                                                   contacted_by_unknown_person=True))
    assert result['type'] == 'fake_job_scam'
    assert result['confidence_kind'] == 'structured_rule_evidence'


def test_confidence_is_not_fraud_risk():
    assert calculate_scenario_risk('normal_or_unknown', .99, PaymentContext())['score'] == 0
    assert calculate_scenario_risk('investment_scam', .99, PaymentContext(payment_reason='investment',
        contacted_by_unknown_person=False, promised_profit=False))['score'] == 0
    assert calculate_scenario_risk('government_impersonation', .99, PaymentContext())['score'] == 0
    context = PaymentContext(payment_reason='government', contacted_by_unknown_person=True,
        claimed_authority=True, threatened_consequences=True, urgent_payment_requested=True)
    assert calculate_scenario_risk('government_impersonation', .9, context)['score'] >= 60


def test_missing_model_uses_rules_and_discloses_fallback():
    result = ScenarioService().predict_scenario('My recruiter wants a registration fee',
        PaymentContext(payment_reason='job', asked_to_pay_fee=True))
    assert result['type'] == 'fake_job_scam'
    assert 'text_model_unavailable_rule_fallback' in result['reason_codes']


def test_disjoint_and_nontrivial_corpus():
    data = pd.read_csv(SCENARIO_DATA_PATH)
    report = validate_messages(data)
    assert report['rows'] >= 5000
    assert min(report['classes'].values()) >= 300
    assert report['train_test_message_overlap'] == 0
    assert report['train_test_template_overlap'] == 0
    assert set(data.language) == {'English', 'Hinglish'}
    assert report['average_text_length'] > 80
    bad = data.copy()
    family = bad.template_id.iloc[0]
    indices = bad.index[bad.template_id == family][:2]
    bad.loc[indices, 'split'] = ['train', 'test']
    with pytest.raises(ValueError, match='Template-family leakage'):
        validate_messages(bad)


def test_generator_is_reproducible():
    pd.testing.assert_frame_equal(generate_messages(samples_per_template=2), generate_messages(samples_per_template=2))


@pytest.mark.parametrize('context,text,expected', [
    (dict(payment_reason='investment', contacted_by_unknown_person=True, contact_channel='social_media', promised_profit=True),
     'This new advisor guarantees twenty percent every month if I transfer an initial investment.', 'investment_scam'),
    (dict(payment_reason='job', asked_to_pay_fee=True, contacted_by_unknown_person=True),
     'The recruiter offered work after I pay five thousand rupees for registration and security.', 'fake_job_scam'),
    (dict(payment_reason='tech_support', asked_to_install_remote_access=True, fund_transfer_requested=True, contacted_by_unknown_person=True),
     'An unknown support caller wants remote access to my screen and then a money transfer.', 'tech_support_scam'),
])
def test_required_structured_plus_text_examples(scenario_service, context, text, expected):
    result = scenario_service.predict_scenario(text, PaymentContext(**context))
    assert result['type'] == expected


def test_strong_structured_evidence_survives_conflicting_text():
    class ConflictingTextModel:
        def predict(self, text):
            labels = get_scenario_labels()
            return {'scores': {label: float(label == 'tech_support_scam') for label in labels},
                    'scenario': 'tech_support_scam', 'support_terms': ['remote access'], 'confidence_kind': 'test_evidence'}
    context = PaymentContext(payment_reason='investment', promised_profit=True, contacted_by_unknown_person=True)
    result = ScenarioService(ConflictingTextModel()).predict_scenario('remote repair message', context)
    assert result['type'] == 'investment_scam'
    assert 'text_context_disagreement' in result['reason_codes']

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## tests/test_contextual_api.py

Contextual API integration, missing-text handling and Day 2 compatibility.

~~~python
"""Contextual API integration, missing-text handling and Day 2 compatibility."""
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.schemas.risk import ContextualRiskResponse


@pytest.fixture(scope='module')
def client():
    with TestClient(create_app()) as instance:
        assert instance.get('/ready').status_code == 200
        yield instance


@pytest.fixture
def transaction():
    return dict(sender_id='A0001', receiver_id='A1006', amount=85000,
        timestamp='2026-01-30T23:31:50+00:00', device_id='D0001', payment_type='bank_transfer')


@pytest.fixture
def authority_context():
    return dict(payment_reason='government', contacted_by_unknown_person=True, contact_channel='phone',
        claimed_authority=True, authority_type='police', urgent_payment_requested=True,
        threatened_consequences=True, requested_secrecy=True, fund_transfer_requested=True)


def test_government_contextual_api(client, transaction, authority_context):
    with patch('pandas.read_csv', side_effect=AssertionError('Unexpected CSV read during inference')):
        response = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction,
            context=authority_context, message='Cyber Crime Department says my Aadhaar is involved in illegal transfers. Pay immediately to avoid arrest.'))
    assert response.status_code == 200, response.text
    result = ContextualRiskResponse.model_validate(response.json())
    assert result.scenario.type == 'government_impersonation'
    assert result.context_risk.score >= 80
    assert result.risk_level == 'CRITICAL'
    assert result.extended_preliminary_risk >= 80
    assert result.reason_codes
    assert result.transaction_risk.evidence
    assert result.recipient_risk.evidence
    assert result.context_risk.evidence


def test_message_optional_and_day2_still_works(client, transaction):
    response = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction,
        context=dict(payment_reason='job', asked_to_pay_fee=True, contacted_by_unknown_person=True)))
    assert response.status_code == 200
    assert response.json()['scenario']['type'] == 'fake_job_scam'
    preliminary = client.post('/api/v1/risk/preliminary', json=transaction)
    assert preliminary.status_code == 200
    assert isinstance(preliminary.json()['transaction_risk'], (int, float))
    assert 'extended_preliminary_risk' not in preliminary.json()


def test_known_family_and_legitimate_investment(client):
    transaction = dict(sender_id='A0242', receiver_id='A0928', amount=2381.48,
        timestamp='2026-01-30T23:31:49+00:00', device_id='D0242', payment_type='bank_transfer')
    for reason in ('family', 'investment'):
        context = dict(payment_reason=reason, contacted_by_unknown_person=False, promised_profit=False,
                       urgent_payment_requested=False, threatened_consequences=False)
        response = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction, context=context))
        assert response.status_code == 200
        assert response.json()['context_risk']['score'] == 0
        assert response.json()['risk_level'] == 'LOW'


def test_message_source_validation(client, transaction):
    context = dict(payment_reason='job', asked_to_pay_fee=True, user_message='registration fee request')
    alias = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction, context=context))
    assert alias.status_code == 200
    conflict = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction, context=context, message='different story'))
    assert conflict.status_code == 422


@pytest.mark.parametrize('change', [{'message': 'x'*4001}, {'context': {'payment_reason': 'invalid'}},
                                   {'context': {'otp': '123456'}}])
def test_invalid_contextual_request(client, transaction, change):
    request = dict(transaction=transaction, context={}) | change
    assert client.post('/api/v1/risk/contextual', json=request).status_code == 422


def test_rule_fallback_preserves_day2_availability(transaction, authority_context):
    with patch('backend.app.main.ScenarioModel', side_effect=FileNotFoundError('missing text artifact')):
        with TestClient(create_app()) as fallback:
            assert fallback.get('/ready').status_code == 200
            result = fallback.post('/api/v1/risk/contextual', json=dict(transaction=transaction,
                context=authority_context, message='Police requested an urgent transfer'))
            assert result.status_code == 200
            assert result.json()['scenario']['type'] == 'government_impersonation'
            assert 'text_model_unavailable_rule_fallback' in result.json()['scenario']['reason_codes']
            assert fallback.post('/api/v1/risk/preliminary', json=transaction).status_code == 200


def test_missing_context_does_not_erase_existing_risk(client, transaction):
    baseline = client.post('/api/v1/risk/preliminary', json=transaction).json()
    response = client.post('/api/v1/risk/contextual', json=dict(transaction=transaction, context={}))
    assert response.status_code == 200
    result = response.json()
    assert result['extended_preliminary_risk'] >= baseline['preliminary_risk']
    assert result['context_risk']['context_available'] is False
    assert 'day2_risk_retained_missing_context' in result['reason_codes']

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## scripts/smoke_contextual_api.py

Exercise the running contextual endpoint with optional text and legitimate counterexamples.

~~~python
"""Exercise the running contextual endpoint with optional text and legitimate counterexamples."""
import json
from time import perf_counter
from urllib.request import Request, urlopen
from backend.app.config.context_config import SCENARIO_REPORT_DIR

SUSPICIOUS_PAYMENT = dict(sender_id='A0001', receiver_id='A1006', amount=85000,
    timestamp='2026-01-30T23:31:50+00:00', device_id='D0001', payment_type='bank_transfer')
NORMAL_PAYMENT = dict(sender_id='A0242', receiver_id='A0928', amount=2381.48,
    timestamp='2026-01-30T23:31:49+00:00', device_id='D0242', payment_type='bank_transfer')


def post(path: str, payload: dict) -> tuple[dict, float]:
    body = json.dumps(payload).encode('utf-8')
    start = perf_counter()
    with urlopen(Request('http://127.0.0.1:8000' + path, data=body,
                         headers={'Content-Type': 'application/json'}), timeout=20) as response:
        result = json.load(response)
    return result, (perf_counter() - start) * 1000


def main() -> None:
    government = dict(transaction=SUSPICIOUS_PAYMENT, context=dict(payment_reason='government',
        contacted_by_unknown_person=True, contact_channel='phone', claimed_authority=True,
        authority_type='police', urgent_payment_requested=True, threatened_consequences=True,
        requested_secrecy=True, fund_transfer_requested=True),
        message='Cyber Crime Department said my Aadhaar was involved in money laundering. Transfer the funds immediately to avoid legal action.')
    investment = dict(transaction=NORMAL_PAYMENT, context=dict(payment_reason='investment',
        contacted_by_unknown_person=False, promised_profit=False, guaranteed_returns_promised=False,
        urgent_payment_requested=False, threatened_consequences=False),
        message='I voluntarily pay my registered investment fund. There are no guaranteed returns or urgent instructions.')
    job_without_text = dict(transaction=SUSPICIOUS_PAYMENT, context=dict(payment_reason='job',
        contacted_by_unknown_person=True, asked_to_pay_fee=True))
    examples = {}
    for name, request in (('government', government), ('legitimate_investment', investment), ('job_without_text', job_without_text)):
        result, latency = post('/api/v1/risk/contextual', request)
        examples[name] = {'request': request, 'response': result, 'latency_ms': latency}
    assert examples['government']['response']['scenario']['type'] == 'government_impersonation'
    assert examples['government']['response']['risk_level'] == 'CRITICAL'
    assert examples['government']['response']['context_risk']['score'] >= 80
    assert examples['legitimate_investment']['response']['context_risk']['score'] == 0
    assert examples['legitimate_investment']['response']['risk_level'] != 'CRITICAL'
    assert examples['job_without_text']['response']['scenario']['type'] == 'fake_job_scam'
    day2, _ = post('/api/v1/risk/preliminary', SUSPICIOUS_PAYMENT)
    assert 'preliminary_risk' in day2 and 'extended_preliminary_risk' not in day2
    report = {'examples': examples, 'day2_endpoint_compatible': True,
              'latency_note': 'Single localhost HTTP measurements include transport and are not a production benchmark'}
    SCENARIO_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (SCENARIO_REPORT_DIR / 'contextual_api_examples.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    for name, example in examples.items():
        response = example['response']
        print(f"{name}: scenario={response['scenario']['type']}, context={response['context_risk']['score']}, "
              f"extended={response['extended_preliminary_risk']}, level={response['risk_level']}, "
              f"latency={example['latency_ms']:.1f} ms")
    print('Day 2 preliminary endpoint remains compatible')


if __name__ == '__main__':
    main()

~~~

Run/check: `.venv\Scripts\python -m scripts.smoke_contextual_api`.

## README.md

Full setup, assumptions, evaluation results and examples.

~~~markdown
# APP Shield — Context-Aware Authorized Payment Scam Detection Engine

Traditional fraud detection asks: **Is the person making the transaction really the authorized user?**
APP Shield additionally asks: **Is the genuine authorized user being manipulated by a scammer?**

Day 1 provides the data and backend foundation. Day 2 adds transaction abnormality and recipient suspiciousness baselines. Day 3 adds payment context and scenario intelligence. Psychology, graph and deployment modules remain reserved placeholders.

## Run locally (Python 3.11+)

Run these commands from the app-shield directory:

~~~powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements.txt
.venv\Scripts\python -m scripts.generate_transactions
.venv\Scripts\python -m scripts.analyze_transactions --output data/processed/analysis.txt
.venv\Scripts\python -m ml.transaction.train
.venv\Scripts\python -m ml.recipient.train
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
~~~

GET / returns project=APP Shield and status=running. GET /health returns status=healthy.
Open http://127.0.0.1:8000/docs for endpoint documentation.

## Data

The default seed 42 creates 1,000 normal users, 40 suspicious accounts and 10,000 payments (7.5% fraud), covering seven APP scenarios. Regenerate with --seed or --transactions. Files are saved in data/synthetic/transactions.csv and accounts.csv. Amounts are synthetic INR values.

Users have distinct spending averages, active hours, devices, recipient sets and frequencies. Both classes contain small and large payments. Investment scenarios reuse recipients and often increase payments. Suspicious account behavior overlaps with ordinary accounts. Account report counts and outgoing ratios are simulated pre-observation historical snapshots; they are not measured from the generated stream. Incoming velocity and distinct senders use the preceding 24 hours, excluding the current payment. First-time status includes a simulated pre-observation recipient history. Timestamps use a fixed January 2026 UTC observation window.

Derived features: amount_ratio, is_large_deviation (ratio > 3), is_new_recipient, recipient_age_bucket, recipient_activity_level, recipient_reported. Thresholds are illustrative rather than validated risk rules.

Exclude is_fraud, fraud_type, is_suspicious, is_known_mule, transaction/account identifiers and profile-only metadata from future model predictors. Keep labels for evaluation only. Split future experiments by time/user as appropriate; do not evaluate on duplicated profiles across random splits without checking leakage. Synthetic results cannot establish real-world fraud-detection accuracy. No PIN, OTP, CVV, passwords or banking secrets are stored; schemas reject extra fields.

## Database

SQLAlchemy account/payment tables and an engine factory support SQLite locally and PostgreSQL via DATABASE_URL. No database is initialized on service startup. Export DATABASE_URL explicitly; .env.example is documentation and is not automatically loaded.

## Future architecture

~~~text
Transaction Risk + Recipient Risk + Graph/Mule Risk + Payment Context
+ Scam Scenario Detection + Psychological Manipulation Detection
                         ↓
                    APP Scam Risk
~~~

See DAY1_IMPLEMENTATION.md for every implemented file's complete code, purpose and run/test commands. Empty package initializers enable imports. Existing notebooks and model placeholders are unused in Day 1.


## Day 2

Implemented: transaction feature engineering, transaction rules and two ML baselines; recipient feature engineering, recipient rules and two ML baselines; preliminary risk fusion; explainable reason codes; POST /api/v1/risk/preliminary.

**This is not yet the final APP scam detector.** Day 3 now supplies scam context and narrative classification. Psychological manipulation and transaction-network intelligence will be added later. Transaction training uses synthetic is_fraud labels to compare baseline fraud-propensity signals, not validated abnormality labels. Recipient training uses is_suspicious (40 synthetic positives); is_known_mule marks only a random subset and is not a complete negative label.

Run training, evaluation and benchmarking from this directory:

~~~powershell
.venv\Scripts\python -m ml.transaction.train
.venv\Scripts\python -m ml.recipient.train
.venv\Scripts\python -m ml.transaction.evaluate
.venv\Scripts\python -m ml.recipient.evaluate
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m scripts.benchmark_risk
.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
~~~

Restart FastAPI after training. Data and model artifacts are loaded once during lifespan startup. Missing models produce a clear 503 on scoring and /ready; /health remains a liveness check. Requests are read-only previews and do not append payments to history. Unknown accounts return 404. Invalid input, naive timestamps and dates before the observation window return 422. Use account IDs from accounts.csv (A0000–A1039), rather than the illustrative U101/M012 identifiers.

### Features and leakage boundaries

Both training and inference call identical extractors. Sender counts/averages and recipient inflows/outflows use timestamps strictly before the payment; same-timestamp transactions and the current transaction ID are excluded. Sender average falls back to the pre-observation profile for a cold start. Zero baseline yields a neutral amount ratio of 1 plus a baseline-unavailable reason. First-time recipients are derived server-side, including pre-observation usual recipients; a client's first_time_recipient value is ignored. Transaction models exclude absolute amount, labels, payment reasons, identifiers and mule flags. Clock hour alone never adds a rule penalty; outside-usual-hours is only one learned behavioral feature. All timestamps/hours are UTC, matching the synthetic profiles.

Fraud reports, holding times and historical outgoing ratios are **simulated pre-observation snapshots**, not timestamped production observations. The recipient outgoing_ratio is the maximum of bounded observed 24h outflow/inflow and the historical profile ratio; observed_outgoing_ratio and both measured amounts are exposed separately. The synthetic accounts lack realistic onward transfers, so this approximation must be replaced with ledger and report-event data before production use. Short historical holding time plus high observed outflow is supporting evidence, not a causal rapid-transfer reconstruction.

Transaction evaluation uses chronological 60/20/20 train/validation/test partitions. Prior test-period payments may be used as history for later test payments, but their labels never enter features. Recipient evaluation uses one snapshot per account at the end of the observation window and stratified account-disjoint 60/20/20 partitions. Test accounts' earlier activity is available as unlabeled feature history, as it would be when scoring them. This is not a future temporal recipient benchmark. Only training uses balanced class weights. Neither validation nor test data is oversampled.

Logistic regression and random forest are compared. Selection uses validation average precision; threshold selection maximizes validation recall subject to a 10% FPR cap. Test metrics include precision, recall, F1, ROC-AUC, PR-AUC (average precision), confusion matrix and false-positive rate. Accuracy alone is misleading: predicting every payment as legitimate yields 92.5% overall accuracy and zero fraud recall. Recipient metrics have only eight positive test accounts, so estimates are especially uncertain. Feature importances/standardized coefficients describe model associations, not causal explanations.

### MVP scores

Each component score = 60% × ML output × 100 + 40% × rule score. Preliminary score = 45% × transaction score + 55% × recipient score. When stacked rule evidence reaches 80 or above, the component score is floored at its rule score, with reason strong_rule_evidence_floor. This prevents an uncalibrated model trained on sparse synthetic activity from erasing extreme recipient evidence outside its training range. These configurable weights and this safeguard are illustrative, not optimized or calibrated. ML outputs are uncalibrated probabilities from synthetic supervised baselines. The fused score is an evidence index, not an APP fraud probability. Levels: LOW 0–29, MEDIUM 30–59, HIGH 60–79, CRITICAL 80–100 (floating scores use cutoffs 30, 60, 80). See backend/app/config/risk_config.py.

Saved artifacts: saved_models/transaction_model.pkl and recipient_model.pkl, with adjacent feature/config metadata. Only load locally trained, trusted pickle artifacts. Reports and held-out feature tables are saved under data/processed/day2/. Retrain after changing features or regenerating the dataset.

The numeric top-level transaction_risk and recipient_risk fields support concise clients. transaction_details and recipient_details include score, rule_score, ml_probability and reason codes. Combined reasons preserve both sets.

See DAY2_IMPLEMENTATION.md for complete code for every changed/new file, run instructions, and an actual example response. requirements.txt pins the ML dependency versions used locally; the official scikit-learn 1.5 documentation lists support through Python 3.12: [installation documentation](https://scikit-learn.org/1.5/install.html). This setup was tested with Python 3.12.10.


### Verified local results

53 automated tests pass. A live HTTP payment returned transaction risk 91.24, recipient risk 77.97 and preliminary risk 83.94 (CRITICAL); the normal example returned 0.10 (LOW). The latest measurement on this machine was median 122.0 ms / p95 170.9 ms across 20 warmed localhost HTTP requests. TestClient measurements ranged from roughly 15 to 96 ms across runs; these are environment-sensitive smoke measurements, not a production latency guarantee. Run scripts.smoke_risk_api after starting the server for the HTTP check.

| Selected baseline | Precision | Recall | F1 | ROC-AUC | PR-AUC | FPR |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Transaction: random forest | 0.309 | 0.538 | 0.393 | 0.887 | 0.424 | 0.093 |
| Recipient: logistic regression | 0.556 | 0.625 | 0.588 | 0.979 | 0.788 | 0.020 |

The recipient random forest scored better on the test partition but was not selected, because selection was locked to validation average precision. Do not switch models based on the held-out test results without introducing a fresh evaluation set. These baselines miss substantial positives; synthetic results do not demonstrate production readiness.

For the exact tested environment, install backend/requirements.lock.txt. One upstream Starlette TestClient deprecation warning remains; all tests pass.

Example request (use an explicit timezone):

~~~powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/risk/preliminary' -Method Post -ContentType 'application/json' -Body '{"sender_id":"A0001","receiver_id":"A1006","amount":66994.74,"timestamp":"2026-01-30T23:31:50+00:00","device_id":"D0001","payment_type":"bank_transfer"}'
~~~

Expected numeric scores with the seeded artifacts: transaction_risk=91.24, recipient_risk=77.97, preliminary_risk=83.94, risk_level=CRITICAL. The complete response and both normal/suspicious examples are in data/processed/day2/latency_and_example.json and DAY2_IMPLEMENTATION.md.


## Day 3 — payment context and scam scenarios

Implemented: payment-context schema, explainable context rules, centralized scenario taxonomy, diverse synthetic English/Hinglish narratives, TF-IDF logistic regression and linear SVM comparison, structured-plus-text inference, top-three scenario candidates, contextual risk API, and Day 2/Day 3 integration. Psychological manipulation classification and graph-network intelligence are not implemented yet. All outputs remain preliminary evidence scores, not a final APP fraud probability.

### Generate, train, evaluate and run

Run these commands from app-shield with the existing environment and Day 2 models:

~~~powershell
.venv\Scripts\python -m scripts.generate_scam_messages
.venv\Scripts\python -m scripts.analyze_scam_messages
.venv\Scripts\python -m ml.scenario.train
.venv\Scripts\python -m ml.scenario.evaluate
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
# In another terminal while the API is running:
.venv\Scripts\python -m scripts.smoke_contextual_api
~~~

Restart the API after training. The TF-IDF vectorizer and classifier are saved together in saved_models/scenario_pipeline.pkl; taxonomy/version metadata is adjacent. Model, vocabulary and taxonomy are cached at startup. No per-request training, CSV reads, or LLM calls occur. If only the text artifact is missing, structured scenario rules and both Day 2 risk engines continue working; the response reports text_model_unavailable_rule_fallback when a message was supplied.

### Context and input semantics

POST /api/v1/risk/contextual accepts transaction, context, and optional message. The transaction block reuses the Day 2 request/schema. Put the expanded Day 3 payment_reason in context (romance, marketplace, tech_support, emergency and existing Day 1 reasons, including legacy relationship). Use actual synthetic account IDs and an explicit timezone, as in the example below. Unknown accounts return 404; invalid fields, naive timestamps, unsupported reasons and conflicting message sources return 422.

All circumstance booleans are optional and strict: missing/null means unknown, not false. user_message inside context is an alternative to the top-level message; if both are supplied they must match. Empty/whitespace text is treated as missing. Text is capped at 4,000 characters. Additional explicit fields fund_transfer_requested, guaranteed_returns_promised and online_relationship allow evidence to be reported without guessing it from a vague payment reason. promised_profit alone does not imply a guaranteed return. Context scoring treats new-recipient status as server-derived Day 2 evidence, never as a client assertion.

Context rules stack signals and combinations. Unknown contact, authority, urgency and threats together produce high scores; single signals do not yield maximum risk. Ordinary family payments and voluntary registered investment-like payments with no reported pressure stay low. Remote access plus a transfer instruction, job fees and unsolicited profit promises add interpretable reason codes. Missing circumstances yield insufficient_context_information and context_available=false; a zero context score in that case is not proof of safety.

### Scenario evidence and fusion

The only taxonomy list is ml/scenario/labels.json. Rule mappings, templates, model artifacts and response validators check that taxonomy. The text pipeline consumes text only; labels, message IDs, template IDs, language and split fields never enter predictors.

Without a message, structured rules infer scenarios such as fake_job_scam. With both text and a matching structured pattern, evidence scores use 65% structured rules and 35% text. Explicit structured patterns take priority because the text baseline generalizes imperfectly; disagreements are reported as text_context_disagreement. Without a structured match, the text model supplies the narrative evidence; low-confidence/low-margin text can abstain to normal_or_unknown. Top-three scores and confidence are MVP evidence strengths and need not sum to one. They are not calibrated probabilities. Text-support terms are linear model associations, not independent factual verification.

calculate_scenario_risk requires a non-normal scenario, matching structured evidence strength >=0.55 and context score >=20. Its provisional score is context_score × (0.65 + 0.35 × scenario_confidence). Normal/unknown or unsupported text-only predictions get scenario risk zero; high narrative confidence alone cannot produce high fraud risk.

extended_preliminary_risk = 0.25×transaction + 0.30×recipient + 0.25×context + 0.20×scenario_risk. These temporary hand-tuned weights are not production-calibrated. When structured circumstances are missing, existing Day 2 preliminary risk is retained as a minimum, with day2_risk_retained_missing_context; absent answers cannot erase known evidence. All thresholds/weights are in backend/app/config/context_config.py and the existing risk_config.py.

The original /api/v1/risk/preliminary contract remains unchanged. The new endpoint returns nested transaction/recipient/context scores, a scenario object, separate scenario_risk, extended_preliminary_risk, risk_level and merged reason_codes. Each layer includes reasons and relevant evidence.

### Synthetic corpus and evaluation limits

The corpus contains **5499 unique messages** across 11 classes (499–500 per class), from **110 narrative families**. One normalized exact duplicate was removed. Amount, caller name, channel, deadlines, style and message framing vary. English and Hinglish base narratives are balanced; framing phrases may mix languages. Legitimate-like examples include bank, investment, job and marketplace wording, rather than a keyword-only normal class.

Families stay together in class/language-balanced 60/20/20 train/validation/test splits. Each language/class contributes three families to training, one to validation and one to test. This is stricter than random row stratification and prevents variants of a template leaking into the test set. Training vocabulary is fit only on training messages; model selection uses validation macro F1. No test data or the separate 55-message manual Hinglish holdout is used for model selection or training.

| Model | Validation macro F1 | Test macro F1 |
| --- | ---: | ---: |
| tfidf_logistic_regression | 0.567 | 0.630 |
| tfidf_linear_svm | 0.558 | 0.649 |

Selected **tfidf_logistic_regression** by validation macro F1, even though the SVM scores higher on this particular test partition. Selected-model test accuracy is 0.661, macro precision 0.648, macro recall 0.661, macro F1 0.630.

| Selected model language slice | Accuracy | Macro F1 |
| --- | ---: | ---: |
| English generated holdout | 0.642 | 0.608 |
| Hinglish generated holdout | 0.680 | 0.621 |
| Independently authored Hinglish, 55 messages | 0.764 | 0.761 |

| Scenario | Test precision | Test recall | Test F1 |
| --- | ---: | ---: | ---: |
| normal_or_unknown | 0.505 | 0.500 | 0.503 |
| government_impersonation | 0.660 | 0.990 | 0.792 |
| bank_impersonation | 0.375 | 0.270 | 0.314 |
| investment_scam | 0.000 | 0.000 | 0.000 |
| fake_job_scam | 1.000 | 1.000 | 1.000 |
| tech_support_scam | 0.405 | 1.000 | 0.576 |
| romance_scam | 0.962 | 0.500 | 0.658 |
| family_emergency_scam | 0.574 | 0.700 | 0.631 |
| marketplace_scam | 0.667 | 0.500 | 0.571 |
| loan_scam | 0.980 | 1.000 | 0.990 |
| refund_scam | 1.000 | 0.810 | 0.895 |

The text-only baseline has substantial weaknesses. Held-out investment narratives are often confused with tech support or family emergencies; marketplace and romance narratives can also be confused with tech support. Bank/government impersonation and refund/marketplace distinctions remain difficult. Legitimate bank and shop messages can be misclassified because vocabulary alone does not reliably capture negation or intent. Failure counts often cluster by held-out template family, which is why thousands of generated variants do not equal thousands of independent real-world examples.

Reports preserve every class's precision/recall/F1, the complete labeled confusion matrix, most common confusions, English/Hinglish slices, top model terms, and manual-Hinglish errors. Dataset analysis includes class balance, text lengths, duplicates, exact overlap, template overlap and frequent words. Files are under data/processed/day3/. Review these failures before expanding data or retraining; no blind retraining was performed using the manual holdout.

Synthetic results and the small manual holdout do not establish real-world accuracy. Context is user-reported, text may be inaccurate or unrelated, and confidence is uncalibrated. The scoring pipeline does not authenticate authority claims or verify a recipient's registration status. The existing Day 2 data approximations remain applicable.

### Verified live examples

- government: scenario=government_impersonation; context=100.00; extended=90.32; level=CRITICAL.
- legitimate_investment: scenario=normal_or_unknown; context=0.00; extended=0.06; level=LOW.
- job_without_text: scenario=fake_job_scam; context=60.00; extended=72.78; level=HIGH.

All **138 tests pass** across Days 1–3. One upstream Starlette TestClient deprecation warning remains. The live HTTP smoke check confirms Day 2 compatibility and saves full request/response examples in data/processed/day3/contextual_api_examples.json.

Example request:

~~~json
{
  "transaction": {
    "sender_id": "A0001",
    "receiver_id": "A1006",
    "amount": 85000,
    "timestamp": "2026-01-30T23:31:50+00:00",
    "device_id": "D0001",
    "payment_type": "bank_transfer"
  },
  "context": {
    "payment_reason": "government",
    "contacted_by_unknown_person": true,
    "contact_channel": "phone",
    "claimed_authority": true,
    "authority_type": "police",
    "urgent_payment_requested": true,
    "threatened_consequences": true,
    "requested_secrecy": true,
    "fund_transfer_requested": true
  },
  "message": "Cyber Crime Department said my Aadhaar was involved in money laundering. Transfer the funds immediately to avoid legal action."
}
~~~

Send it to POST http://127.0.0.1:8000/api/v1/risk/contextual, or run scripts.smoke_contextual_api. Expected scenario: government_impersonation; context score: 100; extended score: 90.32; level: CRITICAL with the seeded artifacts. The complete response is in DAY3_IMPLEMENTATION.md and the example JSON report.

~~~

Run/check: `.venv\Scripts\python -m pytest -q`.

## Complete live government example response

~~~json
{
  "transaction_risk": {
    "score": 91.24,
    "ml_probability": 0.954067,
    "rule_score": 85,
    "reasons": [
      "amount_much_higher_than_normal",
      "first_time_recipient",
      "amount_above_recent_average",
      "transaction_model_elevated_risk"
    ],
    "evidence": {
      "amount": 85000,
      "sender_average_amount": 2233.158,
      "amount_ratio": 38.06268969772851,
      "first_time_recipient": 1,
      "transaction_hour": 23,
      "device_changed": 0,
      "transactions_last_1h": 0,
      "transactions_last_24h": 0,
      "amount_vs_recent_average": 38.06268969772851,
      "amount_deviation": 37.06268969772851,
      "recipient_seen_before": 0,
      "outside_usual_hours": 1,
      "history_count": 5,
      "baseline_available": 1
    }
  },
  "recipient_risk": {
    "score": 77.97,
    "ml_probability": 0.999536,
    "rule_score": 45,
    "reasons": [
      "high_outgoing_ratio",
      "multiple_prior_fraud_reports",
      "recipient_model_elevated_risk"
    ],
    "evidence": {
      "account_age_days": 33,
      "incoming_transactions_1h": 0,
      "incoming_transactions_24h": 0,
      "unique_senders_1h": 0,
      "unique_senders_24h": 0,
      "incoming_amount_24h": 0,
      "outgoing_amount_24h": 0,
      "outgoing_ratio": 0.9060308797089864,
      "observed_outgoing_ratio": 0,
      "fraud_report_count": 2,
      "transaction_velocity": 0,
      "sender_diversity": 0,
      "average_incoming_amount": 0,
      "median_incoming_amount": 0,
      "inflow_outflow_imbalance": 0,
      "average_holding_minutes": 316.00930004987663
    }
  },
  "context_risk": {
    "score": 100,
    "reasons": [
      "unknown_contact",
      "authority_claim",
      "urgent_payment_request",
      "threatened_consequences",
      "secrecy_request",
      "fund_transfer_request",
      "authority_threat_urgency_combination"
    ],
    "evidence": {
      "unknown_contact": true,
      "authority_claim": true,
      "urgent_payment_request": true,
      "threatened_consequences": true,
      "secrecy_request": true,
      "fund_transfer_request": true,
      "authority_threat_urgency_combination": true
    },
    "context_available": true
  },
  "scenario": {
    "type": "government_impersonation",
    "confidence": 0.873773,
    "confidence_kind": "structured_and_text_evidence",
    "top_scenarios": [
      {
        "scenario": "government_impersonation",
        "score": 0.873773
      },
      {
        "scenario": "loan_scam",
        "score": 0.008621
      },
      {
        "scenario": "normal_or_unknown",
        "score": 0.007434
      }
    ],
    "reason_codes": [
      "authority_claim",
      "government_impersonation_pattern",
      "crime_or_legal_threat",
      "text_classifier_evidence"
    ],
    "evidence": {
      "structured_scenario": "government_impersonation",
      "structured_strength": 0.9,
      "text_scenario": "government_impersonation",
      "text_support_terms": [
        "laundering",
        "money",
        "legal",
        "money laundering",
        "aadhaar"
      ],
      "message_available": true,
      "text_model_available": true
    }
  },
  "scenario_risk": {
    "score": 95.58,
    "reasons": [
      "government_impersonation_context_supported"
    ],
    "evidence": {
      "matching_structured_strength": 0.9,
      "context_score": 100
    },
    "context_available": null
  },
  "extended_preliminary_risk": 90.32,
  "risk_level": "CRITICAL",
  "reason_codes": [
    "amount_much_higher_than_normal",
    "first_time_recipient",
    "amount_above_recent_average",
    "transaction_model_elevated_risk",
    "high_outgoing_ratio",
    "multiple_prior_fraud_reports",
    "recipient_model_elevated_risk",
    "unknown_contact",
    "authority_claim",
    "urgent_payment_request",
    "threatened_consequences",
    "secrecy_request",
    "fund_transfer_request",
    "authority_threat_urgency_combination",
    "government_impersonation_pattern",
    "crime_or_legal_threat",
    "text_classifier_evidence",
    "government_impersonation_context_supported"
  ]
}
~~~

## Generated artifacts

data/synthetic/scam_messages.csv — generated narrative corpus with template/language/split provenance.

saved_models/scenario_pipeline.pkl — vectorizer and selected classifier in one trusted local artifact.

saved_models/scenario_pipeline.metadata.json — taxonomy, seed, input allowlist, version and data hash.

data/processed/day3/scenario_evaluation.json — both model comparisons and dataset quality.

data/processed/day3/saved_model_evaluation.json — selected-model metrics, language slices, independent Hinglish diagnostics and errors.

data/processed/day3/dataset_quality.json — class/length/overlap/frequent-word analysis.

data/processed/day3/top_class_terms.json — top model terms by class.

data/processed/day3/manual_hinglish_holdout.csv — 55 independently authored messages.

data/processed/day3/contextual_api_examples.json — complete live examples.
