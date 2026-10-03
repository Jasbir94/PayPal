from backend.app.security.text_normalization import normalize_text_view


def test_normalizes_common_obfuscation_and_preserves_original():
    view = normalize_text_view('P.A.Y N.O.W — p0l1ce  R.B.I')
    assert 'PAY NOW' in view.normalized_text
    assert 'police' in view.normalized_text
    assert 'RBI' in view.normalized_text
    assert view.original_text == 'P.A.Y N.O.W — p0l1ce  R.B.I'
    assert 'split_letters_joined' in view.transformations


def test_unicode_and_zero_width_variants_normalize():
    view = normalize_text_view('ｂａｎｋ\u200b transfer')
    assert view.normalized_text == 'bank transfer'
    assert 'unicode_nfkc' in view.transformations
    assert 'zero_width_removed' in view.transformations


def test_numeric_references_are_not_leetspeak_rewritten():
    assert normalize_text_view('A123 R2D2 001234').normalized_text == 'A123 R2D2 001234'


def test_hyphenated_split_letters_are_joined_safely():
    assert normalize_text_view('p-a-y-m-e-n-t').normalized_text == 'payment'
