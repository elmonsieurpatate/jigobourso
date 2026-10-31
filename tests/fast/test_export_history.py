"""Export de l'historique long (scripts/export_history.py) : lecture de la réponse Yahoo, fichiers atomiques, reprise, arrêt propre sur un 429."""
import csv
import gzip
import importlib.util
import json
import os

import pytest

from engine.market.yahoo import RateLimited, YahooError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location('export_history', os.path.join(ROOT, 'scripts', 'export_history.py'))
eh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eh)

# 2026-01-05 → 2026-01-08 14:30 UTC = 09:30 à New York
T = [1767623400 + 86400 * i for i in range(4)]


def payload(closes, adj, tz='America/New_York', volumes=None, stamps=None):
    return {'chart': {'result': [{'meta': {'exchangeTimezoneName': tz}, 'timestamp': stamps or T[:len(closes)],
                                  'indicators': {'quote': [{'close': closes, 'volume': volumes or [1000] * len(closes)}], 'adjclose': [{'adjclose': adj}]}}]}}


def test_parse_daily_keeps_adjusted_and_skips_incomplete_days():
    data = eh.parse_daily(payload([10.0, None, 12.0, 13.0], [9.5, 9.9, None, 12.4]))
    assert [r[0] for r in data['rows']] == ['2026-01-05', '2026-01-08']
    assert data['rows'][0][1:3] == (10.0, 9.5) and data['skipped'] == 2             # jour sans clôture et jour sans cours ajusté écartés, jamais complétés


def test_parse_daily_unusable_answers():
    assert eh.parse_daily({}) is None
    assert eh.parse_daily({'chart': {'result': None}}) is None
    assert eh.parse_daily(payload([None, None], [None, None])) is None


class FakeTransport:
    """`answers[symbole]` : une réponse, une exception, ou une LISTE consommée appel après appel (pour simuler une panne puis un retour à la normale)."""

    def __init__(self, answers):
        self.answers, self.calls, self.min_interval = answers, [], 0.8

    def get(self, path, params):
        symbol = path.rsplit('/', 1)[-1]
        self.calls.append((symbol, params))
        answer = self.answers[symbol]
        if isinstance(answer, list):
            answer = answer.pop(0) if len(answer) > 1 else answer[0]
        if isinstance(answer, Exception):
            raise answer
        return json.dumps(answer)


UNIVERSE = [{'key': i, 'symbol': s, 'mic': 'XNYS', 'kind': 'equity', 'country': 'United States', 'currency': 'USD'} for i, s in ((1, 'AAA'), (2, 'BBB'), (3, 'CCC'))]


def read_history(path):
    with gzip.open(path, 'rt', encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def test_export_writes_files_and_is_resumable(tmp_path):
    out = str(tmp_path)
    answers = {s: payload([10.0, 11.0, 12.0], [9.0, 10.0, 11.0]) for s in ('AAA', 'BBB', 'CCC')}
    first = FakeTransport(answers)
    stats = eh.export(UNIVERSE, first, out, years=10)
    assert stats['done'] == 3 and stats['errors'] == 0 and not stats['rate_limited']
    rows = read_history(eh.history_path(out, 1))
    assert [r['date'] for r in rows] == ['2026-01-05', '2026-01-06', '2026-01-07'] and rows[0]['adjclose'] == '9.0'
    params = first.calls[0][1]
    assert 'range' not in params and params['period1'] > 0 and params['period2'] > params['period1'] and params['includeAdjustedClose'] == 'true'   # par dates, jamais range=max
    with open(os.path.join(out, 'universe.csv'), encoding='utf-8') as fh:
        assert [r['symbol'] for r in csv.DictReader(fh)] == ['AAA', 'BBB', 'CCC']
    second = FakeTransport(answers)
    again = eh.export(UNIVERSE, second, out, years=10)
    assert again['already'] == 3 and again['done'] == 0 and second.calls == []          # rien n'est redemandé


def test_rate_limit_stops_cleanly_and_resumes(tmp_path):
    out = str(tmp_path)
    good = payload([10.0, 11.0], [9.0, 10.0])
    limited = FakeTransport({'AAA': good, 'BBB': RateLimited(None), 'CCC': good})
    waits = []
    stats = eh.export(UNIVERSE, limited, out, sleep=waits.append)
    assert stats['done'] == 1 and stats['rate_limited'] and stats['remaining'] == 2
    assert stats['retries'] == 4 and len(waits) == 4 and waits[0] >= 20 and waits == sorted(waits)      # attentes croissantes avant d'abandonner proprement
    assert os.path.exists(eh.history_path(out, 1)) and not os.path.exists(eh.history_path(out, 2))
    assert not [f for f in os.listdir(os.path.join(out, 'history')) if f.endswith('.part')]     # jamais de fichier tronqué
    resumed = eh.export(UNIVERSE, FakeTransport({'BBB': good, 'CCC': good}), out)
    assert resumed['already'] == 1 and resumed['done'] == 2 and not resumed['rate_limited']


def test_unknown_symbol_is_logged_and_does_not_stop_the_export(tmp_path):
    out = str(tmp_path)
    good = payload([10.0, 11.0], [9.0, 10.0])
    stats = eh.export(UNIVERSE, FakeTransport({'AAA': YahooError('HTTP 404'), 'BBB': good, 'CCC': {'chart': {'result': None}}}), out)
    assert stats['errors'] == 1 and stats['done'] == 1 and stats['empty'] == 1
    assert 'HTTP 404' in open(os.path.join(out, 'errors.log'), encoding='utf-8').read()
    assert read_history(eh.history_path(out, 3)) == []                                    # « demandé, rien reçu » : pas de nouvel appel à la relance


def test_whole_history_is_requested_by_dates_not_by_range_max(tmp_path):
    transport = FakeTransport({'AAA': payload([10.0, 11.0], [9.0, 10.0])})
    eh.fetch_daily(transport, 'AAA', 0)
    params = transport.calls[0][1]
    assert params['period1'] == 0 and 'range' not in params          # range=max renvoie un point par mois


def test_monthly_history_is_refused_not_saved_as_daily(tmp_path):
    out = str(tmp_path)
    monthly = [1767623400 + 30 * 86400 * i for i in range(14)]
    transport = FakeTransport({'AAA': payload([10.0 + i for i in range(14)], [9.0 + i for i in range(14)], stamps=monthly),
                               'BBB': payload([10.0, 11.0], [9.0, 10.0]), 'CCC': payload([10.0, 11.0], [9.0, 10.0])})
    stats = eh.export(UNIVERSE, transport, out)
    assert stats['errors'] == 1 and stats['done'] == 2
    assert not os.path.exists(eh.history_path(out, 1))               # rien d'enregistré : la relance le redemandera
    assert 'non quotidien' in open(os.path.join(out, 'errors.log'), encoding='utf-8').read()


def test_transient_424_is_retried_then_saved(tmp_path):
    good = payload([10.0, 11.0], [9.0, 10.0])
    transport = FakeTransport({'AAA': [YahooError('HTTP 424'), good], 'BBB': good, 'CCC': good})
    waits = []
    stats = eh.export(UNIVERSE, transport, str(tmp_path), sleep=waits.append)
    assert stats['done'] == 3 and stats['errors'] == 0 and stats['retries'] == 1 and len(waits) == 1
    assert [c[0] for c in transport.calls].count('AAA') == 2


def test_retry_after_is_honoured_and_calls_are_spaced_out_afterwards(tmp_path):
    good = payload([10.0, 11.0], [9.0, 10.0])
    transport = FakeTransport({'AAA': [RateLimited('90'), good], 'BBB': good, 'CCC': good})
    waits = []
    stats = eh.export(UNIVERSE, transport, str(tmp_path), sleep=waits.append)
    assert stats['done'] == 3 and waits[0] >= 90 and waits[0] <= 90 * 1.2 + 0.01
    assert transport.min_interval > 0.8                                  # pause entre appels augmentée après le refus


def test_unknown_symbol_404_is_not_retried(tmp_path):
    transport = FakeTransport({'AAA': YahooError('HTTP 404'), 'BBB': payload([10.0, 11.0], [9.0, 10.0]), 'CCC': payload([10.0, 11.0], [9.0, 10.0])})
    waits = []
    stats = eh.export(UNIVERSE, transport, str(tmp_path), sleep=waits.append)
    assert stats['errors'] == 1 and stats['retries'] == 0 and waits == []


def test_persistent_blocking_stops_the_export_instead_of_hammering_yahoo(tmp_path):
    universe = [{'key': i, 'symbol': f'T{i}', 'mic': 'XNYS', 'kind': 'equity', 'country': '', 'currency': 'USD'} for i in range(20)]
    transport = FakeTransport({u['symbol']: YahooError('HTTP 424') for u in universe})
    stats = eh.export(universe, transport, str(tmp_path), sleep=lambda w: None)
    assert stats['blocked'] and stats['errors'] == eh.MAX_CONSECUTIVE_FAILURES and stats['remaining'] == 20 - eh.MAX_CONSECUTIVE_FAILURES
    assert len(transport.calls) == eh.MAX_CONSECUTIVE_FAILURES * (len(eh.RETRY_WAITS) + 1)     # bornée : pas de boucle sans fin
