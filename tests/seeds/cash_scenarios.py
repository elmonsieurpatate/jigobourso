"""Six scénarios de validation du moteur de performance v2 (modèle à liquidités). Données déterministes, calcul pur (aucune base).

Utilisés par tests/fast/test_cash_scenarios.py (assertions chiffrées vérifiées à la main) et par scripts/scenarios_performance_v2.py (tableau comparatif).
Tous les cours sont en euros par unité ; le scénario 6 les construit à partir d'un cours en dollars et d'un taux de change journalier."""

from engine.analytics.portfolio import cash_performance as cp

DAYS = ['2026-06-01', '2026-06-02', '2026-06-03', '2026-06-04', '2026-06-05', '2026-06-08']


def ev(day, hh, kind, key=None, qty=None, price=None, fees=0.0, amount=None, i=0):
    e = {'at': f'{day} {hh}', 'kind': kind, 'id': i}
    if key is not None:
        e['key'] = key
    if qty is not None:
        e.update(qty=qty, price=price, fees=fees)
    if amount is not None:
        e['amount'] = amount
    return e


CAPITAL = ev(DAYS[0], '00:00:00', 'initial_capital', amount=1000.0, i=1)


def s1():
    """1 000 € ; achat 200 € (2 × 100) ; vente 250 € (2 × 125) ; plus aucune position."""
    return dict(
        title='1. Virtuel 1 000 €, achat 200 €, vente 250 €',
        closes={'A': [100, 100, 125, 125, 125, 125]},
        events=[CAPITAL, ev(DAYS[1], '12:00:00', 'buy', 'A', 2, 100, i=2), ev(DAYS[2], '12:00:00', 'sell', 'A', 2, 125, i=3)],
    )


def s2():
    """Scénario 1 + dépôt de 500 € puis retrait de 100 € : les mouvements de capital ne sont ni gain ni perte."""
    s = s1()
    s['title'] = '2. Scénario 1 + dépôt 500 € + retrait 100 €'
    s['events'] = s['events'] + [ev(DAYS[3], '12:00:00', 'deposit', amount=500.0, i=4), ev(DAYS[4], '12:00:00', 'withdrawal', amount=100.0, i=5)]
    return s


def s3():
    """Achats et ventes successifs, liquidités réinvesties (deux titres)."""
    return dict(
        title='3. Achats/ventes successifs, réinvestissement',
        closes={'A': [100, 100, 110, 105, 108, 110], 'B': [50, 50, 50, 55, 56, 56]},
        events=[
            CAPITAL,
            ev(DAYS[1], '10:00:00', 'buy', 'A', 5, 100, i=2),  # 500 €
            ev(DAYS[2], '10:00:00', 'sell', 'A', 5, 110, i=3),  # +550 € -> 1 050 €
            ev(DAYS[2], '14:00:00', 'buy', 'B', 10, 50, i=4),  # 500 € de B avec le produit de la vente
            ev(DAYS[3], '10:00:00', 'buy', 'A', 4, 105, i=5),  # 420 € : A est racheté
            ev(DAYS[4], '10:00:00', 'sell', 'B', 10, 56, i=6),  # B soldé : +560 €
        ],
    )


def s4():
    """Gain réalisé conservé après vente complète : A est soldé à 130 ; il retombe ensuite à 80 sans effet sur le portefeuille."""
    return dict(
        title='4. Vente complète : gain réalisé conservé',
        closes={'A': [100, 100, 130, 100, 90, 80]},
        events=[CAPITAL, ev(DAYS[1], '12:00:00', 'buy', 'A', 10, 100, i=2), ev(DAYS[2], '12:00:00', 'sell', 'A', 10, 130, i=3)],
    )


def s5():
    """Contributions par titre : trois titres de poids et de résultats différents + liquidités restantes."""
    return dict(
        title='5. Contributions par titre et liquidités',
        closes={'A': [100, 100, 110, 121, 121, 121], 'B': [50, 50, 50, 45, 45, 45], 'C': [20, 20, 20, 20, 21, 22]},
        events=[
            CAPITAL,
            ev(DAYS[1], '12:00:00', 'buy', 'A', 4, 100, i=2),  # 400 €
            ev(DAYS[1], '12:05:00', 'buy', 'B', 4, 50, i=3),  # 200 €
            ev(DAYS[1], '12:10:00', 'buy', 'C', 10, 20, i=4),  # 200 € ; 200 € restent en liquidités
        ],
    )


USD_TO_EUR = [0.90, 0.90, 0.95, 0.95, 0.96, 0.96]
USD_PX = [100, 100, 110, 110, 110, 110]


def s6():
    """Titre en dollars : 10 × 100 $ achetés à 0,90 ; le cours monte à 110 $ et le dollar de 0,90 à 0,95 ; vente à 110 $ au change de 0,95."""
    closes = {'U': [p * r for p, r in zip(USD_PX, USD_TO_EUR)]}
    return dict(
        title='6. Titre en dollars, change 0,90 → 0,95',
        closes=closes,
        events=[
            CAPITAL,
            ev(DAYS[1], '12:00:00', 'buy', 'U', 10, 100 * 0.90, i=2),  # 900 €
            ev(DAYS[3], '12:00:00', 'sell', 'U', 10, 110 * 0.95, i=3),  # 1 045 €
        ],
    )


SCENARIOS = [s1, s2, s3, s4, s5, s6]


def run(build):
    s = build()
    return s, cp.analyse(DAYS, s['closes'], s['events'])


def row(build):
    """Ligne du tableau comparatif d'un scénario."""
    s, r = run(build)
    ev_ = s['events']
    cap = sum(e['amount'] for e in ev_ if e['kind'] == 'initial_capital')
    dep = sum(e['amount'] for e in ev_ if e['kind'] == 'deposit')
    wd = sum(e['amount'] for e in ev_ if e['kind'] == 'withdrawal')
    pos = {k: p for k, p in r['positions'].items() if p['status'] == 'open'}
    last = lambda seq: seq[-1]  # noqa: E731
    return {
        'title': s['title'],
        'capital': cap,
        'deposits': dep,
        'withdrawals': wd,
        'net_contributions': last(r['net_contributions']),
        'cash': last(r['cash']),
        'securities': last(r['securities']),
        'open': {k: p['quantity'] for k, p in pos.items()},
        'value': last(r['value']),
        'gain': last(r['gain']),
        'realized': last(r['realized']),
        'latent': last(r['latent']),
        'twr': {k: last(r['twr'][k]) for k in ('low', 'central', 'high')},
        'estimated_days': sum(1 for x in r['estimated'] if x),
        'contributions': {str(k): v[-1] for k, v in r['contributions'].items()},
        'checks': r['checks'],
    }
