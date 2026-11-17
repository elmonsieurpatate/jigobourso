"""Lecture des durées demandées par les configurations enregistrées, sans dépendance au moteur analytique."""

import json


BUILTIN = {'day': 1, 'week': 5, 'month': 21, 'quarter': 63, 'half': 126, 'year': 252, 'two_year': 504, 'three_year': 756, 'five_year': 1260}


def requested_sessions(conn):
    requested = set()
    with conn.cursor() as cur:
        cur.execute("SELECT name,value_json FROM settings WHERE name LIKE 'scores_profiles%' OR name LIKE 'ct_strategies:%'")
        settings_rows = cur.fetchall()
        cur.execute('SELECT strategy_config FROM portfolios WHERE strategy_config IS NOT NULL')
        portfolio_rows = cur.fetchall()
    for row in settings_rows:
        try:
            doc = json.loads(row['value_json'])
            candidates = (
                (item.get('config', {}).get('periods', {}) for item in doc.get('items', []))
                if row['name'].startswith('ct_strategies:')
                else (p.get('periods', {}) for p in doc.values() if isinstance(p, dict))
            )
            for periods in candidates:
                for pid, detail in periods.items():
                    if isinstance(detail, dict) and detail.get('enabled'):
                        n = detail.get('sessions', BUILTIN.get(pid))
                        if type(n) is int and 1 <= n <= 1260:
                            requested.add(n)
        except (TypeError, ValueError, KeyError, AttributeError):
            continue
    for row in portfolio_rows:
        try:
            cfg = json.loads(row['strategy_config'])
            for p in cfg.get('periods') or []:
                n = p.get('sessions')
                if p.get('enabled') and type(n) is int and 1 <= n <= 1260:
                    requested.add(n)
        except (TypeError, ValueError, KeyError, AttributeError):
            continue
    return requested
