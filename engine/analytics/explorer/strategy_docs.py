"""Faits de référence des sept stratégies officielles, lus dans le code réellement exécuté (jamais recopiés) : critères de recherche, granularités, poids, constantes de formule.
Le centre d'aide et les fiches de « Mes stratégies » les affichent tels quels : si une valeur change dans le moteur, la documentation change avec elle."""
from ..scoring import ranking_table
from ..scoring import scores as SC
from ..admin import scores_admin as A
from . import strategy as LEGACY
from . import explorer_config as C
from ..scoring import score_service


def facts(conn, request=None):
    A.refresh(conn)
    glob = score_service.admin_defaults(conn)
    crit = ranking_table.criteria()['criteria']
    out = []
    for ct_id, name in A.CT_BUILTIN.items():
        prof = A.official_clean(conn, name)
        base = A.base_config(name)
        active = [pid for pid in A.SCORING_PERIODS if prof['periods'][pid]['enabled']]
        auto = A.auto_weights(glob['kappa'], active)
        custom = prof['weights_mode'] == 'custom'
        periods = [{'id': pid, 'sessions': C.SESSIONS[pid], 'label': A.PERIOD_LABELS[pid], 'weight': (prof['weights'].get(pid, 0.0) if custom else auto.get(pid, 0.0))} for pid in active]
        out.append({'id': ct_id, 'name': name, 'label': A.LABELS[name],
                    'criteria': {pid: dict(v) for pid, v in crit[ct_id]['periods'].items()},
                    'periods': periods, 'weights_mode': prof['weights_mode'], 'complex_weights': prof['complex_weights'], 'tuning': prof['tuning'],
                    'sort': base['ranking']['sort'], 'require_fresh': prof['technical']['require_fresh']})
    return {'strategies': out,
            'common': {'kappa': glob['kappa'], 'threshold': glob['threshold'], 'anchor': glob['anchor'],
                       'slope_levels': LEGACY.SLOPE_LEVELS, 'r2_levels': {k: v for k, v in LEGACY.R2_LEVELS.items() if v is not None},
                       'periods': {pid: {'sessions': C.SESSIONS[pid], 'label': A.PERIOD_LABELS.get(pid, pid)} for pid in C.PERIODS},
                       'saturation': {'a': SC.SAT_A, 'b': SC.SAT_B}, 'gate_floor': SC.GATE_FLOOR, 'reliability_sessions': SC.RELIABILITY_SESSIONS, 'min_sessions': SC.MIN_SESSIONS,
                       'accel': {'ref': SC.ACCEL_REF, 'r2': SC.ACCEL_R2}, 'recovery': {'best': SC.RECOVERY_BEST, 'worst': SC.RECOVERY_WORST},
                       'momentum': {'saturation': SC.MOMENTUM_SAT, 'long': {'6m': 126, '12m': 252}, 'skip': 21},
                       'liquidity': {'floor_eur': SC.LIQUIDITY_FLOOR_EUR, 'ceil_eur': SC.LIQUIDITY_CEIL_EUR},
                       'vol': {'ratio_best': SC.VOL_RATIO_BEST, 'ratio_worst': SC.VOL_RATIO_WORST, 'slope_floor': SC.VOL_SLOPE_FLOOR},
                       'complex_labels': SC.COMPLEX_LABELS, 'complex_defaults': SC.COMPLEX_WEIGHTS}}
