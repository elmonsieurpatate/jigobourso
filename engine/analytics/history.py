"""Évolution d'un portefeuille jour par jour, VENTES COMPRISES : valeur, apports nets, résultat cumulé, et valeur de chaque titre.

- Valeur(j)       : Σ quantité détenue × clôture du jour × change du jour (euros). Sans cours connu ou change, la valeur est indisponible (jamais remplacée par un prix d'achat).
- Apports nets(j) : Σ achats (prix × quantité × change de la transaction + frais) − Σ ventes (produit net de frais). C'est l'argent sorti de la poche.
- Résultat(j)     : Valeur − Apports nets = plus-values latentes + plus-values réalisées (identique au « gain » du registre quand les cours coïncident).
Les splits : clôtures et quantités sont exprimées dans les unités d'aujourd'hui (comme les courbes des fiches). Un split déjà saisi à la main par un « achat gratuit »
(prix 0) n'est pas compté deux fois : l'achat gratuit est ignoré et le split appliqué aux quantités. Lecture seule.
"""
import datetime
import math

from .series import prepare_series


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def applied_splits(bars, splits):
    """Splits à appliquer aux quantités : tous ceux dont le ratio est valide. Les courbes (prepare_series) sont dans les unités d'aujourd'hui,
    que le split ait été corrigé par le moteur ou déjà inclus par le fournisseur ; les quantités doivent l'être aussi."""
    return [(d, r) for d, r in splits if r is not None and r > 0 and math.isfinite(r) and r != 1]


def _load(conn, ids, start):
    bars, splits, unit = {}, {}, {}
    if not ids:
        return bars, splits, unit, ({}, {})
    marks = ','.join(['%s'] * len(ids))
    with conn.cursor() as cur:
        cur.execute(f'SELECT listing_id, price_date, close_px, adj_close_px FROM daily_prices WHERE listing_id IN ({marks}) ORDER BY listing_id, price_date', list(ids))
        for r in cur.fetchall():
            bars.setdefault(r['listing_id'], []).append((r['price_date'].isoformat(), float(r['close_px']), None if r['adj_close_px'] is None else float(r['adj_close_px'])))
        cur.execute(f"SELECT listing_id, event_date, ratio FROM corporate_events WHERE listing_id IN ({marks}) AND kind IN ('split','reverse_split')", list(ids))
        for r in cur.fetchall():
            splits.setdefault(r['listing_id'], []).append((r['event_date'].isoformat(), _num(r['ratio'])))
        cur.execute(f'SELECT l.id, COALESCE(p.currency, l.currency) cur, l.symbol, i.name, p.price, p.price_time FROM listings l JOIN instruments i ON i.id=l.instrument_id LEFT JOIN latest_prices p ON p.listing_id=l.id WHERE l.id IN ({marks})', list(ids))
        meta = {r['id']: r for r in cur.fetchall()}
        unit = {k: v['cur'] for k, v in meta.items()}
        curs = sorted({('GBP' if (c or '').upper() in ('GBP', 'GBX') else (c or '').upper()) for c in unit.values()} - {'EUR', ''})
        fx = {}
        if curs:
            cur.execute(f"SELECT currency, rate_date, to_eur FROM fx_rates WHERE currency IN ({','.join(['%s'] * len(curs))}) AND rate_date >= %s ORDER BY currency, rate_date",
                        curs + [start - datetime.timedelta(days=15)])
            for r in cur.fetchall():
                fx.setdefault(r['currency'], []).append((r['rate_date'].isoformat(), float(r['to_eur'])))
    return bars, splits, unit, (fx, meta)


class _Carry:
    """Dernière valeur connue à une date (séries triées)."""
    def __init__(self, pairs):
        self.pairs, self.i, self.last = pairs, 0, None

    def at(self, day):
        while self.i < len(self.pairs) and self.pairs[self.i][0] <= day:
            self.last = self.pairs[self.i][1]
            self.i += 1
        return self.last


def build(transactions, bars, splits, unit, fx, meta, today=None, bars15=None):
    """Calcul pur (testable sans base). transactions : lignes du registre (trade_at, side, quantity, unit_price, fx_to_eur, fees, listing_id, symbol, name, currency)."""
    today = (today or datetime.date.today()).isoformat()
    txs = sorted(transactions, key=lambda t: (str(t['trade_at']), int(t.get('id') or 0)))
    if not txs:
        return {'dates': [], 'value': [], 'net_in': [], 'gain': [], 'purchases': [], 'unpriced': [], 'lines': [], 'trades': [], 'notes': [], 'intraday': {'t': [], 'value': []}}
    notes = []
    series, applied = {}, {}
    for lid in {int(t['listing_id']) for t in txs if t.get('listing_id')}:
        b = bars.get(lid, [])
        ev = sorted(splits.get(lid, []))
        dates, closes, _, _ = prepare_series(b, ev)
        series[lid] = list(zip(dates, closes))
        applied[lid] = applied_splits(b, ev)
    free = {lid: [str(t['trade_at'])[:10] for t in txs if t.get('listing_id') and int(t['listing_id']) == lid and t['side'] == 'buy' and (_num(t['unit_price']) or 0) == 0]
            for lid in applied}
    first = str(txs[0]['trade_at'])[:10]
    calendar = sorted({d for lid in series for d, _ in series[lid] if first <= d <= today} | {str(t['trade_at'])[:10] for t in txs})
    if calendar and calendar[-1] < today and series:
        calendar.append(today)
    # Dernier point : le dernier cours connu (cotation du jour) quand il est plus récent que la dernière clôture, comme la valeur affichée en haut de page.
    for lid in series:
        m = meta.get(lid) or {}
        live, when = _num(m.get('price')), m.get('price_time')
        day_live = when.date().isoformat() if hasattr(when, 'date') else (str(when)[:10] if when else None)
        if live and day_live and (not series[lid] or day_live >= series[lid][-1][0]) and day_live <= today:
            series[lid].append((today, live))
    closes = {lid: _Carry(series[lid]) for lid in series}
    rates = {c: _Carry(v) for c, v in fx.items()}

    def to_eur(lid, day):
        u = (unit.get(lid) or 'EUR')
        if u.upper() == 'EUR':
            return 1.0
        base = 'GBP' if u.upper() in ('GBP', 'GBX') else u.upper()
        r = rates[base].at(day) if base in rates else None
        return None if r is None else r / (100 if u in ('GBp', 'GBX') else 1)

    holdings, net_in, purchases, k = {}, 0.0, 0.0, 0
    lines = {}
    out = {'dates': [], 'value': [], 'net_in': [], 'gain': [], 'purchases': [], 'unpriced': []}
    trades = []
    for day in calendar:
        while k < len(txs) and str(txs[k]['trade_at'])[:10] <= day:
            t = txs[k]; k += 1
            qty, price, fees = _num(t['quantity']) or 0.0, _num(t['unit_price']) or 0.0, _num(t.get('fees')) or 0.0
            rate = _num(t.get('fx_to_eur')) or (1.0 if (t.get('currency') or '').upper() == 'EUR' else None)
            if rate is None:
                notes.append(f"Transaction n° {t.get('id')} sans taux de change : ignorée dans l'évolution.")
                continue
            key = int(t['listing_id']) if t.get('listing_id') else 'S' + str(t['symbol']).upper()
            factor = 1.0
            if isinstance(key, int):
                day0 = str(t['trade_at'])[:10]
                if t['side'] == 'buy' and price == 0 and any(e <= day0 for e, _ in applied.get(key, [])):
                    trades.append({'date': day0, 'side': 'buy', 'symbol': t['symbol'], 'note': 'split saisi à la main'})
                    continue                                     # « achat gratuit » d'un split : déjà compté par la conversion des quantités
                for e, r in applied.get(key, []):
                    if e > day0:
                        factor *= r
            gross = qty * price * rate
            if t['side'] == 'buy':
                holdings[key] = holdings.get(key, 0.0) + qty * factor
                net_in += gross + fees
                purchases += gross + fees
            else:
                holdings[key] = max(0.0, holdings.get(key, 0.0) - qty * factor)
                net_in -= gross - fees
            lines.setdefault(key, {'key': str(key), 'symbol': t['symbol'], 'name': (meta.get(key) or {}).get('name') or t.get('name') or t['symbol'], 'values': [], 'net_in': [], 'purchases': [], '_in': 0.0, '_purchases': 0.0})
            if t['side'] == 'buy':
                lines[key]['_purchases'] += gross + fees
            lines[key]['_in'] += (gross + fees) if t['side'] == 'buy' else -(gross - fees)
            trades.append({'id': t.get('id'), 'key': str(key), 'date': str(t['trade_at'])[:10], 'trade_at': str(t['trade_at']), 'side': t['side'], 'symbol': t['symbol'],
                           'quantity': qty, 'unit_price': price, 'currency': t.get('currency'), 'fees_eur': fees, 'fx_to_eur': rate,
                           'first_buy': t['side'] == 'buy' and not any(x.get('key') == str(key) and x['side'] == 'buy' for x in trades)})
        total, unpriced = 0.0, 0
        for key, line in lines.items():
            q = holdings.get(key, 0.0)
            v = 0.0
            if q > 1e-12:
                c = closes[key].at(day) if isinstance(key, int) and key in closes else None
                f = to_eur(key, day) if c is not None else None
                v = q * c * f if c is not None and f is not None else None
            line['values'].append(None if v is None else round(v, 2))
            line['purchases'].append(round(line['_purchases'], 2))
            line['net_in'].append(round(line['_in'], 2))
            if v is None:
                unpriced += 1
            else:
                total += v
        # titres apparus après le début : leurs valeurs antérieures valent 0
        for line in lines.values():
            if len(line['values']) < len(out['dates']) + 1:
                pad = len(out['dates']) + 1 - len(line['values'])
                line['values'][:0] = [0.0] * pad
                line['net_in'][:0] = [0.0] * pad
                line['purchases'][:0] = [0.0] * pad
        out['dates'].append(day)
        out['value'].append(None if unpriced else round(total, 2))
        out['unpriced'].append(unpriced)
        out['purchases'].append(round(purchases, 2))
        out['net_in'].append(round(net_in, 2))
        out['gain'].append(None if unpriced else round(total - net_in, 2))
    for line in lines.values():
        line.pop('_in', None)
        line.pop('_purchases', None)
        line['gain'] = [None if v is None else round(v - i, 2) for v, i in zip(line['values'], line['net_in'])]      # gain ou perte cumulé du titre (latent + réalisé)
    out['lines'] = sorted(lines.values(), key=lambda l: -max((v for v in l['values'] if v is not None), default=0))
    out['intraday'] = intraday_value(holdings, bars15 or {}, {k: (closes[k].last if k in closes else None) for k in holdings if isinstance(k, int)}, to_eur, today)
    out['market'] = market_history(holdings, bars, splits, unit, {k: {**{'symbol': l['symbol'], 'name': l['name']}, **meta.get(k, {})} for k, l in lines.items()}, today, bars15 or {})
    out['trades'] = trades
    if any(out['unpriced']):
        notes.append('Valorisation indisponible aux dates sans cours ou change : aucune estimation au prix d’achat.')
    out['notes'] = notes
    return out


def market_history(holdings, bars, splits, unit, meta, today, bars15):
    """Observed split-adjusted native prices of CURRENT holdings, independent of acquisition.

    No cash-flow/FX/portfolio return is inferred from this comparison. Missing observations
    stay null; last observations keep their real dates. Intraday is the last stored session,
    never a fabricated replay of holdings or transactions during the session.
    """
    lines, intraday = [], []
    for lid, qty in holdings.items():
        if qty <= 1e-12:
            continue
        m = meta.get(lid, {})
        dates, closes, _, quality = prepare_series(bars.get(lid, []), sorted(splits.get(lid, [])))
        observed = {d: c for d, c in zip(dates, closes) if d <= today}
        when = m.get('price_time')
        day = str(when)[:10] if when else None
        live = _num(m.get('price'))
        if live is not None and live > 0 and day and day <= today and (not observed or day >= max(observed)):
            observed[day] = live
        info = {'key': str(lid), 'symbol': m.get('symbol') or str(lid).removeprefix('S'),
                'name': m.get('name') or str(lid), 'currency': unit.get(lid),
                'break_dates': [dates[i] for i in quality], 'last_date': max(observed) if observed else None}
        lines.append(dict(info, observations=observed))
        intraday.append(dict(info, observations={t: c for t, c in bars15.get(lid, []) if t[:10] <= today}))
    def aligned(items, session=False):
        dates = sorted({d for l in items for d in l['observations']})
        if session and dates:
            dates = [d for d in dates if d[:10] == dates[-1][:10]]
        return {'dates': dates, 'lines': [{**{k: v for k, v in l.items() if k != 'observations'},
                                         'prices': [l['observations'].get(d) for d in dates]} for l in items]}
    return dict(aligned(lines), intraday=aligned(intraday, True))


def intraday_value(holdings, bars15, last_close, to_eur, today):
    """Valeur du portefeuille ACTUEL barre par barre (15 min) sur la dernière journée de cotation connue : quantités d'aujourd'hui,
    chaque titre au dernier prix de 15 min connu (sinon sa dernière clôture), change du jour. Sans barre : rien."""
    held = {k: q for k, q in holdings.items() if q > 1e-12}
    days = sorted({t[:10] for k in held if isinstance(k, int) for t, _ in bars15.get(k, [])})
    if not days:
        return {'t': [], 'value': []}
    day = days[-1]
    slots = sorted({t for k in held if isinstance(k, int) for t, _ in bars15.get(k, []) if t[:10] == day})
    cur = {k: last_close.get(k) for k in held if isinstance(k, int)}
    series = {k: [(t, c) for t, c in bars15.get(k, []) if t[:10] == day] for k in cur}
    idx = {k: 0 for k in cur}
    out = {'t': [], 'value': []}
    for s in slots:
        total, unavailable = 0.0, False
        for k, q in held.items():
            if not isinstance(k, int):
                unavailable = True
                continue
            while idx[k] < len(series[k]) and series[k][idx[k]][0] <= s:
                cur[k] = series[k][idx[k]][1]; idx[k] += 1
            f = to_eur(k, today)
            if cur[k] is None or f is None:
                unavailable = True
            else:
                total += q * cur[k] * f
        out['t'].append(s)
        out['value'].append(None if unavailable else round(total, 2))
    return out


def portfolio_history(conn, request):
    txs = request.get('transactions', [])
    if not txs:
        return build([], {}, {}, {}, {}, {})
    start = datetime.date.fromisoformat(min(str(t['trade_at'])[:10] for t in txs))
    ids = sorted({int(t['listing_id']) for t in txs if t.get('listing_id')})
    bars, splits, unit, (fx, meta) = _load(conn, ids, start)
    bars15 = {}
    if ids:
        with conn.cursor() as cur:
            cur.execute(f"SELECT listing_id, slot_start, close_px FROM intraday_prices WHERE listing_id IN ({','.join(['%s'] * len(ids))}) AND slot_start >= NOW() - INTERVAL 6 DAY ORDER BY listing_id, slot_start", ids)
            for r in cur.fetchall():
                bars15.setdefault(r['listing_id'], []).append((r['slot_start'].isoformat(), float(r['close_px'])))
    return build(txs, bars, splits, unit, fx, meta, bars15=bars15)
