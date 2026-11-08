"""Barre de risque d'un achat : trois signaux simples (tendance, recul depuis le plus haut, stabilité), chacun noté de 0 à 2.

Rien n'est vendu et rien n'est prédit : la barre résume l'état du cours depuis l'achat et dit pourquoi, chiffres à l'appui.
Somme 0-1 : « ok » (tendance intacte) · 2-3 : « watch » (à surveiller) · 4-6 : « act » (vente à envisager).
Un recul qui atteint le seuil passe directement en « act ». Un saut de cours (règle ×1,6) ou un historique trop court donnent « na » :
la barre n'est alors pas évaluée au lieu de déclencher une alerte à tort. Les valeurs par défaut sont des points de départ modifiables, pas des vérités.
"""
import math

from .series import BREAK_RATIO

# Fenêtres (séances) par horizon de stratégie : (récente, longue, horizon du seuil de recul).
HORIZONS = {
    'fast': (21, 63, 10),
    'regular': (63, 126, 21), 'low_volatility': (63, 126, 21), 'recovery': (63, 126, 21), 'custom': (63, 126, 21),
    'momentum': (126, 252, 63), 'momentum12': (126, 252, 63), 'momentum_risk': (126, 252, 63),
}
K = 2.0                 # le seuil de recul vaut K × volatilité quotidienne × √horizon
DROP_MIN, DROP_MAX = 6.0, 30.0
EXTENDED = 25.0         # % au-dessus de la moyenne 50 jours : simple information, jamais notée
LEVELS = ('ok', 'watch', 'act')


def windows(strategy):
    """(récente, longue, horizon) d'une stratégie, None quand la barre n'a pas de sens (stratégie prudente, rééquilibrage annuel)."""
    return HORIZONS.get(strategy)


def _fit(closes):
    """Pente (% par séance), R² et ratio d'efficacité d'une série de clôtures positives, ou None."""
    n = len(closes)
    if n < 3 or min(closes) <= 0:
        return None
    y = [math.log(c) for c in closes]
    mx, my = (n - 1) / 2, sum(y) / n
    sxx = sum((i - mx) ** 2 for i in range(n))
    sxy = sum((i - mx) * (v - my) for i, v in enumerate(y))
    syy = sum((v - my) ** 2 for v in y)
    slope = sxy / sxx
    r2 = (sxy * sxy) / (sxx * syy) if syy > 0 else 0.0
    steps = [abs(y[i] - y[i - 1]) for i in range(1, n)]
    path = sum(steps)
    er = abs(y[-1] - y[0]) / path if path > 0 else 0.0
    return {'slope': 100 * math.expm1(slope), 'r2': r2, 'er': er}


def _vol(closes):
    r = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0 and closes[i] > 0]
    if len(r) < 2:
        return None
    m = sum(r) / len(r)
    return 100 * math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1))


def _fr(x, digits=1):
    return f'{x:.{digits}f}'.replace('.', ',')


def assess(strategy, closes, drop_pct, drop_override=None, ma50=None):
    """closes : clôtures corrigées des splits jusqu'à aujourd'hui (au moins la fenêtre longue) ; drop_pct : recul (%) depuis le plus haut depuis l'achat.

    Retourne {'level': 'ok'|'watch'|'act'|'na', 'score', 'max', 'signals': [...], 'drop_threshold', 'windows', 'reason'}.
    """
    w = windows(strategy)
    if w is None:
        return None
    recent, long_, horizon = w
    if len(closes) < long_ + 1:
        return {'level': 'na', 'score': None, 'max': 6, 'signals': [], 'windows': [recent, long_], 'reason': 'history',
                'message': f"Historique trop court pour évaluer la barre (il faut {long_ + 1} clôtures)."}
    tail = closes[-(long_ + 1):]
    if any(b > 0 and (a / b > BREAK_RATIO or a / b < 1 / BREAK_RATIO) for a, b in zip(tail[1:], tail[:-1])):
        return {'level': 'na', 'score': None, 'max': 6, 'signals': [], 'windows': [recent, long_], 'reason': 'break',
                'message': "Un saut de cours inhabituel (plus de ×1,6 ou moins de ÷1,6 en une séance) rend la barre non évaluable par prudence."}
    r, lg = _fit(closes[-(recent + 1):]), _fit(tail)
    sigma = _vol(tail)
    if r is None or lg is None or sigma is None:
        return {'level': 'na', 'score': None, 'max': 6, 'signals': [], 'windows': [recent, long_], 'reason': 'data', 'message': 'Données insuffisantes pour évaluer la barre.'}
    signals = []
    # 1. Tendance : pente récente comparée à la pente longue.
    if r['slope'] > 0 and r['slope'] >= 0.5 * max(lg['slope'], 0):
        pts, txt = 0, f"Tendance intacte : pente récente {_fr(r['slope'], 2)} %/séance sur {recent} séances (longue : {_fr(lg['slope'], 2)} %)."
    elif r['slope'] <= 0 and lg['slope'] <= 0:
        pts, txt = 2, f"Tendance cassée : pente récente {_fr(r['slope'], 2)} %/séance et pente sur {long_} séances {_fr(lg['slope'], 2)} %."
    else:
        pts, txt = 1, f"Tendance qui ralentit : pente récente {_fr(r['slope'], 2)} %/séance contre {_fr(lg['slope'], 2)} % sur {long_} séances."
    signals.append({'kind': 'slope', 'points': pts, 'label': 'Tendance', 'message': txt})
    # 2. Recul depuis le plus haut observé depuis l'achat : seuil proportionnel à la nervosité du titre, sauf réglage personnel.
    thr = float(drop_override) if drop_override is not None else min(DROP_MAX, max(DROP_MIN, K * sigma * math.sqrt(horizon)))
    d = drop_pct or 0.0
    pts = 2 if d >= thr else 1 if d >= 0.5 * thr else 0
    signals.append({'kind': 'drop', 'points': pts, 'label': 'Recul', 'value': round(d, 1), 'threshold': round(thr, 1),
                    'message': f"Recul de {_fr(d)} % depuis le plus haut depuis l'achat (seuil {_fr(thr)} %{', réglé par vous' if drop_override is not None else ' = ' + _fr(K, 0) + ' × volatilité × √' + str(horizon)})."})
    # 3. Stabilité : régularité de la hausse maintenant, comparée à la fenêtre précédente.
    before = _fit(closes[-(long_ + 1 + recent):-recent]) if len(closes) >= long_ + 1 + recent else None
    if before is None:
        pts, txt = 0, f"Régularité (R²) : {_fr(lg['r2'], 2)} sur {long_} séances."
    else:
        fall = before['r2'] - lg['r2']
        pts = 2 if lg['r2'] < 0.3 and fall >= 0.4 else 1 if lg['r2'] < 0.5 and fall >= 0.2 else 0
        txt = f"Régularité (R²) : {_fr(lg['r2'], 2)} contre {_fr(before['r2'], 2)} auparavant." + (' La hausse devient erratique.' if pts else '')
    signals.append({'kind': 'stability', 'points': pts, 'label': 'Stabilité', 'message': txt})
    score = sum(s['points'] for s in signals)
    level = 'act' if score >= 4 or d >= thr else 'watch' if score >= 2 else 'ok'
    out = {'level': level, 'score': score, 'max': 6, 'signals': signals, 'drop_threshold': round(thr, 1), 'windows': [recent, long_], 'reason': None}
    if ma50 and closes[-1] > ma50 * (1 + EXTENDED / 100):
        out['info'] = f"Information : le cours est {_fr(100 * (closes[-1] / ma50 - 1), 0)} % au-dessus de sa moyenne 50 jours (très étendu). Ce n'est pas un ordre de vente."
    return out
