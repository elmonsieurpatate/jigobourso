"""Calendriers des séances utilisés pour dater les fenêtres d'analyse.

Un MIC inconnu ou un calendrier non disponible ne retombe jamais sur un
calendrier lundi-vendredi : le calcul doit échouer fermé plutôt que compter
un jour férié comme une séance.
"""
import datetime
from functools import lru_cache


# Alias limités aux places ayant le même calendrier de jours de négociation.
# Les places régionales allemandes partagent le calendrier de Francfort.
_CALENDAR_BY_MIC = {
    'XASE': 'XNYS', 'ARCX': 'XNYS', 'XNAS': 'XNAS', 'XNYS': 'XNYS', 'BATS': 'BATS',
    'XFRA': 'XFRA', 'XETR': 'XETR', 'XBER': 'XFRA', 'XSTU': 'XFRA', 'XDUS': 'XFRA',
    'XHAM': 'XFRA', 'XMUN': 'XFRA', 'XHAN': 'XFRA',
    'XPAR': 'XPAR', 'XAMS': 'XAMS', 'XBRU': 'XBRU', 'XLON': 'XLON', 'XMIL': 'XMIL',
    'XMAD': 'XMAD', 'XSTO': 'XSTO', 'XOSL': 'XOSL', 'XSWX': 'XSWX', 'XHEL': 'XHEL',
    'XCSE': 'XCSE', 'XICE': 'XICE', 'XWBO': 'XWBO', 'XDUB': 'XDUB', 'XLIS': 'XLIS',
    'XWAR': 'XWAR', 'XPRA': 'XPRA', 'XBUD': 'XBUD', 'XBSE': 'XBSE', 'XIST': 'XIST',
    'XTSE': 'XTSE', 'XCNQ': 'XTSE', 'XTSX': 'XTSE', 'XMEX': 'XMEX', 'BVMF': 'BVMF',
    'XSGO': 'XSGO', 'XBUE': 'XBUE', 'XTKS': 'XTKS', 'XHKG': 'XHKG', 'XSHG': 'XSHG',
    'XSHE': 'XSHG', 'XKRX': 'XKRX', 'XKOS': 'XKRX', 'XASX': 'XASX', 'XNZE': 'XNZE',
    'XSES': 'XSES', 'XBOM': 'XBOM', 'XNSE': 'XBOM', 'XTAI': 'XTAI', 'XTAE': 'XTAE',
    'XJSE': 'XJSE', 'XBKK': 'XBKK', 'XIDX': 'XIDX', 'XKLS': 'XKLS', 'XKAR': 'XKAR',
    'XPHS': 'XPHS', 'XSAU': 'XSAU', 'XBOG': 'XBOG', 'XLIM': 'XLIM', 'XCBF': 'XCBF',
}


@lru_cache(maxsize=64)
def _sessions(mic, end_date, count):
    """Renvoie les `count` dernières séances jusqu'à end_date (dates ISO), ou None."""
    calendar_name = _CALENDAR_BY_MIC.get(str(mic or '').upper())
    if not calendar_name:
        return None
    try:
        import exchange_calendars as xc
        end = datetime.date.fromisoformat(str(end_date)[:10])
        # Au moins 2 années de marge pour compter les séances à partir du jour
        # de référence même quand une place a de longues fermetures saisonnières.
        start = end - datetime.timedelta(days=max(730, int(count) * 4))
        cal = xc.get_calendar(calendar_name, start=start.isoformat(), end=end.isoformat())
        labels = cal.sessions
        result = [str(x.date()) for x in labels if x.date() <= end]
        return result[-int(count):] if len(result) >= int(count) else None
    except (ImportError, ValueError, KeyError, TypeError):
        return None


def session_dates(mic, end_date, count):
    """Interface sûre pour obtenir count dates de séance se terminant au jour indiqué."""
    if not end_date or not count or count < 1:
        return None
    return _sessions(str(mic or '').upper(), str(end_date)[:10], int(count))


def window_calendars(mic, end_date, windows):
    """Dictionnaire n -> n+1 séances (un rendement sur n séances)."""
    return {int(n): session_dates(mic, end_date, int(n) + 1) for n in windows}


@lru_cache(maxsize=128)
def _next_sessions(mic, after_date, count):
    calendar_name = _CALENDAR_BY_MIC.get(str(mic or '').upper())
    if not calendar_name:
        return None
    try:
        import exchange_calendars as xc
        after = datetime.date.fromisoformat(str(after_date)[:10])
        end = after + datetime.timedelta(days=max(30, int(count) * 4))
        cal = xc.get_calendar(calendar_name, start=after.isoformat(), end=end.isoformat())
        result = [str(x.date()) for x in cal.sessions if x.date() > after]
        return result[:int(count)] if len(result) >= int(count) else None
    except (ImportError, ValueError, KeyError, TypeError):
        return None


def next_session_dates(mic, after_date, count):
    """Les prochaines dates de séance strictement après une clôture donnée."""
    if not after_date or not count or count < 1:
        return None
    return _next_sessions(str(mic or '').upper(), str(after_date)[:10], int(count))
