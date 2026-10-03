"""Shared light text normalization and TF-IDF construction for both NLP modules."""
from sklearn.feature_extraction.text import TfidfVectorizer


def normalize_text(text: str) -> str:
    """Normalize case and spacing without removing negation or language cues."""
    return ' '.join(text.replace('’', "'").replace('‘', "'").casefold().split())


def make_text_vectorizer(**overrides) -> TfidfVectorizer:
    """Keep the established Day 3 unigram/bigram preprocessing configuration."""
    options = dict(ngram_range=(1, 2), min_df=2, max_features=18000,
                   sublinear_tf=True, strip_accents='unicode')
    options.update(overrides)
    return TfidfVectorizer(**options)
