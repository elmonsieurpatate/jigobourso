"""Performance d'un portefeuille avec liquidités : moteur « v2 », calculé EN PARALLÈLE de l'ancien (performance.linked). Rien n'est affiché à partir d'ici sans validation.

Calcul pur : aucune base, aucun réseau. Entrées : jours de valorisation, cours de clôture en EUR par unité (ajustés des splits), événements (achats, ventes, dépôts,
retraits, dividendes, frais). Toutes les formules sont documentées ici et vérifiées par tests/fast/test_cash_performance.py.

DISTINCTIONS FONDAMENTALES
  flux EXTERNES  : capital initial, dépôt, retrait. Seuls à couper la chaîne du TWR. Jamais un gain ni une perte.
  opérations INTERNES : achat, vente (cash <-> titres), dividende (gain), frais (perte). Elles ne sont jamais des flux : une vente garde son produit dans les liquidités.
  gain en euros  : variation de valeur qui n'est pas un flux externe (somme exacte, aucune hypothèse).
  rendement en % : TWR (chaîne des rendements quotidiens). Jamais « gain / achats » ni « gain / capital investi ».

VALEUR ET GAIN
  V(t) = liquidités(t) + somme(quantité × cours EUR)
  gain total(t) = V(t) − apports nets(t)   avec apports nets = capital + dépôts − retraits
              = réalisé (PMP) + latent (positions ouvertes) + dividendes − frais de compte           [identité vérifiée à chaque jour]
  Décomposition exacte d'une journée, par titre k :
     gain_k = q_fin·c_fin − q_début·c_veille − (achats bruts − ventes brutes)  + dividendes_k − frais_k
     somme_k(gain_k) − frais de compte = V_fin − V_début − flux externes du jour                     [identité vérifiée à chaque jour]

TWR (rendement pondéré par le temps)
  facteur du jour = produit, sur les sous-périodes coupées aux flux externes, de V(avant flux) / V(après le flux précédent) ; TWR = produit des facteurs − 1.
  Un jour SANS flux externe : facteur = V_fin / V_début, EXACT (les achats et ventes internes ne changent pas la valeur, sauf frais).
  Un jour AVEC flux externe : l'heure du flux par rapport aux cours du jour est inconnue (les transactions n'ont qu'une heure supposée).
  Valeur d'un titre à l'instant d'un flux : points connus = clôture de la veille (00:00), prix d'exécution de chaque transaction du titre, clôture du jour (fin de journée).
     centrale : interpolation linéaire entre ces points ; bornes : le titre garde le dernier point connu (« prev ») ou saute déjà au suivant (« next »).
  Le résultat est donc donné avec un intervalle [bas, haut] et un indicateur « estimé » par jour ; il ne devient exact que les jours sans flux externe.

CONTRIBUTIONS (somme exacte = TWR)
  gain_k du jour ÷ base effective du jour (= gain total du jour ÷ (facteur − 1)), puis lissage de Cariño :  C_k(t) = somme_i c_k,i · K_i / K_t,
  K_i = ln(1+r_i)/r_i , K_t = ln(1+R_t)/R_t  (r_i rendement du jour, R_t TWR cumulé).  Somme_k C_k(t) = R_t exactement. Les titres vendus gardent leur contribution.

RENDEMENT D'UN TITRE (« sleeve ») : chaîne des rendements journaliers gain_k / (q_début·c_veille + achats du jour au prix d'exécution), net de frais, dividendes compris.
  Pour un titre seul, c'est EXACT (les achats et ventes se font au prix d'exécution, sa valeur à cet instant est connue).
MWR : taux interne de rendement des flux externes et de la valeur finale, ramené à la période (jamais annualisé sous un an).
"""

import datetime as dt
import math

EPS = 1e-9
# Ordre à horodatage identique : apports d'abord, retraits en dernier ; achats et ventes dans l'ordre du registre (id), car une vente doit suivre l'achat qui la précède
# (la règle « vente avant achat » du solde de liquidités ne concerne que la validation du solde, pas les quantités de titres).
PRIORITY = {'initial_capital': 0, 'deposit': 1, 'dividend': 1, 'sell': 2, 'buy': 2, 'fee': 4, 'withdrawal': 5}
EXTERNAL = ('initial_capital', 'deposit', 'withdrawal')
DAY_SECONDS = 86400.0


def _when(s):
    return s if isinstance(s, dt.datetime) else dt.datetime.fromisoformat(str(s).replace('T', ' '))


def legacy_equivalent_events(events):
    """Hypothèse « ancien modèle » : pas de liquidités, chaque achat est financé par un apport simultané et chaque vente suivie d'un retrait de son produit net.
    Sert uniquement à comparer avec l'ancien moteur ; les liquidités restent nulles."""
    out = list(events)
    for e in events:
        if e['kind'] == 'buy':
            out.append({'at': e['at'], 'kind': 'deposit', 'amount': e['qty'] * e['price'] + e.get('fees', 0.0), 'id': e.get('id'), 'synthetic': True})
        elif e['kind'] == 'sell':
            out.append({'at': e['at'], 'kind': 'withdrawal', 'amount': e['qty'] * e['price'] - e.get('fees', 0.0), 'id': e.get('id'), 'synthetic': True})
    return out


def open_sleeve_events(events):
    """Événements du sous-portefeuille des titres ENCORE DÉTENUS : leurs achats et ventes (financés par apports et retraits synthétiques, comme l'ancien modèle),
    leurs dividendes (encaissés puis retirés). Titres entièrement vendus, liquidités et frais de compte : exclus. Rétrospectif : un titre vendu demain disparaît."""
    net = {}
    for e in events:
        if e['kind'] in ('buy', 'sell') and e.get('key') is not None:
            net[e['key']] = net.get(e['key'], 0.0) + (float(e['qty']) if e['kind'] == 'buy' else -float(e['qty']))
    open_keys = {k for k, v in net.items() if v > EPS}
    sel = [e for e in events if e.get('key') in open_keys and e['kind'] in ('buy', 'sell', 'dividend')]
    out = legacy_equivalent_events(sel)
    for e in sel:
        if e['kind'] == 'dividend':
            out.append({'at': e['at'], 'kind': 'withdrawal', 'amount': float(e['amount']), 'id': e.get('id'), 'synthetic': True})
    return out, sorted(open_keys, key=str)


def _price_at(anchors, t, mode):
    """Prix d'un titre à l'instant t (secondes depuis 00:00) selon les points connus ; mode : linear | prev | next."""
    if not anchors:
        return None
    before = after = None
    for a in anchors:
        if a[0] <= t:
            before = a
        if a[0] >= t and after is None:
            after = a
    if before is not None and after is not None and before[0] == after[0]:
        return before[1]
    if mode == 'prev':
        return (before or after)[1]
    if mode == 'next':
        return (after or before)[1]
    if before is None:
        return after[1]
    if after is None:
        return before[1]
    return before[1] + (after[1] - before[1]) * (t - before[0]) / (after[0] - before[0])


def _xirr_period(flows, final_value, start, end):
    """Rendement g de la période entière (non annualisé) tel que  somme F_k · (1+g)^(1−u_k) = V_fin,  u_k = fraction de la période écoulée au flux k."""
    span = (end - start).total_seconds()
    if span <= 0 or not flows:
        return None
    fr = [((t - start).total_seconds() / span, f) for t, f in flows]

    def npv(g):
        return sum(f * (1.0 + g) ** (1.0 - u) for u, f in fr) - final_value

    lo, hi = -0.999999, 1e6
    flo, fhi = npv(lo), npv(hi)
    if not (math.isfinite(flo) and math.isfinite(fhi)) or flo * fhi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        fm = npv(mid)
        if flo * fm <= 0:
            hi = mid
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


class _Book:
    """Registre en cours : liquidités, quantités, prix de revient moyen pondéré (PMP), réalisé, dividendes, frais."""

    def __init__(self, keys):
        self.cash = 0.0
        self.q = {k: 0.0 for k in keys}
        self.cost = {k: 0.0 for k in keys}
        self.realized = {k: 0.0 for k in keys}
        self.dividends = {k: 0.0 for k in keys}
        self.fees_tx = {k: 0.0 for k in keys}
        self.fees_acct = 0.0
        self.net_contrib = 0.0
        self.flows_all = []
        self.trades = []  # opérations de titres : prix, frais et, pour une vente, gain réalisé au PMP

    def apply(self, e, t, day, snaps, anchors):
        """Applique un événement ; t = secondes depuis 00:00 du jour ; day cumule les montants du jour."""
        kind = e['kind']
        if kind in EXTERNAL:
            amount = float(e['amount'])
            flow = amount if kind != 'withdrawal' else -amount
            snaps.append((t, self.cash, {k: v for k, v in self.q.items() if v > EPS}, flow))
            self.cash += flow
            day['flow'] += flow
            self.net_contrib += flow
            self.flows_all.append((_when(e['at']), flow))
        elif kind in ('buy', 'sell'):
            k, qty, price, fees = e['key'], float(e['qty']), float(e['price']), float(e.get('fees') or 0.0)
            anchors[k].append((t, price))
            gross = qty * price
            trade = {'id': e.get('id'), 'at': str(e['at']), 'kind': kind, 'key': k, 'qty': qty, 'price': price, 'fees': fees, 'realized': None}
            self.trades.append(trade)
            if kind == 'buy':
                self.cash -= gross + fees
                self.q[k] += qty
                self.cost[k] += gross + fees
                day['buys_gross'][k] += gross
                day['buys_base'][k] += gross
            else:
                before = self.q[k]
                out_cost = (self.cost[k] / before if before > EPS else 0.0) * qty
                self.cash += gross - fees
                self.q[k] = before - qty
                self.cost[k] -= out_cost
                self.realized[k] += (gross - fees) - out_cost
                trade['realized'] = (gross - fees) - out_cost
                day['sells_gross'][k] += gross
                if self.q[k] <= EPS:
                    self.q[k], self.cost[k] = 0.0, 0.0
            self.fees_tx[k] += fees
            day['fee'][k] += fees
        elif kind == 'dividend':
            if e.get('key') is None:
                raise ValueError('dividende sans titre')
            amount = float(e['amount'])
            self.cash += amount
            self.dividends[e['key']] += amount
            day['div'][e['key']] += amount
        elif kind == 'fee':
            amount = float(e['amount'])
            self.cash -= amount
            self.fees_acct += amount
            day['acct'] += amount
        else:
            raise ValueError('type d’événement inconnu : ' + str(kind))


def _day_factors(invalid, started, v_start, v_end, snaps, anchors):
    """Facteur du jour (central, bas, haut) : produit des sous-périodes coupées aux flux externes ; 3 hypothèses de valeur des titres à l'heure du flux."""
    if invalid or not started:
        fac = {m: (None if invalid else 1.0) for m in ('linear', 'prev', 'next')}
    else:
        fac = {}
        for mode in ('linear', 'prev', 'next'):
            prod, plus, bad = 1.0, v_start, False
            for t, c0, qb, flow in snaps:
                vals = [_price_at(anchors[k], t, mode) for k in qb]
                if any(v is None for v in vals):
                    bad = True
                    break
                vm = c0 + sum(qb[k] * v for k, v in zip(qb, vals))
                if plus > EPS:
                    prod *= vm / plus
                plus = vm + flow
            if not bad and plus > EPS:
                prod *= v_end / plus
            fac[mode] = None if bad else prod
    valid_f = [f for f in fac.values() if f is not None]
    central = fac.get('linear')
    if central is None or any(f is None for f in fac.values()) or not all(math.isfinite(f) and f >= 0 for f in valid_f):
        return None, None, None
    return central, min(valid_f), max(valid_f)


def _contributions(keys, factors, day_gain, day_base, twr_central):
    """Contributions de Cariño : somme exacte = TWR central à chaque jour (titres, y compris vendus, et frais de compte)."""
    contrib = {k: [] for k in list(keys) + ['__fees__']}
    run = {k: 0.0 for k in contrib}
    ok = True
    for i in range(len(factors)):
        if factors[i] is None or day_base[i] is None or not ok or twr_central[i] is None:
            ok = False
            for k in contrib:
                contrib[k].append(None)
            continue
        r_i = factors[i] - 1.0
        k_i = math.log1p(r_i) / r_i if abs(r_i) > 1e-12 else 1.0
        for k in contrib:
            run[k] += ((day_gain[k][i] or 0.0) / day_base[i]) * k_i
        R = twr_central[i]
        K = math.log1p(R) / R if abs(R) > 1e-12 else 1.0
        for k in contrib:
            contrib[k].append(run[k] / K)
    return contrib


def _positions(keys, days, sleeve_ret, day_gain, book, closes, names, contrib):
    """Synthèse par titre : rendement (chaîne des rendements journaliers du titre), réalisé, latent, dividendes, frais, gain cumulé, contribution."""
    positions = {}
    for k in keys:
        idx, growth, first, last = [], 1.0, None, None
        for i, rr in enumerate(sleeve_ret[k]):
            if rr is not None:
                growth *= 1.0 + rr
                first = first or days[i]
                last = days[i]
            idx.append(growth - 1.0 if first else None)
        held = book.q[k] > EPS
        run_g, gain = 0.0, []
        for g in day_gain[k]:
            run_g += g if g is not None else 0.0
            gain.append(None if g is None else run_g)
        positions[k] = {
            'key': k,
            'name': names.get(k),
            'status': 'open' if held else 'closed',
            'first_day': first,
            'last_day': last,
            'twr': (growth - 1.0) if first else None,  # exact pour un titre : prix d'exécution connus
            'twr_series': idx,
            'realized': book.realized[k],
            'latent': ((book.q[k] * closes[k][-1] - book.cost[k]) if closes[k][-1] is not None else None) if held else 0.0,
            'dividends': book.dividends[k],
            'fees': book.fees_tx[k],
            'quantity': book.q[k],
            'gain': gain,
            'contribution': contrib[k][-1] if contrib[k] else None,
            'contribution_series': contrib[k],
        }
    return positions


def _open_series(pnl, base):
    """Rendement des titres actuellement ouverts, sans liquidités : base = valeur de la veille + achats au prix d'exécution."""
    growth, series, started = 1.0, [], False
    for p, b in zip(pnl, base):
        if p is not None and b is not None and b > EPS:
            growth *= 1.0 + p / b
            started = True
        series.append(growth - 1.0 if started else None)
    return series


def analyse(days, closes, events, names=None):
    """Calcule valeur, liquidités, gains, TWR (avec intervalle), contributions, rendements par titre. Voir le docstring du module.
    days    : ['AAAA-MM-JJ', ...] croissants ; tout événement doit tomber un de ces jours.
    closes  : {clé: [cours EUR par unité ajustée à chaque jour | None]}
    events  : [{'at', 'kind', 'key', 'qty', 'price', 'fees', 'amount', 'id'}] ; amount en EUR (positif) pour les mouvements d'argent."""
    names = names or {}
    n = len(days)
    by_day = {d: [] for d in days}
    for e in events:
        d = str(e['at'])[:10]
        if d not in by_day:
            raise ValueError(f'événement hors calendrier : {d}')
        by_day[d].append(e)
    keys = sorted({e['key'] for e in events if e.get('key') is not None}, key=str)

    book = _Book(keys)
    q, cost, realized, dividends = book.q, book.cost, book.realized, book.dividends

    out = {k: [] for k in ('value', 'cash', 'securities', 'net_contributions', 'gain', 'realized', 'latent', 'dividends', 'fees', 'estimated', 'factor', 'factor_low', 'factor_high', 'invalid')}
    day_gain = {k: [] for k in keys}  # gain journalier par titre (EUR)
    holding_value = {k: [] for k in keys}  # valeur de marché du titre en fin de journée (0 hors détention)
    sleeve_ret = {k: [] for k in keys}  # rendement journalier du titre (None hors exposition)
    day_base = []
    sleeve_pnl_open, sleeve_base_open = [], []
    max_identity_error = 0.0
    chain = {'central': 1.0, 'low': 1.0, 'high': 1.0}
    index = {'central': [], 'low': [], 'high': []}
    broken = False
    first_event_day = min((str(e['at'])[:10] for e in events), default=None)

    for i, d in enumerate(days):
        day0 = dt.datetime.fromisoformat(d)
        evs = sorted(by_day[d], key=lambda e: (_when(e['at']), PRIORITY[e['kind']], e.get('id') or 0))
        prev = {k: (closes[k][i - 1] if i > 0 else None) for k in keys}
        cur = {k: closes[k][i] for k in keys}
        held_start = {k: q[k] for k in keys if q[k] > EPS}
        invalid = any(prev[k] is None for k in held_start)
        v_start = book.cash + sum(held_start[k] * prev[k] for k in held_start) if not invalid else None
        buys_gross = {k: 0.0 for k in keys}
        sells_gross = {k: 0.0 for k in keys}
        buys_base = {k: 0.0 for k in keys}
        div_day = {k: 0.0 for k in keys}
        fee_day = {k: 0.0 for k in keys}
        anchors = {k: [] for k in keys}
        for k in held_start:
            if prev[k] is not None:
                anchors[k].append((0.0, prev[k]))
        snaps = []  # (t, cash avant, {clé: quantité avant}, flux signé)
        day_acc = {'buys_gross': buys_gross, 'sells_gross': sells_gross, 'buys_base': buys_base, 'div': div_day, 'fee': fee_day, 'acct': 0.0, 'flow': 0.0}
        for e in evs:
            book.apply(e, (_when(e['at']) - day0).total_seconds(), day_acc, snaps, anchors)
        acct_day, f_net = day_acc['acct'], day_acc['flow']
        held_end = {k: q[k] for k in keys if q[k] > EPS}
        if any(cur[k] is None for k in held_end):
            invalid = True
        for k in keys:
            if cur[k] is not None:
                anchors[k].append((DAY_SECONDS, cur[k]))
            anchors[k].sort(key=lambda a: a[0])
        v_end = None if invalid else book.cash + sum(held_end[k] * cur[k] for k in held_end)
        if v_end is not None and v_end < -0.005:
            invalid, v_end = True, None  # valeur négative (découvert supérieur aux titres) : le rendement n'a plus de sens, jamais de valeur inventée

        started = first_event_day is not None and d >= first_event_day
        est = bool(snaps)
        central, low, high = _day_factors(invalid, started, v_start, v_end, snaps, anchors)

        # gains par titre et identité
        pnl = {}
        for k in keys:
            price_pnl = (held_end.get(k, 0.0) * (cur[k] or 0.0) if k in held_end else 0.0) - (held_start.get(k, 0.0) * (prev[k] or 0.0) if k in held_start else 0.0) - (buys_gross[k] - sells_gross[k])
            pnl[k] = price_pnl + div_day[k] - fee_day[k]
        total_pnl = sum(pnl.values()) - acct_day
        if not invalid and v_start is not None and v_end is not None:
            max_identity_error = max(max_identity_error, abs((v_end - v_start - f_net) - total_pnl))
        r = None if central is None else central - 1.0
        if invalid or r is None:
            base_eff = None
        elif abs(r) > 1e-12:
            base_eff = total_pnl / r
        else:
            base_eff = v_start if v_start and v_start > EPS else 1.0  # gain nul : la base n'a aucun effet
        day_base.append(base_eff)
        for k in keys:
            day_gain[k].append(None if invalid else pnl[k])
            holding_value[k].append(None if invalid else (held_end[k] * cur[k] if k in held_end else 0.0))
        day_gain.setdefault('__fees__', []).append(None if invalid else -acct_day)
        # rendement du titre (« sleeve ») : exposition = quantité détenue la veille et achats du jour, au prix d'exécution
        base_sleeve_total, pnl_sleeve_total = 0.0, 0.0
        for k in keys:
            base_k = held_start.get(k, 0.0) * (prev[k] or 0.0) + buys_base[k]
            if invalid or base_k <= EPS:
                sleeve_ret[k].append(None)
            else:
                sleeve_ret[k].append(pnl[k] / base_k)
                if q[k] > EPS:
                    base_sleeve_total += base_k
                    pnl_sleeve_total += pnl[k]
        sleeve_pnl_open.append(None if invalid else pnl_sleeve_total)
        sleeve_base_open.append(None if invalid else base_sleeve_total)

        # chaînes : une valeur manquante coupe la chaîne pour la suite (aucune liaison artificielle entre deux passages fiables)
        if broken or central is None:
            broken = True
            for name in index:
                index[name].append(None)
        else:
            for name, f in (('central', central), ('low', low), ('high', high)):
                chain[name] *= f
                index[name].append(chain[name])
        out['factor'].append(central)
        out['factor_low'].append(low)
        out['factor_high'].append(high)
        out['estimated'].append(bool(est and started and low is not None and high - low > 1e-12))  # estimé seulement si l'heure du flux change vraiment le résultat
        out['invalid'].append(invalid)
        securities = None if invalid else sum(held_end[k] * cur[k] for k in held_end)
        out['value'].append(v_end)
        out['cash'].append(book.cash)
        out['securities'].append(securities)
        out['net_contributions'].append(book.net_contrib)
        rl = sum(realized.values())
        out['realized'].append(rl)
        out['dividends'].append(sum(dividends.values()))
        out['fees'].append(book.fees_acct)
        out['latent'].append(None if invalid else sum(held_end[k] * cur[k] - cost[k] for k in held_end))
        out['gain'].append(None if invalid else v_end - book.net_contrib)

    twr = {name: [None if x is None else x - 1.0 for x in index[name]] for name in index}

    contrib = _contributions(keys, out['factor'], day_gain, day_base, twr['central'])

    positions = _positions(keys, days, sleeve_ret, day_gain, book, closes, names, contrib)
    series = _open_series(sleeve_pnl_open, sleeve_base_open)

    mwr = None
    flows_all = book.flows_all
    if flows_all and out['value'] and out['value'][-1] is not None:
        start = min(t for t, _ in flows_all)
        end = dt.datetime.fromisoformat(days[-1]) + dt.timedelta(days=1)
        g = _xirr_period(flows_all, out['value'][-1], start, end)
        mwr = {'period': g, 'days': (end - start).total_seconds() / DAY_SECONDS}

    # cohérence : la somme des contributions égale le TWR affiché
    max_contrib_error = 0.0
    for i in range(n):
        if twr['central'][i] is not None and keys and contrib[keys[0]][i] is not None:
            max_contrib_error = max(max_contrib_error, abs(sum(contrib[k][i] for k in contrib) - twr['central'][i]))

    return {
        'method': 'twr_cash_v2',
        'days': list(days),
        **{k: out[k] for k in ('value', 'cash', 'securities', 'net_contributions', 'gain', 'realized', 'latent', 'dividends', 'fees', 'estimated', 'invalid')},
        'twr': twr,
        'factors': {'central': out['factor'], 'low': out['factor_low'], 'high': out['factor_high']},
        'contributions': contrib,
        'positions': positions,
        'open_positions_twr': series,
        'holding_value': holding_value,
        'trades': book.trades,
        'mwr': mwr,
        'checks': {'identity_max_abs_error': max_identity_error, 'contribution_sum_max_abs_error': max_contrib_error},
    }
