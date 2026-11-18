"""Comparatif LECTURE SEULE ancien moteur (Dietz quotidien chaîné) / nouveau moteur (TWR avec liquidités) d'un portefeuille.

Usage : PYTHONPATH=. python scripts/compare_performance_v2.py <portfolio_id> [--symbol GIBO] [--json]
Ne fait que des SELECT (transactions, mouvements de liquidités, cours). N'écrit rien, n'affiche rien dans l'application."""

import argparse
import json
import sys

from engine.analytics.series import cash_history, history
from engine.shared.db import connect


def load(conn, pid):
    with conn.cursor() as c:
        try:
            c.execute('SELECT id, name, cash_model, cash_from FROM portfolios WHERE id=%s', (pid,))
            pf = c.fetchone()
        except Exception:  # base sans le modèle de liquidités : portefeuille « ancien modèle »
            c.execute('SELECT id, name FROM portfolios WHERE id=%s', (pid,))
            pf = {**c.fetchone(), 'cash_model': 'legacy', 'cash_from': None}
        c.execute(
            'SELECT id, symbol, name, listing_id, side, quantity, unit_price, currency, fx_to_eur, fees, trade_at FROM portfolio_transactions WHERE portfolio_id=%s ORDER BY trade_at, id', (pid,)
        )
        txs = c.fetchall()
        try:
            c.execute('SELECT id, kind, amount_net, currency, fx_to_eur, listing_id, occurred_at FROM portfolio_cash_movements WHERE portfolio_id=%s ORDER BY occurred_at, id', (pid,))
            mov = c.fetchall()
        except Exception:
            mov = []  # base sans le modèle de liquidités (phase 1 non migrée)
    for t in txs:
        for k in ('quantity', 'unit_price', 'fx_to_eur', 'fees'):
            t[k] = float(t[k]) if t[k] is not None else None
        t['trade_at'] = str(t['trade_at'])
    for m in mov:
        m['amount_net'], m['fx_to_eur'], m['occurred_at'] = float(m['amount_net']), float(m['fx_to_eur']), str(m['occurred_at'])
    return pf, txs, mov


def last(seq):
    return next((x for x in reversed(seq) if x is not None), None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('portfolio_id', type=int)
    ap.add_argument('--symbol')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    conn = connect()
    pf, txs, mov = load(conn, a.portfolio_id)
    old = history.portfolio_history(conn, {'transactions': txs})
    mode = 'cash' if pf['cash_model'] == 'cash' else 'legacy_equivalent'
    new = cash_history.portfolio_cash_performance(conn, {'transactions': txs, 'movements': mov, 'mode': mode, 'cash_from': str(pf['cash_from']) if pf.get('cash_from') else None})
    legacy = new if mode == 'legacy_equivalent' else cash_history.portfolio_cash_performance(conn, {'transactions': txs, 'movements': [], 'mode': 'legacy_equivalent'})
    old_idx = last(old['performance']['index'])
    res = {
        'portfolio': pf['name'],
        'mode': mode,
        'old': {'dietz_index': old_idx, 'dietz_pct': None if old_idx is None else (old_idx - 1) * 100, 'value': last(old['value']), 'gain': last(old['gain']), 'net_in': last(old['net_in'])},
        'new': {
            'twr_pct': {k: None if last(new['twr'][k]) is None else last(new['twr'][k]) * 100 for k in ('low', 'central', 'high')},
            'mwr_period_pct': None if not new['mwr'] or new['mwr']['period'] is None else new['mwr']['period'] * 100,
            'value': last(new['value']),
            'cash': last(new['cash']),
            'gain': last(new['gain']),
            'realized': last(new['realized']),
            'latent': last(new['latent']),
            'dividends': last(new['dividends']),
            'fees': last(new['fees']),
            'open_positions_twr_pct': None if last(new['open_positions_twr']) is None else last(new['open_positions_twr']) * 100,
            'estimated_days': sum(1 for x in new['estimated'] if x),
            'checks': new['checks'],
        },
        'legacy_equivalent_twr_pct': None if last(legacy['twr']['central']) is None else last(legacy['twr']['central']) * 100,
        'positions': {
            str(k): {f: p[f] for f in ('name', 'status', 'first_day', 'last_day', 'twr', 'realized', 'latent', 'dividends', 'fees', 'contribution')} | {'gain': last(p['gain'])}
            for k, p in new['positions'].items()
        },
        'daily': [
            {'day': d, 'old_factor': of, 'new_central': nc, 'new_low': nl, 'new_high': nh, 'estimated': es, 'value': v}
            for d, of, nc, nl, nh, es, v in zip(
                new['days'], _align(old, new['days'], old['performance']['factors']), new['factors']['central'], new['factors']['low'], new['factors']['high'], new['estimated'], new['value']
            )
        ],
        'notes': new.get('notes', []),
    }
    if a.symbol:
        res['symbol_days'] = [x for x in res['daily'] if x['estimated'] or x['old_factor'] != 1.0 or x['new_central'] != 1.0][:50]
    print(json.dumps(res, indent=2, default=str, ensure_ascii=False) if a.json else summary(res))


def _align(old, days, factors):
    by = dict(zip(old['dates'], factors))
    return [by.get(d) for d in days]


def summary(r):
    o, n = r['old'], r['new']
    pct = lambda x: '—' if x is None else f'{x:+.2f} %'  # noqa: E731
    eur = lambda x: '—' if x is None else f'{x:,.2f} €'  # noqa: E731
    out = [f"Portefeuille « {r['portfolio']} » (mode {r['mode']})", '']
    out.append(f"Ancien moteur : Dietz chaîné {pct(o['dietz_pct'])} · valeur {eur(o['value'])} · gain {eur(o['gain'])} · apports nets {eur(o['net_in'])}")
    t = n['twr_pct']
    out.append(f"Nouveau moteur : TWR {pct(t['central'])} (intervalle {pct(t['low'])} à {pct(t['high'])}, {n['estimated_days']} jours estimés) · MWR période {pct(n['mwr_period_pct'])}")
    out.append(
        f"  gain {eur(n['gain'])} = réalisé {eur(n['realized'])} + latent {eur(n['latent'])} + dividendes {eur(n['dividends'])} − frais de compte {eur(n['fees'])} · liquidités {eur(n['cash'])}"
    )
    out.append(f"  titres ouverts seuls {pct(n['open_positions_twr_pct'])} · contrôles {n['checks']}")
    out.append('')
    for k, p in r['positions'].items():
        out.append(
            f"  {p['name'] or k:<28} {p['status']:<7} {p['first_day']}→{p['last_day']} rendement {pct(None if p['twr'] is None else p['twr'] * 100)} gain {eur(p['gain'])} (réalisé {eur(p['realized'])}, latent {eur(p['latent'])}) contribution {pct(None if p['contribution'] is None else p['contribution'] * 100)}"
        )
    out += [''] + r['notes']
    return '\n'.join(out)


if __name__ == '__main__':
    sys.exit(main())
