"""Generate a 6,000-row multi-label corpus with disjoint phrase families."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from backend.app.config.psychology_config import SEED, PSYCHOLOGY_DATA_PATH
from backend.app.utils.psychology_labels import get_psychology_labels
from backend.app.features.text_features import normalize_text
from scripts.psychology_templates import TECHNIQUE_PHRASES, NEUTRAL_PHRASES

PREFIXES = ('', 'The message says: ', 'I received this wording: ', 'Mujhe ye text mila: ')
SUFFIXES = ('', ' What should I do?', ' Is this request appropriate?', ' Is payment ka matlab kya hai?')
DETAILS = ('My payment question involves {amount}.', 'The amount I am asking about is {amount}.',
           'I am considering a payment of {amount}.', 'Mera payment question {amount} ke bare me hai.')


def _family_roles(count: int, rng: np.random.Generator) -> dict[int, str]:
    """Keep families disjoint. Row counts, not family counts, use 70/15/15."""
    if count % 2:
        raise ValueError('English/Hinglish banks must have equal size')
    half = count // 2
    roles = {}
    for offset in (0, half):
        groups = rng.permutation(np.arange(offset, offset+half))
        # At least one source family per language for validation and test.
        for position, index in enumerate(groups):
            roles[int(index)] = 'train' if position < half-2 else 'validation' if position == half-2 else 'test'
    return roles


def generate_psychology_messages(count: int = 6000, seed: int = SEED) -> pd.DataFrame:
    if count < 100:
        raise ValueError('At least 100 messages are required')
    labels = get_psychology_labels()
    if set(TECHNIQUE_PHRASES) != set(labels):
        raise ValueError('Phrase bank taxonomy differs from labels.json')
    rng = np.random.default_rng(seed)
    assignments = {label: _family_roles(len(bank), rng) for label, bank in TECHNIQUE_PHRASES.items()}
    neutral_roles = _family_roles(len(NEUTRAL_PHRASES), rng)
    train_count, validation_count = int(count*.70), int(count*.15)
    sizes = {'train': train_count, 'validation': validation_count, 'test': count-train_count-validation_count}
    rows, seen = [], set()
    for role, size in sizes.items():
        for row_number in range(size):
            language = 'English' if row_number % 2 == 0 else 'Hinglish'
            for attempt in range(100):
                positive_labels, phrases, families = set(), [], []
                neutral = rng.random() < .22
                if neutral:
                    half = len(NEUTRAL_PHRASES)//2
                    pool = [i for i, r in neutral_roles.items() if r == role and (i < half) == (language == 'English')]
                    chosen = int(rng.choice(pool))
                    phrases.append(NEUTRAL_PHRASES[chosen])
                    families.append(f'neutral:{chosen}')
                else:
                    techniques = int(rng.choice([1, 2, 3, 4], p=[.40, .30, .22, .08]))
                    chosen_labels = rng.choice(labels, size=techniques, replace=False)
                    for label in chosen_labels:
                        bank = TECHNIQUE_PHRASES[label]
                        pool = [i for i, r in assignments[label].items() if r == role and (i < 5) == (language == 'English')]
                        chosen = int(rng.choice(pool))
                        phrase, extras = bank[chosen]
                        positive_labels.update((label, *extras))
                        phrases.append(phrase)
                        families.append(f'{label}:{chosen}')
                amount = f'₹{int(rng.integers(10, 1500))*100:,}'
                name = str(rng.choice(['Sharma', 'Patel', 'Rao', 'Verma', 'Khan', 'Mehta']))
                text = ' '.join(phrases).format(amount=amount, name=name)
                # Shared, non-label-bearing framing supplies variation to neutral examples too.
                prefix = str(rng.choice(PREFIXES))
                suffix = str(rng.choice(SUFFIXES))
                detail = str(rng.choice(DETAILS)).format(amount=amount)
                text = prefix + text + ' ' + detail + suffix
                style = rng.random()
                if style < .05:
                    text = text.upper()
                elif style < .15:
                    text = text.lower()
                elif style < .22:
                    text = text.replace('immediately', 'immediatly').replace('please', 'pls')
                normalized = normalize_text(text)
                if normalized not in seen:
                    seen.add(normalized)
                    break
            else:
                raise ValueError('Could not produce a unique psychology message')
            rows.append({'message_id': f'PSY{len(rows):06d}', 'text': text,
                **{label: int(label in positive_labels) for label in labels},
                'language': language, 'split': role, 'source_families': '|'.join(sorted(families)),
                'neutral': neutral})
    return pd.DataFrame(rows).sample(frac=1, random_state=seed).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, default=6000)
    parser.add_argument('--seed', type=int, default=SEED)
    parser.add_argument('--output', type=Path, default=PSYCHOLOGY_DATA_PATH)
    args = parser.parse_args()
    data = generate_psychology_messages(args.count, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(args.output, index=False)
    print(f'Saved {len(data)} unique multi-label messages to {args.output}')
    print(data.groupby('split')[list(get_psychology_labels())].agg(['size', 'sum']).to_string())


if __name__ == '__main__':
    main()
