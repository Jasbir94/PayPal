"""Sentence-scoped weighted manipulation evidence with explicit hard-negative handling."""
import re
from backend.app.features.text_features import normalize_text
from backend.app.rules.psychology_patterns import PATTERNS, BENIGN_QUALIFIERS
from backend.app.utils.psychology_labels import get_psychology_labels

COMPILED = {label: [(code, re.compile(pattern), weight) for code, pattern, weight in patterns]
            for label, patterns in PATTERNS.items()}
BENIGN = {label: re.compile(pattern) for label, pattern in BENIGN_QUALIFIERS.items()}


def detect_psychology_rules(text: str | None) -> dict:
    labels = get_psychology_labels()
    if set(COMPILED) != set(labels):
        raise ValueError('Pattern taxonomy differs from psychology labels.json')
    scores = dict.fromkeys(labels, 0.0)
    reasons, evidence, suppressed = [], {}, []
    if not text or not text.strip():
        return {'scores': scores, 'reasons': ['message_unavailable'], 'evidence': {}, 'suppressed_techniques': []}
    sentences = [normalize_text(part) for part in re.split(r'(?<=[.!?])\s+|[;\n]+', text) if part.strip()]
    for label in labels:
        matches = {}
        for sentence in sentences:
            if BENIGN[label].search(sentence):
                suppressed.append(label)
                continue
            for code, pattern, weight in COMPILED[label]:
                match = pattern.search(sentence)
                if match:
                    # Count distinct patterns, not repeated copies of the same phrase.
                    matches[code] = max(weight, matches.get(code, 0))
        remaining = 1.0
        for code, weight in matches.items():
            remaining *= 1 - weight
            reasons.append(code)
        scores[label] = round(1 - remaining, 6)
        if matches:
            evidence[label] = {'pattern_codes': list(matches), 'distinct_pattern_count': len(matches)}
    suppressed = [label for label in dict.fromkeys(suppressed) if scores[label] == 0]
    return {'scores': scores, 'reasons': list(dict.fromkeys(reasons)) or ['no_rule_manipulation_evidence'],
            'evidence': evidence, 'suppressed_techniques': suppressed}
