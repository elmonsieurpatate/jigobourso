"""Client Yahoo Finance (bibliothèque standard). Quote (prix, volume moyen) et Spark (séries par lots).

Le transport est injectable : les tests rejouent des réponses enregistrées, sans réseau.
Un 429 lève RateLimited ; l'appelant décide de la pause (jamais de boucle d'attente ici).
"""
import http.cookiejar
import json
import re
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BASE = 'https://query1.finance.yahoo.com'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
QUOTE_FIELDS = 'symbol,regularMarketPrice,regularMarketTime,averageDailyVolume3Month,currency,marketCap,quoteType,netExpenseRatio,averageDailyVolume10Day,averageAnalystRating,netAssets'


class RateLimited(Exception):
    def __init__(self, retry_after=None):
        super().__init__('Yahoo : trop de requêtes (429)')
        self.retry_after = retry_after


class YahooError(Exception):
    pass


class UrllibTransport:
    """Transport réel : cookie de session + crumb pour Quote."""

    def __init__(self, timeout=30, min_interval=0.3):
        self.timeout = timeout
        self.min_interval = min_interval        # pause minimale entre deux appels (politesse, évite les 429)
        self._last = 0.0
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.opener.addheaders = [('User-Agent', UA), ('Accept', 'application/json, text/plain, */*')]
        self.crumb = None

    def _open(self, url):
        try:
            return self.opener.open(url, timeout=self.timeout).read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RateLimited(e.headers.get('Retry-After'))
            if e.code == 404 and 'fc.yahoo.com' in url:
                return ''           # le cookie est posé malgré le 404
            raise YahooError(f'HTTP {e.code}')
        except urllib.error.URLError as e:
            raise YahooError('réseau : ' + str(e.reason))

    def get(self, path, params):
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        if path.endswith('/quote') or '/quoteSummary/' in path:
            if self.crumb is None:
                self._open('https://fc.yahoo.com')
                self.crumb = self._open(BASE + '/v1/test/getcrumb')
                if not self.crumb or '<' in self.crumb:
                    self.crumb = None
                    raise YahooError('crumb Yahoo indisponible')
            params = dict(params, crumb=self.crumb)
        return self._open(BASE + path + '?' + urllib.parse.urlencode(params))


class YahooClient:
    def __init__(self, transport=None):
        self.transport = transport or UrllibTransport()

    def quotes(self, symbols):
        """{symbole: {price, price_time, avg_volume_3m, currency, market_cap, quote_type}}"""
        text = self.transport.get('/v7/finance/quote', {'symbols': ','.join(symbols), 'formatted': 'false', 'fields': QUOTE_FIELDS})
        return parse_quotes(json.loads(text))

    def spark(self, symbols, range_, interval):
        """{symbole: {currency, timezone, bars: [(timestamp_utc, close)]}}"""
        text = self.transport.get('/v7/finance/spark', {'symbols': ','.join(symbols), 'range': range_, 'interval': interval})
        return parse_spark(json.loads(text), symbols)

    def splits(self, symbol, range_='2y'):
        """Splits et regroupements que Yahoo déclare pour ce titre sur la période : voir parse_splits."""
        text = self.transport.get('/v8/finance/chart/' + urllib.parse.quote(symbol, safe=''), {'range': range_, 'interval': '1d', 'events': 'split', 'includePrePost': 'false'})
        return parse_splits(json.loads(text))

    def chart(self, symbol, range_='5d', interval='15m'):
        """Bougies OHLCV d'un seul symbole (utilisé à la consultation d'une fiche) : voir parse_chart."""
        text = self.transport.get('/v8/finance/chart/' + urllib.parse.quote(symbol, safe=''), {'range': range_, 'interval': interval, 'includePrePost': 'false'})
        return parse_chart(json.loads(text))


def parse_splits(payload):
    """Splits déclarés par Yahoo dans la réponse /v8/finance/chart?events=split : [(date ISO de la séance, parts nouvelles, parts anciennes)].
    Ex. un regroupement « 1:10 » donne (date, 1.0, 10.0) : ratio parts nouvelles / anciennes = 0,1. Liste vide si rien de déclaré ou réponse inexploitable."""
    result = (((payload or {}).get('chart') or {}).get('result') or [None])[0]
    if not isinstance(result, dict):
        return []
    meta = result.get('meta') or {}
    tz = meta.get('exchangeTimezoneName') or meta.get('timezone')
    out = []
    for ev in ((result.get('events') or {}).get('splits') or {}).values():
        num, den, ts = _num(ev.get('numerator')), _num(ev.get('denominator')), ev.get('date')
        if num and den and num > 0 and den > 0 and isinstance(ts, int):
            out.append((local_date(ts, tz).isoformat(), num, den))
    return sorted(out)


def parse_chart(payload):
    """Réponse /v8/finance/chart : bougies de 15 min (horodatage UTC, O/H/L/C, volume) et séances régulières déclarées par Yahoo.
    Renvoie None si la réponse ne contient rien d'exploitable. Aucune interpolation : une barre sans cours est ignorée."""
    result = (((payload or {}).get('chart') or {}).get('result') or [None])[0]
    if not isinstance(result, dict):
        return None
    meta = result.get('meta') or {}
    quote = ((result.get('indicators') or {}).get('quote') or [{}])[0]
    cols = [quote.get(k) or [] for k in ('open', 'high', 'low', 'close', 'volume')]
    bars = []
    for i, ts in enumerate(result.get('timestamp') or []):
        vals = [c[i] if i < len(c) else None for c in cols]
        o, h, l, c = (_num(v) for v in vals[:4])
        if c is None or c <= 0 or not isinstance(ts, int):
            continue
        v = vals[4]
        bars.append((ts, o, h, l, c, int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else None))
    periods = []
    for day in ((meta.get('tradingPeriods') or {}).get('regular') or []) if isinstance(meta.get('tradingPeriods'), dict) else []:
        for p in day if isinstance(day, list) else [day]:
            if isinstance(p, dict) and isinstance(p.get('start'), int) and isinstance(p.get('end'), int):
                periods.append((p['start'], p['end']))
    return {'currency': (meta.get('currency') or '')[:3] or None, 'timezone': meta.get('exchangeTimezoneName') or meta.get('timezone'),
            'regular_market_time': meta.get('regularMarketTime'), 'instrument_type': meta.get('instrumentType'), 'bars': bars, 'periods': periods}


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def _fee(v):
    """Frais courants en % ; une valeur absente ou hors de 0-100 reste inconnue."""
    v = _num(v)
    return v if v is not None and 0 <= v <= 100 else None


_RATING = re.compile(r'^[1-5](\.\d)? - [A-Za-z ]{2,24}$')


def _rating(v):
    """Consensus d'analystes tel que Yahoo l'écrit (« 1.8 - Buy ») ; tout autre format reste inconnu."""
    return v if isinstance(v, str) and _RATING.match(v.strip()) else None


def parse_quotes(payload):
    out = {}
    for r in (((payload or {}).get('quoteResponse') or {}).get('result') or []):
        symbol = str(r.get('symbol') or '').upper()
        price = _num(r.get('regularMarketPrice'))
        if not symbol or price is None or price <= 0:
            continue
        t = r.get('regularMarketTime')
        out[symbol] = {'price': price, 'price_time': datetime.fromtimestamp(t, timezone.utc).replace(tzinfo=None) if isinstance(t, (int, float)) else None,
                       'avg_volume_3m': int(r['averageDailyVolume3Month']) if _num(r.get('averageDailyVolume3Month')) is not None else None,
                       'currency': (r.get('currency') or '')[:3] or None,
                       'market_cap': int(r['marketCap']) if _num(r.get('marketCap')) else None, 'quote_type': r.get('quoteType'),
                       'expense_ratio': _fee(r.get('netExpenseRatio')), 'analyst_rating': _rating(r.get('averageAnalystRating')),
                       'net_assets': int(r['netAssets']) if _num(r.get('netAssets')) and r['netAssets'] > 0 else None,
                       'avg_volume_10d': int(r['averageDailyVolume10Day']) if _num(r.get('averageDailyVolume10Day')) is not None else None}
    return out


def parse_spark(payload, requested):
    """Accepte les deux formes de réponse Spark (liste enveloppée ou dictionnaire par symbole)."""
    wanted = {s.upper() for s in requested}
    root = (payload or {}).get('spark') if isinstance(payload, dict) else None
    entries = []
    if isinstance(root, dict) and isinstance(root.get('result'), list):
        for item in root['result']:
            resp = (item.get('response') or [None])[0]
            if isinstance(resp, dict):
                entries.append((str(item.get('symbol') or '').upper(), resp))
    elif isinstance(payload, dict):
        for key, resp in payload.items():
            if isinstance(resp, dict) and ('timestamp' in resp or 'close' in resp):
                entries.append((str(resp.get('symbol') or key).upper(), resp))
    out = {}
    for symbol, resp in entries:
        if symbol not in wanted:
            continue
        meta = resp.get('meta') or {}
        quote = ((resp.get('indicators') or {}).get('quote') or [{}])[0]
        closes = quote.get('close') or resp.get('close') or []
        bars = []
        for ts, close in zip(resp.get('timestamp') or [], closes):
            close = _num(close)
            if close is not None and close > 0 and isinstance(ts, int):
                bars.append((ts, close))
        out[symbol] = {'currency': (meta.get('currency') or '')[:3] or None,
                       'timezone': meta.get('exchangeTimezoneName') or meta.get('timezone'), 'bars': bars}
    return out


def local_date(ts, tzname):
    try:
        zone = ZoneInfo(tzname)
    except Exception:
        zone = timezone.utc
    return datetime.fromtimestamp(ts, zone).date()
