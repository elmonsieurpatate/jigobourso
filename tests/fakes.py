"""Faux client Yahoo : rejoue des séries construites par le test, sans réseau."""
import datetime


class FakeYahoo:
    def __init__(self, quotes=None, daily=None, intraday=None, declared_splits=None):
        self.quote_data = quotes or {}      # symbole -> dict Quote
        self.daily = daily or {}            # symbole -> (tz, [(date, close)])
        self.intraday = intraday or {}      # symbole -> (tz, [(datetime_utc, close)])
        self.declared_splits = declared_splits or {}   # symbole -> [(date ISO, parts nouvelles, parts anciennes)]
        self.calls = []

    def quotes(self, symbols):
        self.calls.append(('quote', tuple(symbols)))
        return {s: self.quote_data[s] for s in symbols if s in self.quote_data}

    def spark(self, symbols, range_, interval):
        self.calls.append(('spark', tuple(symbols), range_, interval))
        out = {}
        for s in symbols:
            if interval == '1d' and s in self.daily:
                tz, bars = self.daily[s]
                out[s] = {'currency': 'EUR', 'timezone': tz, 'bars': [(int(datetime.datetime(d.year, d.month, d.day, 12, tzinfo=datetime.timezone.utc).timestamp()), c) for d, c in bars]}
            if interval == '15m' and s in self.intraday:
                tz, bars = self.intraday[s]
                out[s] = {'currency': 'EUR', 'timezone': tz, 'bars': [(int(t.replace(tzinfo=datetime.timezone.utc).timestamp()), c) for t, c in bars]}
        return out

    def splits(self, symbol, range_='2y'):
        self.calls.append(('splits', symbol))
        return list(self.declared_splits.get(symbol.upper(), []))
