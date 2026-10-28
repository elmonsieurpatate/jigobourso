import datetime as dt
from engine.market import intraday
from engine.market.yahoo import parse_chart

UTC = dt.timezone.utc


def day_bars(mic, day, skip=(), volume=100, with_ohlc=True):
    out = []
    for s in intraday.expected_slot_starts(mic, day):
        if s in skip:
            continue
        c = 100 + len(out) * 0.1
        out.append((s, c - 0.05 if with_ohlc else None, c + 0.2 if with_ohlc else None, c - 0.2 if with_ohlc else None, c, volume, 1))
    return out


def test_two_last_sessions_over_weekend_in_exchange_timezone():
    fri, mon = dt.date(2026, 10, 23), dt.date(2026, 10, 26)
    bars = day_bars('XPAR', dt.date(2026, 10, 22)) + day_bars('XPAR', fri) + day_bars('XPAR', mon)
    v = intraday.build_view('XPAR', bars, dt.datetime(2026, 10, 27, 7, 0, tzinfo=UTC))
    assert [s['date'] for s in v] == ['2026-10-23', '2026-10-26']          # le week-end n'est pas une séance
    assert all(s['complete'] and s['count'] == s['expected'] == 34 for s in v)
    assert v[0]['open_utc'] == '2026-10-23T07:00:00Z' and v[1]['open_utc'] == '2026-10-26T08:00:00Z'   # heure d'été puis heure d'hiver à Paris
    assert 'CE' in v[0]['tz_label'] and 'UTC+2' in v[0]['tz_label'] and 'UTC+1' in v[1]['tz_label']


def test_us_session_uses_new_york_hours_and_dst():
    v = intraday.build_view('XNAS', day_bars('XNAS', dt.date(2026, 10, 27)), dt.datetime(2026, 10, 28, 3, 0, tzinfo=UTC))
    assert v[0]['open_utc'] == '2026-10-27T13:30:00Z' and v[0]['expected'] == 26 and v[0]['complete']
    v = intraday.build_view('XNAS', day_bars('XNAS', dt.date(2026, 11, 3)), dt.datetime(2026, 11, 4, 3, 0, tzinfo=UTC))
    assert v[0]['open_utc'] == '2026-11-03T14:30:00Z'                       # après le 1er novembre : UTC-5


def test_missing_slots_are_reported_never_invented():
    day = dt.date(2026, 10, 27)
    hole = intraday.expected_slot_starts('XETR', day)[10]
    v = intraday.build_view('XETR', day_bars('XETR', day, skip=(hole,)), dt.datetime(2026, 10, 28, 3, 0, tzinfo=UTC))
    s = v[0]
    assert s['count'] == 33 and s['missing'] == [hole.isoformat() + 'Z'] and not s['complete']
    assert len(s['bars']) == 33


def test_session_in_progress_expects_only_elapsed_slots():
    day = dt.date(2026, 10, 27)
    slots = intraday.expected_slot_starts('XETR', day)[:10]
    bars = [(s, 1, 2, 0.5, 1.5, 10, 1) for s in slots]
    now = slots[9] + dt.timedelta(minutes=15, seconds=30)                   # le 10e créneau vient de se terminer
    v = intraday.build_view('XETR', bars, now.replace(tzinfo=UTC))
    assert v[0]['in_progress'] and not v[0]['complete'] and v[0]['missing'] == []


def test_summary_and_incomplete_volume_flag():
    bars = day_bars('XAMS', dt.date(2026, 10, 27))
    bars[3] = bars[3][:5] + (None, 1)
    s = intraday.build_view('XAMS', bars, dt.datetime(2026, 10, 28, 3, 0, tzinfo=UTC))[0]['summary']
    assert not s['volume_complete'] and s['volume'] == 100 * 33
    assert s['high'] > s['low'] and s['ohlc_complete']


def test_parse_chart_ignores_empty_bars_and_reads_meta():
    payload = {'chart': {'result': [{'meta': {'currency': 'EUR', 'exchangeTimezoneName': 'Europe/Berlin', 'tradingPeriods': {'regular': [[{'start': 100, 'end': 200}]]}},
                                     'timestamp': [1000, 1900, 2800], 'indicators': {'quote': [{'open': [1, None, 3], 'high': [2, None, 4], 'low': [0.5, None, 2], 'close': [1.5, None, 3.5], 'volume': [10, None, 30]}]}}]}}
    d = parse_chart(payload)
    assert d['timezone'] == 'Europe/Berlin' and d['periods'] == [(100, 200)]
    assert d['bars'] == [(1000, 1.0, 2.0, 0.5, 1.5, 10), (2800, 3.0, 4.0, 2.0, 3.5, 30)]
    assert parse_chart({}) is None
