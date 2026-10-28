"""Chargement du catalogue FinanceDatabase (dépôt Git de CSV) dans instruments et listings.

Idempotent : un rechargement met à jour l'identité, applique les règles d'admission et recalcule la cotation principale.
Les statuts décidés par le préfiltre de marché (motif « préfiltre : … ») et les cotations sélectionnées ne sont pas écrasés.
"""
import csv
import datetime
import json
import sys
from collections import defaultdict
from pathlib import Path

from engine.shared import settings
from . import rules
from .primary import choose_primary

csv.field_size_limit(sys.maxsize)
ISIN_COUNTRY = {'DE': 'Germany', 'FR': 'France', 'NL': 'Netherlands', 'GB': 'United Kingdom', 'IT': 'Italy', 'ES': 'Spain',
                'SE': 'Sweden', 'NO': 'Norway', 'CH': 'Switzerland', 'US': 'United States'}
PREFILTER_PREFIX = 'préfiltre'


def group_key(row):
    isin = (row.get('isin') or '').strip()
    if len(isin) == 12:
        return 'isin:' + isin
    for col in ('shareclass_figi', 'composite_figi', 'figi'):
        v = (row.get(col) or '').strip()
        if v:
            return 'figi:' + v
    return f"sym:{row.get('mic')}:{row.get('symbol')}"[:40]


def read_rows(root):
    """Itère (kind, ligne) sur database/equities/*.csv et database/etfs/*.csv."""
    for kind, folder in (('equity', 'equities'), ('etf', 'etfs')):
        for path in sorted(Path(root, 'database', folder).glob('*.csv')):
            with path.open(newline='', encoding='utf-8') as fh:
                for row in csv.DictReader(fh):
                    yield kind, row


def raw_rows(root):
    """Lignes brutes de FinanceDatabase, normalisées pour la table catalogue_raw (aucune règle appliquée ici)."""
    for kind, row in read_rows(root):
        mic, symbol = (row.get('mic') or '').strip(), (row.get('symbol') or '').strip()
        isin = (row.get('isin') or '').strip()
        country = (row.get('country') or '').strip() or ISIN_COUNTRY.get(isin[:2]) if kind == 'equity' else ISIN_COUNTRY.get(isin[:2])
        category = (row.get('sector') if kind == 'equity' else row.get('category_group')) or None
        yield {'kind': kind, 'mic': mic[:12], 'symbol': symbol[:64], 'isin': isin if len(isin) == 12 else None, 'name': (row.get('name') or '')[:200],
               'country': (country or None) and country[:60], 'category': (category or '')[:80] or None, 'currency': (row.get('currency') or '').strip()[:3] or None,
               'delisted': 1 if str(row.get('delisted', '')).strip().lower() in ('true', '1') else 0, 'group_key': group_key(dict(row, mic=mic, symbol=symbol))}


def chunks(rows, size=5000):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


RAW_COLUMNS = ('kind', 'mic', 'symbol', 'isin', 'name', 'country', 'category', 'currency', 'delisted', 'group_key')


def store_raw(conn, root):
    """Remplace le contenu brut par celui du dossier FinanceDatabase. Ne touche ni aux instruments ni aux cotations. Renvoie le nombre de lignes."""
    with conn.cursor() as cur:
        cur.execute('DELETE FROM catalogue_raw')
        sql = f"INSERT INTO catalogue_raw({','.join(RAW_COLUMNS)}) VALUES ({','.join(['%s'] * len(RAW_COLUMNS))})"
        total, batch = 0, []
        for r in raw_rows(root):
            batch.append(tuple(r[c] for c in RAW_COLUMNS))
            if len(batch) >= 5000:
                cur.executemany(sql, batch)
                total += len(batch)
                batch = []
        if batch:
            cur.executemany(sql, batch)
            total += len(batch)
    conn.commit()
    return total


def apply_rules(conn, config=None):
    """Applique les règles du catalogue aux données brutes déjà stockées (sans téléchargement) : renseigne removed_step / removed_reason.
    Renvoie le nombre de lignes dont le résultat a changé."""
    cfg = config or settings.catalogue_rules(conn)
    with conn.cursor() as cur:
        cur.execute('SELECT id, kind, mic, symbol, name, category, delisted, removed_step, removed_reason FROM catalogue_raw ORDER BY id')
        seen, updates = set(), []
        for r in cur.fetchall():
            key = (r['mic'], r['symbol'])
            if not r['mic'] or not r['symbol']:
                step, reason = 'incomplete', rules.BY_ID['incomplete']['reason']
            elif key in seen:
                step, reason = 'duplicates', rules.BY_ID['duplicates']['reason']
            else:
                seen.add(key)
                step, reason = rules.evaluate(r['kind'], r, cfg)
            if (step, reason) != (r['removed_step'], r['removed_reason']):
                updates.append((step, reason, r['id']))
        groups = {}
        for step, reason, rid in updates:                      # peu de motifs distincts : une requête par motif et par paquet d'identifiants
            groups.setdefault((step, reason), []).append(rid)
        for (step, reason), ids in groups.items():
            for part in chunks(ids, 2000):
                cur.execute(f"UPDATE catalogue_raw SET removed_step=%s, removed_reason=%s WHERE id IN ({','.join(['%s'] * len(part))})", [step, reason] + part)
    conn.commit()
    return len(updates)


def sync_listings(conn, config=None):
    """Répercute le résultat des règles sur instruments et cotations. Ne supprime jamais une cotation : une cotation sortie du périmètre
    passe en « exclue » avec son motif (une position détenue reste donc suivie et valorisée). Renvoie un résumé."""
    cfg = config or settings.catalogue_rules(conn)
    perimeter_steps = tuple(r['id'] for r in rules.RULES if r.get('perimeter'))
    marks = ','.join(['%s'] * len(perimeter_steps))
    instruments, listings = {}, []
    with conn.cursor() as cur:
        cur.execute(f'SELECT kind, mic, symbol, isin, name, country, category, currency, group_key, removed_reason FROM catalogue_raw WHERE removed_step IS NULL OR removed_step NOT IN ({marks}) ORDER BY id',
                    perimeter_steps)
        for r in cur.fetchall():
            if r['group_key'] not in instruments:
                instruments[r['group_key']] = {'group_key': r['group_key'], 'isin': r['isin'], 'kind': r['kind'], 'name': r['name'], 'country': r['country'], 'category': r['category']}
            listings.append({'key': r['group_key'], 'mic': r['mic'], 'symbol': r['symbol'][:24], 'currency': r['currency'], 'reason': r['removed_reason']})
        for part in chunks(list(instruments.values())):
            cur.executemany(
                """INSERT INTO instruments(group_key,isin,kind,name,country,category) VALUES (%s,%s,%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE isin=VALUES(isin), name=VALUES(name), country=VALUES(country), category=VALUES(category)""",
                [(i['group_key'], i['isin'], i['kind'], i['name'], i['country'], i['category']) for i in part])
        conn.commit()
        cur.execute('SELECT id, group_key FROM instruments')
        ids = {r['group_key']: r['id'] for r in cur.fetchall()}
        for part in chunks(listings):
            # Une exclusion par les règles remplace 'candidate' ; une cotation déjà 'selected' ou exclue par le préfiltre reste inchangée.
            cur.executemany(
                """INSERT INTO listings(instrument_id,mic,symbol,currency,status,excluded_reason) VALUES (%s,%s,%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE instrument_id=VALUES(instrument_id), currency=VALUES(currency),
                     status=IF(VALUES(status)='excluded','excluded',IF(excluded_reason IS NOT NULL AND excluded_reason NOT LIKE 'préfiltre%%','candidate',status)),
                     excluded_reason=IF(VALUES(status)='excluded',VALUES(excluded_reason),IF(excluded_reason LIKE 'préfiltre%%',excluded_reason,NULL))""",
                [(ids[l['key']], l['mic'], l['symbol'], l['currency'], 'excluded' if l['reason'] else 'candidate', l['reason']) for l in part])
        conn.commit()
        # Cotations déjà connues dont la ligne est maintenant hors périmètre (place ou type retirés) : exclues, jamais supprimées.
        scope = tuple(x for x in perimeter_steps if x not in ('incomplete', 'duplicates'))       # un doublon ne retire pas la ligne d'origine
        cur.execute(f"""UPDATE listings l JOIN catalogue_raw r ON r.mic=l.mic AND r.symbol=l.symbol AND r.removed_step IN ({','.join(['%s'] * len(scope))})
                        SET l.status='excluded', l.excluded_reason=r.removed_reason, l.is_primary=0, l.primary_reason=NULL
                        WHERE l.status<>'excluded' OR l.excluded_reason<>r.removed_reason OR l.excluded_reason IS NULL""", scope)
        outside = cur.rowcount
    conn.commit()
    primaries = assign_primaries(conn)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) n FROM listings WHERE status='excluded'")
        excluded = cur.fetchone()['n']
        cur.execute('SELECT COUNT(*) n FROM listings')
        total = cur.fetchone()['n']
        cur.execute('UPDATE catalogue_loads SET rules_json=%s, rows_kept=%s ORDER BY id DESC LIMIT 1', (json.dumps(cfg, ensure_ascii=False), total))
    conn.commit()
    settings.mark_applied(conn, 'catalogue', cfg)
    return {'instruments': len(instruments), 'cotations': total, 'exclues': excluded, 'principales': primaries, 'hors_perimetre_mises_a_jour': outside}


def record_load(conn, read, commit):
    with conn.cursor() as cur:
        cur.execute('INSERT INTO catalogue_loads(source_commit,loaded_at,rows_read,rows_kept,rules_json) VALUES (%s,%s,%s,%s,%s)',
                    (commit, datetime.datetime.utcnow().replace(microsecond=0), read, 0, '{}'))
    conn.commit()


def load(conn, root, commit):
    """Import complet : stocke les données brutes, applique les règles enregistrées, répercute sur les cotations. Renvoie un résumé."""
    read = store_raw(conn, root)
    apply_rules(conn)
    record_load(conn, read, commit)
    summary = sync_listings(conn)
    summary['lues'] = read
    return summary


def assign_primaries(conn):
    """Recalcule listings.is_primary / primary_reason pour tous les produits (règle R1). Renvoie le nombre de principales."""
    with conn.cursor() as cur:
        cur.execute("""SELECT l.id, l.instrument_id, l.mic, l.symbol, l.currency, i.country,
                              COALESCE(p.price * p.avg_volume_3m * COALESCE(f.to_eur, IF(l.currency='EUR',1,NULL)), 0) AS liquidity
                       FROM listings l JOIN instruments i ON i.id = l.instrument_id
                       LEFT JOIN latest_prices p ON p.listing_id = l.id
                       LEFT JOIN (SELECT currency, SUBSTRING_INDEX(GROUP_CONCAT(to_eur ORDER BY rate_date DESC), ',', 1) AS to_eur
                                  FROM fx_rates GROUP BY currency) f ON f.currency = l.currency
                       WHERE l.status <> 'excluded' OR l.excluded_reason LIKE 'préfiltre%'""")
        by_instrument = defaultdict(list)
        for r in cur.fetchall():
            by_instrument[r['instrument_id']].append(r)
        updates = []
        for rows in by_instrument.values():
            liquidity = {r['id']: float(r['liquidity'] or 0) for r in rows}
            winner, reason = choose_primary(rows, rows[0]['country'], liquidity)
            updates += [(1 if r['id'] == winner else 0, reason if r['id'] == winner else None, r['id']) for r in rows]
        cur.execute('UPDATE listings SET is_primary=0, primary_reason=NULL')
        for part in chunks(updates):
            cur.executemany('UPDATE listings SET is_primary=%s, primary_reason=%s WHERE id=%s', part)
    conn.commit()
    return sum(1 for u in updates if u[0])
