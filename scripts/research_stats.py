"""Outils statistiques des analyses de recherche (bibliothèque standard seulement, aucune base, aucun réseau).

Règles du protocole (research/PROTOCOLE.md) : les actions d'une même date ne sont jamais indépendantes (on agrège par date d'abord) ; les dates voisines se chevauchent quand l'horizon dépasse
le pas de 21 séances (bootstrap par blocs mobiles, jamais par date isolée) ; l'effectif effectif est toujours affiché.
"""
import math
import random
import statistics

STEP = 21
BOOTSTRAP = 2000
SEED = 1


def block_length(horizon, step=STEP):
    """Longueur de bloc (en dates) du bootstrap : max(3, 2 × ⌈h / pas⌉)."""
    return max(3, 2 * math.ceil(horizon / step))


def spacing(horizon, step=STEP):
    return max(1, math.ceil(horizon / step))


def block_bootstrap_mean(values, block, draws=BOOTSTRAP, seed=SEED, alpha=0.05):
    """(moyenne, borne basse, borne haute) de la moyenne, par bootstrap à blocs mobiles (la série est supposée dans l'ordre chronologique). None si trop peu de valeurs."""
    n = len(values)
    if n < 3:
        return (statistics.fmean(values) if values else None), None, None
    block = max(1, min(block, n))
    rng = random.Random(seed)
    starts = n - block + 1
    per = math.ceil(n / block)
    means = []
    for _ in range(draws):
        total, count = 0.0, 0
        for _ in range(per):
            s = rng.randrange(starts)
            seg = values[s:s + block]
            total += sum(seg)
            count += len(seg)
        means.append(total / count)
    means.sort()
    lo, hi = means[int(alpha / 2 * draws)], means[int((1 - alpha / 2) * draws) - 1]
    return statistics.fmean(values), lo, hi


def block_bootstrap_p(values, block, draws=BOOTSTRAP, seed=SEED):
    """p-valeur bilatérale « la moyenne est nulle » : on recentre les valeurs sur 0 et on compte les moyennes rééchantillonnées au moins aussi éloignées que l'observée."""
    n = len(values)
    if n < 3:
        return None
    mean = statistics.fmean(values)
    centered = [v - mean for v in values]
    rng = random.Random(seed)
    block = max(1, min(block, n))
    starts = n - block + 1
    per = math.ceil(n / block)
    extreme = 0
    for _ in range(draws):
        total, count = 0.0, 0
        for _ in range(per):
            s = rng.randrange(starts)
            seg = centered[s:s + block]
            total += sum(seg)
            count += len(seg)
        if abs(total / count) >= abs(mean) - 1e-12:
            extreme += 1
    return (1 + extreme) / (draws + 1)


def tstat(values):
    if len(values) < 3:
        return None
    sd = statistics.stdev(values)
    return None if sd == 0 else statistics.fmean(values) / (sd / math.sqrt(len(values)))


def summary(values, horizon, step=STEP, draws=BOOTSTRAP, seed=SEED):
    """Résumé d'une série chronologique de valeurs (une par date) : moyenne, médiane, dispersion, IC par blocs, p, t sur dates espacées, effectifs."""
    if not values:
        return None
    sp = spacing(horizon, step)
    indep = values[::sp]
    mean, lo, hi = block_bootstrap_mean(values, block_length(horizon, step), draws, seed)
    return {'dates': len(values), 'independent': len(indep), 'mean': mean, 'median': statistics.median(values),
            'sd': statistics.pstdev(values) if len(values) > 1 else 0.0, 'ci_low': lo, 'ci_high': hi,
            'p_block': block_bootstrap_p(values, block_length(horizon, step), draws, seed), 't_indep': tstat(indep),
            'share_positive': 100.0 * sum(1 for v in values if v > 0) / len(values)}


def ranks(values):
    """Rangs moyens (1 = plus petit) d'une liste, ex æquo = moyenne des rangs."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            out[order[k]] = r
        i = j + 1
    return out


def pearson(a, b):
    n = len(a)
    if n < 3:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    if sa == 0 or sb == 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def spearman(a, b):
    """Corrélation de rang (Information Coefficient) ; None si moins de 3 couples ou série constante."""
    if len(a) != len(b) or len(a) < 3:
        return None
    return pearson(ranks(a), ranks(b))


def residuals(y, xs):
    """Résidus de la régression linéaire de y sur les colonnes xs (avec constante), par équations normales. Colonnes colinéaires : renvoie y centré."""
    n, k = len(y), len(xs)
    cols = [[1.0] * n] + [list(x) for x in xs]
    m = k + 1
    a = [[sum(cols[i][r] * cols[j][r] for r in range(n)) for j in range(m)] for i in range(m)]
    b = [sum(cols[i][r] * y[r] for r in range(n)) for i in range(m)]
    for i in range(m):
        piv = max(range(i, m), key=lambda r: abs(a[r][i]))
        if abs(a[piv][i]) < 1e-12:
            mean = sum(y) / n
            return [v - mean for v in y]
        a[i], a[piv] = a[piv], a[i]
        b[i], b[piv] = b[piv], b[i]
        for r in range(i + 1, m):
            f = a[r][i] / a[i][i]
            for c in range(i, m):
                a[r][c] -= f * a[i][c]
            b[r] -= f * b[i]
    beta = [0.0] * m
    for i in range(m - 1, -1, -1):
        beta[i] = (b[i] - sum(a[i][c] * beta[c] for c in range(i + 1, m))) / a[i][i]
    return [y[r] - sum(beta[c] * cols[c][r] for c in range(m)) for r in range(n)]


def partial_spearman(signal, future, controls):
    """Corrélation de rang entre signal et rendement futur après retrait (régression sur les rangs) des variables de contrôle. controls : liste de listes alignées."""
    if len(signal) < 10:
        return None
    rs, rf = ranks(signal), ranks(future)
    rc = [ranks(c) for c in controls]
    return pearson(residuals(rs, rc), residuals(rf, rc))


def var_cvar(returns, level=0.95):
    """(VaR, CVaR) historiques en % de perte (valeurs négatives = pertes) au niveau donné : quantile bas et moyenne des pires cas."""
    if not returns:
        return None, None
    ordered = sorted(returns)
    cut = max(1, int(math.floor((1 - level) * len(ordered) + 1e-9)))
    var = ordered[cut - 1]
    return var, statistics.fmean(ordered[:cut])


def max_drawdown(returns):
    """Drawdown maximal (en %, négatif) d'une suite de rendements périodiques en % (richesse cumulée)."""
    wealth, peak, worst = 1.0, 1.0, 0.0
    for r in returns:
        wealth *= 1 + r / 100.0
        peak = max(peak, wealth)
        worst = min(worst, wealth / peak - 1)
    return 100 * worst
