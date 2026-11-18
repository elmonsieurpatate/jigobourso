"""Adaptateur du moteur de performance v2 (portfolio/cash_performance.py) : transforme transactions, mouvements de liquidités et séries de cours en entrées du calcul pur.

EN PARALLÈLE de history.build (ancien moteur, inchangé, toujours celui qui est affiché). Lecture seule.
Modes : 'legacy_equivalent' = ancien modèle (chaque achat financé par un apport simultané, chaque vente retirée) pour comparer à méthode de flux égale ;
        'cash'              = modèle à liquidités (mouvements réels ; transactions antérieures à cash_from : apports/retraits synthétiques, signalés).
Les quantités et prix suivent les splits comme history.build (valeur d'une transaction inchangée : quantité × facteur, prix ÷ facteur)."""

import datetime

from . import history
from ..portfolio import cash_performance as cp
from ..shared.numbers import finite
from ...shared.units import split_unit


def build(transactions, movements, bars, splits, unit, fx, meta, today=None, mode='legacy_equivalent', cash_from=None):
    today = (today or datetime.date.today()).isoformat()
    txs = sorted(transactions, key=lambda t: (str(t['trade_at']), int(t.get('id') or 0)))
    if not txs and not movements:
        return {'method': 'twr_cash_v2', 'days': [], 'notes': []}
    series, applied = history._split_adjusted_series(txs, bars, splits)
    first = min([str(t['trade_at'])[:10] for t in txs] + [str(m['occurred_at'])[:10] for m in movements])
    calendar = sorted({d for lid in series for d, _ in series[lid] if first <= d <= today} | {str(t['trade_at'])[:10] for t in txs} | {str(m['occurred_at'])[:10] for m in movements})
    if calendar and calendar[-1] < today and series:
        calendar.append(today)
    history._append_live_quotes(series, meta, today)
    carry = {lid: history._Carry(series[lid]) for lid in series}
    rates = {c: history._Carry(v) for c, v in fx.items()}

    def to_eur(lid, day):
        u = unit.get(lid) or 'EUR'
        if u.upper() == 'EUR':
            return 1.0
        base, divisor = split_unit(u)
        r = rates[base].at(day) if base in rates else None
        return None if r is None else r / divisor

    closes = {lid: [] for lid in series}
    for day in calendar:
        for lid in series:
            c = carry[lid].at(day)
            f = to_eur(lid, day) if c is not None else None
            closes[lid].append(None if c is None or f is None else c * f)

    notes, events, names = [], [], {}
    for t in txs:
        qty, price, fees = finite(t['quantity']) or 0.0, finite(t['unit_price']) or 0.0, finite(t.get('fees')) or 0.0
        rate = finite(t.get('fx_to_eur')) or (1.0 if (t.get('currency') or '').upper() == 'EUR' else None)
        if rate is None:
            notes.append(f"Transaction n° {t.get('id')} sans taux de change : ignorée.")
            continue
        key = int(t['listing_id']) if t.get('listing_id') else 'S' + str(t['symbol']).upper()
        factor, day0 = 1.0, str(t['trade_at'])[:10]
        if isinstance(key, int):
            if t['side'] == 'buy' and price == 0 and any(e <= day0 for e, _ in applied.get(key, [])):
                continue  # « achat gratuit » d'un split, déjà compté par la conversion des quantités
            for e, r in applied.get(key, []):
                if e > day0:
                    factor *= r
        if key not in closes:
            closes[key] = [None] * len(calendar)
        names[key] = (meta.get(key) or {}).get('name') or t.get('name') or t['symbol']
        events.append({'at': str(t['trade_at']), 'kind': t['side'], 'key': key, 'qty': qty * factor, 'price': price * rate / factor, 'fees': fees, 'id': t.get('id'), 'symbol': t['symbol']})
    base_events = list(events)
    legacy_from = None if mode == 'legacy_equivalent' else (cash_from or '9999')
    if mode == 'legacy_equivalent':
        events = cp.legacy_equivalent_events(events)
    else:
        synthetic = cp.legacy_equivalent_events([e for e in events if str(e['at']) < str(legacy_from)])
        events = [e for e in events if str(e['at']) >= str(legacy_from)] + [e for e in synthetic if e.get('synthetic')]
        for m in movements:
            amount = float(m['amount_net']) * float(m['fx_to_eur'])
            events.append({'at': str(m['occurred_at']), 'kind': m['kind'], 'amount': amount, 'key': int(m['listing_id']) if m.get('listing_id') else None, 'id': m.get('id')})
        if synthetic:
            notes.append('Transactions antérieures à la date de départ des liquidités : apports et retraits synthétiques (ancien modèle).')
    result = cp.analyse(calendar, closes, events, names)
    divs = [
        {'at': str(m['occurred_at']), 'kind': 'dividend', 'amount': float(m['amount_net']) * float(m['fx_to_eur']), 'key': int(m['listing_id']), 'id': m.get('id')}
        for m in movements
        if m['kind'] == 'dividend' and m.get('listing_id')
    ]
    sleeve_events, open_keys = cp.open_sleeve_events(base_events + divs)
    result['sleeve'] = cp.analyse(calendar, {k: closes[k] for k in open_keys}, sleeve_events, names) if open_keys else None
    result['notes'] = notes
    result['mode'] = mode
    result['symbols'] = {str(k): next((t['symbol'] for t in txs if (int(t['listing_id']) if t.get('listing_id') else 'S' + str(t['symbol']).upper()) == k), None) for k in result['positions']}
    result['summary'] = _summary(movements)
    return result


def _summary(movements):
    """Mouvements d'argent réels en euros (capital initial, dépôts, retraits, dividendes, frais de compte)."""
    totals = {'initial_capital': 0.0, 'deposit': 0.0, 'withdrawal': 0.0, 'dividend': 0.0, 'fee': 0.0}
    for m in movements:
        totals[m['kind']] = totals.get(m['kind'], 0.0) + float(m['amount_net']) * float(m['fx_to_eur'])
    return totals


def _chart(result):
    """Séries du graphique unique, par vue : « full » (portefeuille complet, liquidités comprises) et « open » (sous-portefeuille des titres encore détenus)."""
    hv, pos, sl = result['holding_value'], result['positions'], result.get('sleeve')
    full = {
        **{k: result[k] for k in ('value', 'cash', 'securities', 'gain', 'realized', 'latent', 'estimated')},
        'twr': result['twr'],
        'fees_contribution': result['contributions'].get('__fees__'),
        'holdings': {str(k): {'value': hv[k], 'gain': p['gain'], 'contribution': p['contribution_series'], 'twr': p['twr_series']} for k, p in pos.items()},
    }
    open_view = None
    if sl:
        sp = sl['positions']
        open_view = {
            'keys': [str(k) for k in sp],
            **{k: sl[k] for k in ('value', 'gain', 'realized', 'latent', 'estimated')},
            'twr': sl['twr'],
            'holdings': {str(k): {'value': sl['holding_value'][k], 'gain': p['gain'], 'twr': p['twr_series']} for k, p in sp.items()},
            'checks': sl['checks'],
        }
    return {'days': result['days'], 'full': full, 'open': open_view}


def compact(result):
    """Charge utile de l'interface : synthèse par titre, et séries par vue regroupées dans « chart »."""
    out = {k: v for k, v in result.items() if k not in ('holding_value', 'sleeve', 'contributions', 'open_positions_twr')}
    out['chart'] = _chart(result)
    out['trades'] = [dict(t, key=str(t['key']), symbol=result['symbols'].get(str(t['key']))) for t in result['trades']]
    out['positions'] = {
        k: {f: v for f, v in p.items() if f not in ('twr_series', 'contribution_series', 'gain')} | {'gain_total': next((g for g in reversed(p['gain']) if g is not None), None)}
        for k, p in result['positions'].items()
    }
    return out


def portfolio_cash_performance(conn, request):
    txs = request.get('transactions', [])
    movements = request.get('movements', [])
    ids = sorted({int(t['listing_id']) for t in txs if t.get('listing_id')})
    shape = compact if request.get('compact') else (lambda r: r)
    if not ids:
        return shape(build(txs, movements, {}, {}, {}, {}, {}, mode=request.get('mode', 'legacy_equivalent'), cash_from=request.get('cash_from')))
    starts = [str(t['trade_at'])[:10] for t in txs] + [str(m['occurred_at'])[:10] for m in movements]
    bars, splits, unit, (fx, meta) = history._load(conn, ids, datetime.date.fromisoformat(min(starts)))
    return shape(build(txs, movements, bars, splits, unit, fx, meta, mode=request.get('mode', 'legacy_equivalent'), cash_from=request.get('cash_from')))
