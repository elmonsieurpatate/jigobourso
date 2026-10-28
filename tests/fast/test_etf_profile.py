import json
import pathlib
from engine.market.etf_profile import parse_profile

FIXTURE = pathlib.Path(__file__).resolve().parents[1] / 'fixtures' / 'yahoo' / 'quote_summary_iwda.json'


def test_real_response_parsed():
    p = parse_profile(json.loads(FIXTURE.read_text()))
    assert p['family'] and p['expense_ratio'] == 0.2
    assert p['holdings'][0]['symbol'] == 'NVDA' and 0 < p['holdings'][0]['weight'] < 20
    assert 'Technologie' in p['sectors'] and abs(sum(p['sectors'].values()) - 100) < 3
    assert p['top10_weight'] == round(sum(h['weight'] for h in p['holdings']), 1)


def test_not_a_fund_returns_none():
    assert parse_profile({'quoteSummary': {'result': [{'summaryDetail': {}}]}}) is None
    assert parse_profile({'quoteSummary': {'result': None}}) is None
    assert parse_profile(None) is None
