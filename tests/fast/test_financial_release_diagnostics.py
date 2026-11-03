import pytest
from scripts.verify_financial_release import require_calculation


def test_reference_mismatch_still_blocks_release_with_non_private_diagnostic(capsys):
    with pytest.raises(AssertionError):require_calculation(False,'BOX',21,'perf')
    assert capsys.readouterr().out.strip()=='Erreur contrôle financier : BOX / fenêtre 21 / perf'
    require_calculation(True,'BOX',21,'perf')


def test_unknown_labels_cannot_publish_arbitrary_data(capsys):
    with pytest.raises(AssertionError):require_calculation(False,'private-label',21,'private-field')
    assert 'private' not in capsys.readouterr().out
