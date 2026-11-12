"""Catégories des scores V4 pour les filtres d'affichage de l'Explorer (préparation : l'Explorer ne les consomme pas encore).

Les définitions viennent de l'administration des filtres (réglages `explorer_secondary_filters`, filtres `score_simple` et `score_complex`).
Ce module ne calcule aucune note : il range une note déjà produite par le moteur dans une catégorie et sélectionne des lignes.
Garanties : une ligne retenue est renvoyée telle quelle (note, rang, statut inchangés) ; une ligne exclue n'est ni modifiée ni supprimée du calcul ;
un score partiel reste une note numérique rangée dans sa catégorie ; seule une note absente (None) va dans la catégorie « inconnue ».
"""
FILTERS = {'simple': ('score_simple', 'score_simple_v4'), 'complex': ('score_complex', 'score_complex_v4')}
SETTING = 'explorer_secondary_filters'
DEFAULTS_SETTING = 'explorer_secondary_defaults'


def _inside(c, v):
    return ((c['min'] is None or v > c['min'] or (v == c['min'] and c['minIncluded']))
            and (c['max'] is None or v < c['max'] or (v == c['max'] and c['maxIncluded'])))


def assign(value, categories):
    """Identifiant de la catégorie d'une note (None → catégorie « inconnue » ; None si aucune ne convient)."""
    if value is None:
        return next((c['id'] for c in categories if c.get('unknown')), None)
    return next((c['id'] for c in categories if not c.get('unknown') and _inside(c, value)), None)


def measure(definitions, which):
    """(catégories ordonnées, filtre activé) du score `which` ('simple' | 'complex') dans un document de définitions."""
    fid, mid = FILTERS[which]
    for f in definitions.get('filters', []):
        if f['id'] == fid:
            for m in f['measures']:
                if m['id'] == mid:
                    return m['categories'], bool(f.get('enabled'))
    return [], False


def select(entries, which, selected, categories):
    """Lignes dont la catégorie du score `which` est dans `selected` (None/absent = tout inclure). Ordre, notes et rangs des lignes inchangés."""
    if selected is None or not categories:
        return list(entries)
    key = 'score_' + which
    chosen = set(selected)
    return [e for e in entries if assign(e.get(key), categories) in chosen]


