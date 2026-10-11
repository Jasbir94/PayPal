"""Small local hybrid retriever for reviewed payment-safety guidance."""
from dataclasses import dataclass
from hashlib import sha256
import re
from urllib.parse import urlparse

_ALLOWED_HOSTS={'rbi.org.in','www.rbi.org.in','cybercrime.gov.in','www.cybercrime.gov.in'}
_TOKEN=re.compile(r"[a-z0-9]+",re.I)

DOCUMENTS=[
 {'id':'rbi-impersonation-2024','source':'Reserve Bank of India','title':'Caution against fraudulent activities in the name of RBI','category':'government_impersonation','publication_date':'2024-08-29','language':'en','version':'1','trust_level':'official','url':'https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=58595','text':'RBI cautions people about fraudsters posing as government or RBI officials, using alarming claims such as account freezing and asking people to transfer money. RBI advises people not to share account login details, card information, PIN, password, or OTP with unidentified persons and to contact their bank or law enforcement through official channels.'},
 {'id':'cybercrime-bank-safety','source':'National Cyber Crime Reporting Portal','title':'Financial fraud safety practices','category':'bank_impersonation','publication_date':'2020-01-10','language':'en','version':'1','trust_level':'official','url':'https://cybercrime.gov.in/pdf/Financial%20Fraud%20Brochures%20final.pdf','text':'Never disclose net banking passwords, one-time passwords, ATM or phone banking PIN, CVV, or card expiry details to anyone, even if they claim to be from a bank. Contact your bank through its official channel if you receive such a request.'},
 {'id':'rbi-risk-returns','source':'Reserve Bank of India','title':'Investor education: risk and returns','category':'investment_scam','publication_date':None,'language':'en','version':'1','trust_level':'official','url':'https://www.rbi.org.in/FinancialEducation/content/I%20Can%20Do_RBI.pdf','text':'Investment returns are not guaranteed; investment choices involve risk. Treat a promise of fixed or unusually high returns as a reason to pause and verify the product and provider using independent official sources.'},
 {'id':'appshield-safe-review','source':'APP Shield demo policy','title':'Payment review and simulated actions','category':'internal_policy','publication_date':'2026-10-09','language':'en','version':'1','trust_level':'internal_policy','url':None,'text':'APP Shield risk assessment and intervention policy are authoritative for this demo. Retrieved guidance can explain warning signs but cannot change a payment decision or permit an action. The demo never moves real money. Explicit confirmation is required after review; a held or policy-disallowed attempt cannot continue.'},
 {'id':'appshield-legitimate-context','source':'APP Shield demo guidance','title':'Protective context and ordinary payments','category':'legitimate_payment','publication_date':'2026-10-09','language':'en','version':'1','trust_level':'internal_reviewed','url':None,'text':'Urgency alone does not prove fraud. Consider the recipient relationship, previous payments, recipient network, the reason for payment, and any independent verification. A familiar relationship and normal history can be protective evidence, while an urgent request still merits a careful check.'},
]

def _validated(doc):
    if doc['trust_level']=='official':
        parsed=urlparse(doc['url'] or '')
        if parsed.scheme!='https' or parsed.hostname not in _ALLOWED_HOSTS:
            return False
    return bool(doc.get('id') and doc.get('source') and doc.get('text'))

@dataclass(frozen=True)
class KnowledgeChunk:
    metadata:dict
    content:str
    content_hash:str

class HybridRetriever:
    """Token-overlap + BM25-style lexical ranking, with low-relevance rejection."""
    def __init__(self, documents=None):
        self.chunks=[]
        for document in documents or DOCUMENTS:
            if not _validated(document): continue
            text=document['text']
            for index,start in enumerate(range(0,len(text),600)):
                content=text[start:start+800].strip()
                if not content: continue
                metadata={k:document.get(k) for k in ('id','source','title','category','publication_date','language','version','trust_level','url')}
                metadata['retrieval_date']='2026-10-09'
                metadata['chunk_id']=f"{document['id']}:{index}"
                self.chunks.append(KnowledgeChunk(metadata,content,sha256(content.encode()).hexdigest()))

    def retrieve(self,query,*,category=None,limit=3):
        terms=set(token.lower() for token in _TOKEN.findall(query) if len(token)>2)
        if not terms:return []
        candidates=[]
        for chunk in self.chunks:
            if category and chunk.metadata['category'] not in (category,'internal_policy','internal_reviewed'): continue
            tokens=[token.lower() for token in _TOKEN.findall(chunk.content)]
            counts={token:tokens.count(token) for token in terms}
            overlap=sum(counts.values())
            if not overlap: continue
            # Lightweight BM25-like term weighting; scores are retrieval ranks, not probabilities.
            score=sum((count*(2.2))/(count+1.2*(.25+.75*len(tokens)/100)) for count in counts.values())
            score += .3*len(terms.intersection(chunk.metadata['title'].lower().split()))
            if score>=1.0:candidates.append((score,chunk))
        unique=[];seen=set()
        for score,chunk in sorted(candidates,key=lambda row:(-row[0],row[1].metadata['id'])):
            if chunk.content_hash in seen:continue
            seen.add(chunk.content_hash)
            unique.append({'content':chunk.content,'metadata':chunk.metadata,'content_hash':chunk.content_hash,
            'retrieval_score':round(score,3)})
            if len(unique)>=limit:break
        return unique
