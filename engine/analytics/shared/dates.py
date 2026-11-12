"""Dates sérialisées pour l'interface."""
import datetime


def iso(v):
    """datetime : `AAAA-MM-JJ hh:mm:ss` ; date : `AAAA-MM-JJ` ; toute autre valeur est rendue telle quelle."""
    if isinstance(v, datetime.datetime):
        return v.isoformat(sep=' ')
    return v.isoformat() if isinstance(v, datetime.date) else v
