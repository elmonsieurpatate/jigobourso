"""Filtres pays et catégorie à choix multiple (valeurs séparées par « | »)."""
from engine.analytics import service


def test_choices_accepts_pipe_separated_text_and_lists():
    assert service._choices('US|DE| FR ') == {'US', 'DE', 'FR'}
    assert service._choices(['US', '']) == {'US'}
    assert service._choices(None) == set() and service._choices('') == set()

