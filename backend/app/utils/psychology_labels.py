"""Read the multi-label taxonomy once from its JSON source of truth."""
import json
from functools import lru_cache
from backend.app.config.psychology_config import PSYCHOLOGY_LABELS_PATH


@lru_cache(maxsize=1)
def get_psychology_labels() -> tuple[str, ...]:
    labels = json.loads(PSYCHOLOGY_LABELS_PATH.read_text(encoding='utf-8'))
    if not isinstance(labels, list) or len(labels) != 10 or len(labels) != len(set(labels)):
        raise ValueError('Psychology taxonomy must contain ten unique labels')
    return tuple(labels)


def validate_technique(label: str) -> str:
    if label not in get_psychology_labels():
        raise ValueError(f'Unknown manipulation technique: {label}')
    return label
