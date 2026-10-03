"""Conservative reversible-view text normalization for defensive detection.

The caller keeps the original string separately. This function does not mutate,
persist or log it, and returns only a derived view plus transformation labels.
"""
from dataclasses import dataclass
import re
import unicodedata

_ZERO_WIDTH = dict.fromkeys(map(ord, '\u200b\u200c\u200d\u2060\ufeff'), None)
_LOOKALIKES = str.maketrans({'а':'a','е':'e','о':'o','р':'p','с':'c','х':'x','і':'i','у':'y',
                             'А':'A','Е':'E','О':'O','Р':'P','С':'C','Х':'X','І':'I','У':'Y'})
_LEET = str.maketrans({'0':'o','1':'i','3':'e','@':'a','$':'s'})

@dataclass(frozen=True)
class TextView:
    original_text: str
    normalized_text: str
    transformations: tuple[str, ...]

def normalize_text_view(text: str | None) -> TextView:
    original = text or ''
    value = unicodedata.normalize('NFKC', original)
    changes=[]
    if value != original: changes.append('unicode_nfkc')
    without_zero=value.translate(_ZERO_WIDTH)
    if without_zero != value: changes.append('zero_width_removed')
    value=without_zero.translate(_LOOKALIKES)
    if value != without_zero: changes.append('unicode_lookalike_fold')
    # Keep line/sentence boundaries meaningful while normalizing horizontal space.
    value=re.sub(r'\r\n?|\n', '. ', value)
    # Join only punctuation-separated letters (R.B.I, p-o-l-i-c-e); hyphens
    # between words become spaces to preserve phrase boundaries.
    acronym_fold=re.sub(r'(?i)(?<!\w)(?:[a-z]\.){2,}[a-z](?!\w)',
                 lambda m:m.group(0).replace('.',''), value)
    if acronym_fold != value: changes.append('split_letters_joined')
    value=acronym_fold
    spaced_letters=re.sub(r'(?<!\w)(?:[A-Za-z]\s+){2,}[A-Za-z](?!\w)',
                          lambda m:re.sub(r'\s+','',m.group(0)), value)
    if spaced_letters != value: changes.append('split_letters_joined')
    value=spaced_letters
    punctuation=re.sub(r'(?<=[A-Za-z])[-_](?=[A-Za-z])',' ',value)
    joined_hyphens=re.sub(r'(?<!\w)(?:[A-Za-z]\s+){2,}[A-Za-z](?!\w)',
                 lambda m:re.sub(r'\s+','',m.group(0)), punctuation)
    if joined_hyphens != punctuation: changes.append('split_letters_joined')
    value=joined_hyphens
    # Normalize leetspeak only inside an alphabetic token; standalone numbers,
    # account IDs and payment amounts remain unchanged.
    def map_token(match):
        token=match.group(0)
        # Avoid rewriting short identifiers such as A123 or R2D2. Require
        # multiple letters so ordinary account/payment references stay intact.
        if len(re.findall(r'[A-Za-z]', token)) < 2: return token
        return token.translate(_LEET)
    leet=re.sub(r'(?<!\w)[A-Za-z0-9@$]+(?!\w)',map_token,value)
    if leet != value: changes.append('in_word_leetspeak_fold')
    value=re.sub(r'([!?.,])\1{2,}',r'\1',leet)
    value=re.sub(r'[ \t\f\v]+',' ',value)
    value=re.sub(r'\s*([!?.,])\s*',r'\1 ',value).strip()
    value=re.sub(r'\s+',' ',value)
    if value != original and not changes: changes.append('whitespace_or_punctuation_normalized')
    return TextView(original, value, tuple(dict.fromkeys(changes)))
