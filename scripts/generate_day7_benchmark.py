"""Generate a deterministic, template-based robustness corpus (not real-world data)."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCAMS=[
 ('authority','Police verification is required immediately. Transfer {amount} to the secure account now.'),
 ('authority','Your bank fraud department says your account will be frozen. Pay {amount} to protect it.'),
 ('urgency','Your parcel is held for a small customs fee. Pay {amount} today to release it.'),
 ('fear','A court case has been filed against you. Send {amount} now to avoid arrest.'),
 ('urgency','Your electricity will be disconnected in one hour unless you pay {amount}.'),
 ('authority','This is an RBI security check. Move {amount} to the safe account for verification.'),
 ('secrecy','Do not tell your family or bank. Send {amount} privately and I will return it.'),
 ('urgency','Your KYC expires today. Share the code and transfer {amount} to keep access.'),
 ('fear','Your child is in trouble. Send {amount} immediately and do not call anyone.'),
 ('authority','I am support staff. Give me your OTP so I can reverse the payment.'),
 ('urgency','The prize expires in minutes. Pay a {amount} processing fee to claim it.'),
 ('fear','Your account is compromised. Transfer {amount} to this temporary wallet right away.'),
 ('secrecy','Keep this confidential; send {amount} in gift cards and delete this chat.'),
 ('authority','The tax officer requires an urgent deposit of {amount} to clear your record.'),
 ('urgency','Your job offer is reserved. Pay {amount} for equipment before the deadline.'),
 ('fear','A relative has been detained. Send {amount} now and do not contact the police.'),
 ('authority','The bank agent needs remote access and an OTP to secure your money.'),
 ('urgency','Send a small test payment of {amount}; I will unlock the larger refund.'),
 ('secrecy','Your manager approved this secret vendor payment. Transfer {amount} now.'),
 ('fear','A virus infected your phone. Move {amount} before the account is emptied.'),
 ('urgency','Pay {amount} now to stop a legal penalty from increasing.'),
 ('authority','The government grant is ready; pay {amount} as a release charge.'),
 ('secrecy','Use this new account only and do not verify with your usual contact.'),
 ('fear','You will lose your savings unless you transfer {amount} to our safe account.'),
 ('urgency','Your delivery needs a {amount} redelivery deposit right now.'),
]
BENIGN=[
 'Please transfer {amount} for this month rent to my usual landlord.',
 'The hospital asked me to pay {amount} for the scheduled appointment.',
 'I am paying {amount} for groceries at the familiar local shop.',
 'Please send {amount} for the college fee using the official portal.',
 'I am sending {amount} to my sibling for our planned family dinner.',
 'The electricity bill of {amount} is due; I opened the official provider app.',
 'I am paying {amount} to the known travel company for my booked ticket.',
 'Please transfer {amount} to our regular supplier against invoice 42.',
 'I am paying {amount} for a laptop at the store where I am shopping.',
 'The bank app shows my routine loan installment of {amount}.',
 'I will pay {amount} for the confirmed hotel reservation.',
 'Please send {amount} to my friend for the shared lunch we had.',
 'My dentist appointment invoice is {amount}; I will pay at reception.',
 'I am paying {amount} to the known charity through its verified website.',
 'The monthly subscription renewal is {amount} in the official app.',
 'I am paying {amount} for a repair after receiving the service estimate.',
 'Please pay {amount} for the regular water bill on the provider website.',
 'I am investing {amount} through my established brokerage account.',
 'The school trip fee is {amount}; the teacher sent the normal notice.',
 'I am paying {amount} to the merchant after checking out in person.',
 'Please send {amount} to my parent for their planned medicine purchase.',
 'I am paying {amount} for my usual ride booked in the transport app.',
 'The insurance premium of {amount} is due through the official insurer app.',
 'Please transfer {amount} to my business partner for our agreed invoice.',
 'I am paying {amount} for a class I registered for last week.',
]
AMOUNTS=[10,25,100,500,1200]
VARIANTS=['base','hinglish','leet','split','punctuation','indirect','misspelling','lowercase','polite','small_amount','zero_width','unicode',
 'emoji','elongation','question','formal','fragmented','currency_format','paraphrase','all_caps']
def mutate(text,variant):
 if variant=='base': return text
 if variant=='hinglish': return 'Bhai, '+text+' please, abhi kar do.'
 if variant=='leet': return text.replace('transfer','tr4nsfer').replace('pay ','p@y ').replace('police','p0lice').replace('bank','b@nk')
 if variant=='split': return text.replace('payment','p-a-y-m-e-n-t').replace('police','p-o-l-i-c-e').replace('RBI','R.B.I')
 if variant=='punctuation': return '!!! '.join(text.split(' '))+'!!!'
 if variant=='indirect': return text.replace('Send ','Could you arrange ').replace('Transfer ','Could you arrange ').replace('Pay ','Could you arrange ')
 if variant=='misspelling': return text.replace('immediately','immediatly').replace('transfer','transferr').replace('payment','paymant')
 if variant=='lowercase': return text.lower()
 if variant=='polite': return 'Please, '+text+' thanks.'
 if variant=='small_amount': return text.replace('{amount}','10')
 if variant=='zero_width': return text.replace('transfer','trans\u200bfer').replace('pay ','p\u200bay ')
 if variant=='unicode': return text.replace('a','ａ').replace('e','ｅ')
 if variant=='emoji': return text+' 🙏'
 if variant=='elongation': return text.replace('urgent','urgennnt').replace('transfer','transferrr')
 if variant=='question': return 'Could you please help me? '+text
 if variant=='formal': return 'Kindly note: '+text+' Regards.'
 if variant=='fragmented': return ' '.join(text.split(' ')[:3])+' ... '+' '.join(text.split(' ')[3:])
 if variant=='currency_format': return text.replace('{amount}','Rs 10')
 if variant=='paraphrase': return text.replace('Send ','Arrange ').replace('Transfer ','Move ').replace('Pay ','Settle ')
 if variant=='all_caps': return text.upper()

def main():
 rows=[]
 for label,templates in [('scam',SCAMS),('legitimate',BENIGN)]:
  for ti,item in enumerate(templates):
   template=item[1] if isinstance(item,tuple) else item
   for vi,variant in enumerate(VARIANTS):
    amount=AMOUNTS[(ti+vi)%len(AMOUNTS)]
    text=mutate(template.format(amount=amount),variant)
    rows.append({'case_id':f'{label}-{ti:02d}-{vi:02d}','label':label,'text':text,
       'amount':amount,'category':variant,'source_template':f'{label}-{ti:02d}',
       'split':'holdout' if ti>=20 else ('development' if ti<15 else 'validation'),
       'difficulty':'hard' if variant!='base' or amount<=25 else 'easy',
       'synthetic':True,'ground_truth_scope':'authored message-level label'})
 out=ROOT/'data'/'adversarial'/'benchmark.json'
 out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps({'title':'APP Shield Day 7 authored synthetic text benchmark',
   'case_count':len(rows),'source_template_count':len(SCAMS)+len(BENIGN),
   'notice':'Deterministic template-based robustness probe; not representative production prevalence or payment-level labels.',
   'cases':rows},ensure_ascii=False,indent=2),encoding='utf-8')
 print(f'wrote {len(rows)} cases to {out}')
if __name__=='__main__': main()
