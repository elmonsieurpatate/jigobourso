import pytest
from scripts.release.prepare_financial_release import prepare


def test_consistent_cache_needs_no_refresh():
    prepare(check=lambda:None,refresh=lambda:pytest.fail('unneeded refresh'))


def test_mismatch_refreshes_once_and_checks_again():
    calls=[]
    def check():
        calls.append('check')
        if len(calls)==1:raise AssertionError('stale')
    prepare(check=check,refresh=lambda:calls.append('normal metrics job'))
    assert calls==['check','normal metrics job','check']


def test_remaining_mismatch_still_blocks_release():
    def check():raise AssertionError('still inconsistent')
    with pytest.raises(AssertionError):prepare(check=check,refresh=lambda:None)


def test_non_metric_error_is_not_hidden_or_refreshed():
    def check():raise RuntimeError('connection unavailable')
    with pytest.raises(RuntimeError):prepare(check=check,refresh=lambda:pytest.fail('must not refresh'))
