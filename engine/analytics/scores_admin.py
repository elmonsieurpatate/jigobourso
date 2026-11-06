"""Administration des scores V4 : lecture de l'état (réglages, valeurs de conception, couverture de la liquidité) et enregistrement validé."""
from engine.shared import settings

from . import explorer_config as C, score_service, scores as SC


def design():
    return {'kappa': SC.KAPPA, 'threshold': SC.COVERAGE_THRESHOLD, 'complex_weights': dict(SC.COMPLEX_WEIGHTS)}


def coverage(conn):
    """Origine de la liquidité des titres notés : volumes quotidiens réels, estimation (proxy) ou inconnue."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM v_recommendable")
        total = int(cur.fetchone()['n'])
        cur.execute("SELECT source, COUNT(*) AS n, MAX(computed_at) AS at, MAX(volume_checked_at) AS checked FROM liquidity_state GROUP BY source")
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) AS n FROM score_inputs")
        inputs = int(cur.fetchone()['n'])
    by = {r['source']: int(r['n']) for r in rows}
    return {'universe': total, 'daily': by.get('daily', 0), 'estimated': by.get('estimated', 0), 'unknown': max(0, total - sum(by.values())),
            'computed_at': max((r['at'] for r in rows if r['at']), default=None), 'volume_checked_at': max((r['checked'] for r in rows if r['checked']), default=None), 'score_inputs': inputs}


def state(conn):
    cur = score_service.admin_defaults(conn)
    stored = settings.get(conn, score_service.SETTING, None)
    return {'design': design(), 'current': {'kappa': cur['kappa'], 'threshold': cur['threshold'], 'complex_weights': dict(SC.COMPLEX_WEIGHTS, **cur['complex_weights'])},
            'customised': bool(stored), 'coverage': coverage(conn), 'volume_collection': bool(settings.get(conn, 'volume_collection', False)), 'version': SC.VERSION}


def save(conn, request):
    """Enregistre κ, seuil de couverture et poids du score complexe ; `reset` revient aux valeurs de conception. Rien d'autre n'est modifiable ici."""
    if request.get('reset'):
        settings.put(conn, score_service.SETTING, {})
    else:
        clean = C.validate_scoring({k: request.get(k) for k in ('kappa', 'threshold', 'complex_weights')}, [])
        if not any(clean['complex_weights'].get(k, SC.COMPLEX_WEIGHTS[k]) > 0 for k in SC.COMPLEX_WEIGHTS):
            raise ValueError('Le score complexe doit garder au moins un poids positif')
        settings.put(conn, score_service.SETTING, clean)
    return state(conn)
