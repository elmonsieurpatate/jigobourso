"""Filtres pays et catégorie à choix multiple (valeurs séparées par « | »)."""
from engine.analytics import service


def test_choices_accepts_pipe_separated_text_and_lists():
    assert service._choices('US|DE| FR ') == {'US', 'DE', 'FR'}
    assert service._choices(['US', '']) == {'US'}
    assert service._choices(None) == set() and service._choices('') == set()


def test_front_end_and_back_end_share_the_same_separator():
    import pathlib
    js = (pathlib.Path(__file__).resolve().parents[2] / 'app/public/assets/multiselect.js').read_text()
    assert "SEP = '|'" in js
