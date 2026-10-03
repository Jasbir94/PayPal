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
