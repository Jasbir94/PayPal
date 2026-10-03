"""Reproducible synthetic narrative corpus with family-disjoint, class-balanced splits."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from backend.app.config.context_config import SCENARIO_SEED, SAMPLES_PER_TEMPLATE, SCENARIO_DATA_PATH
from backend.app.utils.scenario_labels import get_scenario_labels
from scripts.scam_templates import TEMPLATES
from backend.app.features.text_features import normalize_text

NAMES = ('Sharma', 'Patel', 'Khan', 'Mehta', 'Rao', 'Roy', 'Kapoor', 'Verma')
CHANNELS = ('phone', 'SMS', 'WhatsApp', 'Telegram', 'email', 'social media')
DEADLINES = ('immediately', 'within an hour', 'before tonight', 'today', 'abhi', 'aaj hi')
PREFIXES = ('', 'This is what they told me: ', 'Please help me understand this message. ', 'Mujhe ye message mila: ')
SUFFIXES = ('', ' Is this the right way to pay?', ' They keep asking me to respond.', ' Kya mujhe ye payment karna chahiye?')


def normalized_text(text: str) -> str:
    return normalize_text(text)


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
