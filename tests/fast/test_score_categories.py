"""Filtres « Score simple V4 » et « Score complexe V4 » : définitions proposées, rangement des notes, sélection sans effet sur notes ni rangs."""
import copy
import json
import pathlib

import pytest

from engine.analytics.scoring import score_categories as SCAT
from engine.analytics.scoring import scores as SC

CONFIG = pathlib.Path(__file__).resolve().parents[2] / 'app' / 'config' / 'explorer_secondary_filters.json'
DEFS = json.loads(CONFIG.read_text(encoding='utf-8'))


@pytest.fixture(params=['simple', 'complex'])
def which(request):
    return request.param


def cats(which):
    c, enabled = SCAT.measure(DEFS, which)
    assert enabled
    return c


def test_the_two_filters_exist_like_the_other_editable_filters(which):
    fid, mid = SCAT.FILTERS[which]
    f = next(x for x in DEFS['filters'] if x['id'] == fid)
    assert f['editable'] and f['enabled'] and f['group'] == 'main' and len(f['measures']) == 1
    m = f['measures'][0]
    assert m['id'] == mid and m['kind'] == 'numeric' and m['unit'] == '/100' and m['supportsUnknown']
    assert [c['name'] for c in m['categories']] == ['Très faible', 'Faible', 'Modéré', 'Élevé', 'Très élevé', 'Inconnu']
    assert len(DEFS['filters']) == 15 and sum(1 for x in DEFS['filters'] if x['editable']) == 11
    assert all(c['active'] for c in m['categories'])                                # toutes incluses par défaut


def test_categories_cover_zero_to_hundred_without_gap_or_overlap(which):
    c = cats(which)
    for v in [i / 100 for i in range(0, 10001)] + [0, 100, 0.0001, 99.9999]:
        hits = [x['id'] for x in c if not x['unknown'] and SCAT._inside(x, v)]
        assert len(hits) == 1, (which, v, hits)
        assert SCAT.assign(v, c) == hits[0]
    bounds = [(x['min'], x['max']) for x in c if not x['unknown']]
    assert bounds[0][0] is None and bounds[-1][1] is None                         # extrémités ouvertes : couvrent [0 ; 100] sans trou
    assert all(bounds[i][1] == bounds[i + 1][0] for i in range(len(bounds) - 1))
    assert [x['name'] for x in c if SCAT._inside(x, 0) and not x['unknown']] == ['Très faible'] and SCAT.assign(100, c) == next(x['id'] for x in c if x['name'] == 'Très élevé')


def test_zero_hundred_partial_and_unavailable_scores(which):
    c = cats(which)
    ids = {x['name']: x['id'] for x in c}
    assert SCAT.assign(0.0, c) == ids['Très faible'] and SCAT.assign(100.0, c) == ids['Très élevé']
    assert SCAT.assign(None, c) == ids['Inconnu']                                  # indisponible ≠ 0
    partial = SC.score_title({5: None, 21: dict(slope=.7, r2=.9, up_fraction=.6, spike_share=.3, volatility=2, drawdown=5)}, {'turnover_eur': None},
                             [dict(id='week', sessions=5), dict(id='month', sessions=21)])
    assert partial['simple']['status'] == 'partiel' and partial['simple']['score'] is not None
    assert SCAT.assign(partial['simple']['score'], c) != ids['Inconnu']            # un score partiel reste une note, rangée par sa valeur
    assert SCAT.assign(partial['complex']['score'], c) != ids['Inconnu']


def test_selection_keeps_notes_ranks_and_calculation_untouched(which):
    c = cats(which)
    names = {x['id']: x['name'] for x in c}
    values = [0.0, 0.5, 3.0, 8.0, 20.0, 40.0, 61.0, 100.0, None, 12.5]
    entries = [{'id': i, 'score_' + which: v, 'rank': i + 1, 'score': v} for i, v in enumerate(values)]
    before = copy.deepcopy(entries)
    kept = SCAT.select(entries, which, [x['id'] for x in c if x['name'] in ('Élevé', 'Très élevé')], c)
    assert entries == before                                                       # rien n'est modifié ni supprimé
    assert all(names[SCAT.assign(e['score_' + which], c)] in ('Élevé', 'Très élevé') for e in kept) and kept and len(kept) < len(entries)
    assert all(e is entries[e['id']] and e['rank'] == e['id'] + 1 for e in kept)   # mêmes lignes, mêmes rangs globaux
    only_unknown = SCAT.select(entries, which, [x['id'] for x in c if x['unknown']], c)
    assert [e['id'] for e in only_unknown] == [8]
    assert SCAT.select(entries, which, [x['id'] for x in c], c) == entries         # tout inclus : aucune ligne masquée
    assert SCAT.select(entries, which, None, c) == entries


def test_existing_thirteen_filters_are_unchanged():
    import subprocess
    old = subprocess.run(['git', 'show', 'c8abdda:app/config/explorer_secondary_filters.json'], capture_output=True, text=True, cwd=CONFIG.parents[2])
    if old.returncode != 0:
        pytest.skip('référence c8abdda absente')
    before = json.loads(old.stdout)['filters']
    now = [f for f in DEFS['filters'] if f['id'] not in ('score_simple', 'score_complex')]
    assert now == before and len(now) == 13
