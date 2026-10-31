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


def payload(closes, adj, tz='America/New_York', volumes=None):
    return {'chart': {'result': [{'meta': {'exchangeTimezoneName': tz}, 'timestamp': T[:len(closes)],
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
    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def get(self, path, params):
        symbol = path.rsplit('/', 1)[-1]
        self.calls.append((symbol, params))
        answer = self.answers[symbol]
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
    assert first.calls[0][1]['range'] == '10y' and first.calls[0][1]['includeAdjustedClose'] == 'true'
    with open(os.path.join(out, 'universe.csv'), encoding='utf-8') as fh:
        assert [r['symbol'] for r in csv.DictReader(fh)] == ['AAA', 'BBB', 'CCC']
    second = FakeTransport(answers)
    again = eh.export(UNIVERSE, second, out, years=10)
    assert again['already'] == 3 and again['done'] == 0 and second.calls == []          # rien n'est redemandé


def test_rate_limit_stops_cleanly_and_resumes(tmp_path):
    out = str(tmp_path)
    good = payload([10.0, 11.0], [9.0, 10.0])
    limited = FakeTransport({'AAA': good, 'BBB': RateLimited(30), 'CCC': good})
    stats = eh.export(UNIVERSE, limited, out)
    assert stats['done'] == 1 and stats['rate_limited'] and stats['remaining'] == 2
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
