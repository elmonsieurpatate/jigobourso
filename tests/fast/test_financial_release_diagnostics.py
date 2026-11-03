import pytest
from scripts.verify_financial_release import require_calculation


def test_reference_mismatch_still_blocks_release_with_non_private_diagnostic(capsys):
    with pytest.raises(AssertionError):require_calculation(False,'BOX',21,'perf')
    assert capsys.readouterr().out.strip()=='Erreur contrôle financier : BOX / fenêtre 21 / perf'
    require_calculation(True,'BOX',21,'perf')


def test_unknown_labels_cannot_publish_arbitrary_data(capsys):
    with pytest.raises(AssertionError):require_calculation(False,'private-label',21,'private-field')
    assert 'private' not in capsys.readouterr().out


def test_failed_read_only_check_releases_its_snapshot(monkeypatch):
    from scripts import verify_financial_release as v
    class Cursor:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def execute(self,*args):pass
        def fetchall(self):return []
    class Conn:
        rolled_back=False
        closed=False
        def cursor(self):return Cursor()
        def rollback(self):self.rolled_back=True
        def close(self):self.closed=True
    c=Conn();monkeypatch.setattr(v,'connect',lambda:c)
    with pytest.raises(AssertionError):v.run()
    assert c.rolled_back and c.closed
