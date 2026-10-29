"""Horaires des places (heure locale, jours ouvrés). Les jours fériés ne sont pas listés : un jour sans aucune cotation
renvoyée par une place est un jour férié (voir gaps.py), pas une panne."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

HOURS = {  # mic: (fuseau, ouverture, clôture)
    'XETR': ('Europe/Berlin', time(9, 0), time(17, 30)), 'XPAR': ('Europe/Paris', time(9, 0), time(17, 30)),
    'XAMS': ('Europe/Amsterdam', time(9, 0), time(17, 30)), 'XLON': ('Europe/London', time(8, 0), time(16, 30)),
    'XMIL': ('Europe/Rome', time(9, 0), time(17, 30)), 'XMAD': ('Europe/Madrid', time(9, 0), time(17, 30)),
    'XSTO': ('Europe/Stockholm', time(9, 0), time(17, 30)), 'XOSL': ('Europe/Oslo', time(9, 0), time(16, 20)),
    'XSWX': ('Europe/Zurich', time(9, 0), time(17, 30)),
    **{m: ('America/New_York', time(9, 30), time(16, 0)) for m in ('XNAS', 'XNYS', 'XASE', 'ARCX', 'BATS')},
    # autres places connues (horaires réguliers approximatifs, pause déjeuner ignorée) : le choix des places est libre dans l'administration
    'XBRU': ('Europe/Brussels', time(9, 0), time(17, 30)), 'XLIS': ('Europe/Lisbon', time(8, 0), time(16, 30)), 'XHEL': ('Europe/Helsinki', time(10, 0), time(18, 30)),
    'XCSE': ('Europe/Copenhagen', time(9, 0), time(17, 0)), 'XICE': ('Atlantic/Reykjavik', time(9, 30), time(15, 30)), 'XWBO': ('Europe/Vienna', time(9, 0), time(17, 30)),
    'XDUB': ('Europe/Dublin', time(8, 0), time(16, 30)), 'XATH': ('Europe/Athens', time(10, 30), time(17, 20)), 'XWAR': ('Europe/Warsaw', time(9, 0), time(17, 0)),
    'XPRA': ('Europe/Prague', time(9, 0), time(16, 20)), 'XBUD': ('Europe/Budapest', time(9, 0), time(17, 0)), 'XIST': ('Europe/Istanbul', time(10, 0), time(18, 0)),
    'XLUX': ('Europe/Luxembourg', time(9, 0), time(17, 30)), 'XBSE': ('Europe/Bucharest', time(10, 0), time(17, 45)),
    **{m: ('Europe/Berlin', time(8, 0), time(20, 0)) for m in ('XFRA', 'XSTU', 'XBER', 'XDUS', 'XHAM', 'XMUN', 'XHAN')},
    **{m: ('America/Toronto', time(9, 30), time(16, 0)) for m in ('XTSE', 'XTSX', 'XCNQ')},
    'XMEX': ('America/Mexico_City', time(8, 30), time(15, 0)), 'BVMF': ('America/Sao_Paulo', time(10, 0), time(17, 0)), 'XSGO': ('America/Santiago', time(9, 30), time(17, 0)),
    'XBUE': ('America/Argentina/Buenos_Aires', time(11, 0), time(17, 0)),
    'XTKS': ('Asia/Tokyo', time(9, 0), time(15, 30)), 'XHKG': ('Asia/Hong_Kong', time(9, 30), time(16, 0)), 'XSHG': ('Asia/Shanghai', time(9, 30), time(15, 0)),
    'XSHE': ('Asia/Shanghai', time(9, 30), time(15, 0)), 'XKRX': ('Asia/Seoul', time(9, 0), time(15, 30)), 'XKOS': ('Asia/Seoul', time(9, 0), time(15, 30)),
    'XASX': ('Australia/Sydney', time(10, 0), time(16, 0)), 'XNZE': ('Pacific/Auckland', time(10, 0), time(16, 45)), 'XSES': ('Asia/Singapore', time(9, 0), time(17, 0)),
    'XBOM': ('Asia/Kolkata', time(9, 15), time(15, 30)), 'XNSE': ('Asia/Kolkata', time(9, 15), time(15, 30)), 'XTAI': ('Asia/Taipei', time(9, 0), time(13, 30)),
    'XBKK': ('Asia/Bangkok', time(10, 0), time(16, 30)), 'XKLS': ('Asia/Kuala_Lumpur', time(9, 0), time(17, 0)), 'XIDX': ('Asia/Jakarta', time(9, 0), time(16, 0)),
    'XTAE': ('Asia/Jerusalem', time(9, 59), time(17, 25)), 'XJSE': ('Africa/Johannesburg', time(9, 0), time(17, 0)),
}
UNKNOWN = ('UTC', time(0, 0), time(23, 59))     # place sans horaires connus : clôtures quotidiennes seulement, pas de barres de 15 minutes
SETTLE_MINUTES = 30      # Yahoo publie la clôture officielle quelques minutes après la fermeture
SLOT_MINUTES = 15


def known(mic):
    """Horaires connus (barres de 15 minutes gérées) ?"""
    return mic in HOURS


def spec(mic):
    return HOURS.get(mic, UNKNOWN)


def _local(mic, now):
    return now.astimezone(ZoneInfo(spec(mic)[0]))


def is_open(mic, now):
    if not known(mic):
        return False
    tz, opens, closes = HOURS[mic]
    local = _local(mic, now)
    return local.weekday() < 5 and opens <= local.time() < closes


def session_date(mic, now):
    """Date locale de la séance en cours ou, hors séance, de la dernière séance ouvrée terminée ou commencée."""
    local = _local(mic, now)
    day = local.date()
    if local.weekday() >= 5 or local.time() < spec(mic)[1]:
        day -= timedelta(days=1)
        while day.weekday() >= 5:
            day -= timedelta(days=1)
    return day


def is_settled(mic, day, now):
    """La clôture officielle de la séance `day` est-elle publiée ?"""
    tz, _, closes = spec(mic)
    end = datetime.combine(day, closes, ZoneInfo(tz)) + timedelta(minutes=SETTLE_MINUTES)
    return now >= end


def expected_slots(mic):
    """Nombre de créneaux de 15 minutes d'une séance complète."""
    if not known(mic):
        return 0
    _, opens, closes = HOURS[mic]
    return int(((closes.hour * 60 + closes.minute) - (opens.hour * 60 + opens.minute)) / SLOT_MINUTES)


def utcnow():
    return datetime.now(timezone.utc)


def expected_last_close(mic, now):
    """Dernière clôture due selon l'horloge, indépendante des réponses du fournisseur.

    Référence prudente jours ouvrés + délai de publication. Sans calendrier certifié,
    un jour férié peut être signalé à vérifier ; une panne générale ne devient jamais
    une preuve de fermeture de marché.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    local = _local(mic, now)
    day = local.date()
    if day.weekday() >= 5 or not is_settled(mic, day, now):
        day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day.isoformat()
