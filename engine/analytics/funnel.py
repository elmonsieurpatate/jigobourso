"""Entonnoirs de filtrage : combien de titres avant, écartés et conservés à CHAQUE étape, quelle règle, quels titres, et pourquoi un titre précis a disparu.

Deux entonnoirs distincts (les trois niveaux de règles ne se mélangent pas ; le niveau 3, les stratégies, se lit dans l'Explorer) :
  catalogue : FinanceDatabase brut → règles du catalogue → cotations conservées → cotation principale par produit → transmis à Yahoo
  yahoo     : cotations du catalogue → secondaires → réponse de Yahoo → prix → volume → liquidité → éligibles aux analyses
Chaque entonnoir est calculé depuis l'état réel de la base (donc exact après n'importe quel traitement) et figé dans `funnel_steps`
à la fin d'une exécution pour garder le détail de chaque passage. Les titres de chaque étape se consultent (`items`) pour l'état de la dernière exécution.
"""
import datetime

from engine.catalogue import rules as crules
from engine.market import prefilter
from engine.market.collect import latest_rates, to_eur_factor
from engine.shared import settings

PAGE = 50
YAHOO_WHERE = {          # étape → condition SQL sur listings l (alias) : les titres écartés (ou conservés) par cette étape
    'asked': "l.is_primary=1 AND (l.status IN ('candidate','selected') OR l.excluded_reason LIKE 'préfiltre%')",
    'secondary': "l.status IN ('candidate','selected') AND l.is_primary=0",
    'no_data': "l.status='candidate' AND l.is_primary=1",
    'stale': "l.status='excluded' AND l.is_primary=1 AND l.excluded_reason LIKE 'préfiltre : dernier cours%'",
    'price': "l.status='excluded' AND l.is_primary=1 AND l.excluded_reason LIKE 'préfiltre : cours%'",
    'volume': "l.status='excluded' AND l.is_primary=1 AND l.excluded_reason LIKE 'préfiltre : volume%'",
    'liquidity': "l.status='excluded' AND l.is_primary=1 AND l.excluded_reason LIKE 'préfiltre : liquidité%'",
    'final': "l.status='selected' AND l.is_primary=1",
}


def _step(seq, key, label, rule, before, removed, info=None):
    return {'seq': seq, 'key': key, 'label': label, 'rule': rule, 'before': before, 'removed': removed, 'kept': before - removed, 'info': info or {}}


# ───────── catalogue ─────────
def catalogue_funnel(conn, cfg=None):
    cfg = cfg or settings.catalogue_rules(conn)
    with conn.cursor() as cur:
        cur.execute('SELECT removed_step s, kind, COUNT(*) n FROM catalogue_raw GROUP BY removed_step, kind')
        counts = {}
        for r in cur.fetchall():
            counts.setdefault(r['s'], {})[r['kind']] = r['n']
        cur.execute('SELECT COUNT(DISTINCT group_key) n FROM catalogue_raw WHERE removed_step IS NULL')
        products = cur.fetchone()['n']
    total = sum(sum(v.values()) for v in counts.values())
    steps = [_step(0, 'raw', 'Données brutes reçues de FinanceDatabase', 'Fichiers equities et etfs du dépôt FinanceDatabase, avant toute règle', total, 0,
                   {'by_kind': {k: sum(v.get(k, 0) for v in counts.values()) for k in ('equity', 'etf')}})]
    kept = total
    for i, rule in enumerate(crules.RULES, 1):
        by_kind = counts.get(rule['id'], {})
        removed = sum(by_kind.values())
        steps.append(_step(i, rule['id'], rule['label'], crules.rule_text(rule['id'], cfg), kept, removed,
                           {'by_kind': by_kind, 'kinds': list(rule['kinds']), 'enabled': cfg[rule['id']]['enabled'] or bool(rule.get('locked')), 'locked': bool(rule.get('locked')), 'help': rule['help']}))
        kept -= removed
    steps.append(_step(len(steps), 'primary', 'Cotations multiples : une cotation principale par produit', 'Règle R1 : place d’origine du produit, sinon cotation la plus liquide, sinon ordre de priorité des places',
                       kept, kept - products, {'products': products}))
    steps.append(_step(len(steps), 'to_yahoo', 'Titres transmis à Yahoo Finance', 'Cotations principales non exclues, plus les cotations détenues dans un portefeuille', products, 0, {'products': products}))
    return steps


# ───────── Yahoo ─────────
def yahoo_funnel(conn, cfg=None):
    cfg = cfg or settings.prefilter_rules(conn)
    with conn.cursor() as cur:
        counts = {}
        for key, cond in YAHOO_WHERE.items():
            cur.execute(f'SELECT COUNT(*) n FROM listings l WHERE {cond}')
            counts[key] = cur.fetchone()['n']
        cur.execute("""SELECT SUM(p.listing_id IS NULL OR p.quote_at IS NULL) no_quote, SUM(p.listing_id IS NOT NULL AND p.quote_at IS NOT NULL AND p.price IS NULL) no_price
                       FROM listings l LEFT JOIN latest_prices p ON p.listing_id=l.id WHERE l.status='candidate' AND l.is_primary=1""")
        nd = cur.fetchone()
        cur.execute("SELECT COUNT(DISTINCT listing_id) n FROM portfolio_transactions WHERE listing_id IS NOT NULL")
        held = cur.fetchone()['n']
    asked = counts['asked']
    rule = lambda rid: ('Règle désactivée : n’écarte rien' if not cfg[rid]['enabled'] else
                        (f'Seuil : {cfg[rid][prefilter.BY_ID[rid]["key"]]:,.0f} {prefilter.BY_ID[rid]["unit"]}'.replace(',', ' ') if 'key' in prefilter.BY_ID[rid] else prefilter.BY_ID[rid]['role']))
    steps = [_step(0, 'asked', 'Titres transmis par FinanceDatabase', 'Cotation principale de chaque produit retenu par le filtrage FinanceDatabase, plus les titres détenus', asked, 0,
                   {'held': held, 'secondary': counts['secondary']})]
    kept = asked
    nodata = counts['no_data']
    steps.append(_step(1, 'no_data', 'Sans information Yahoo', 'Yahoo n’a renvoyé aucun cours exploitable (ou l’import n’a pas été fait) : le titre reste « en attente », jamais retenu sans donnée',
                       kept, nodata, {'no_quote': int(nd['no_quote'] or 0), 'no_price': int(nd['no_price'] or 0)}))
    kept -= nodata
    for seq, key, rid, label in ((2, 'stale', 'stale', 'Exclus : dernier cours trop ancien'), (3, 'price', 'price', 'Exclus selon le prix'), (4, 'volume', 'unknown_volume', 'Exclus : volume inconnu'), (5, 'liquidity', None, 'Exclus selon la liquidité')):
        removed = counts[key]
        text = rule(rid) if rid else f'Actions ≥ {cfg["liquidity_equity"]["min_eur"]:,.0f} €/jour · ETF ≥ {cfg["liquidity_etf"]["min_eur"]:,.0f} €/jour'.replace(',', ' ') + \
            ('' if cfg['liquidity_equity']['enabled'] and cfg['liquidity_etf']['enabled'] else ' (certaines règles désactivées)')
        steps.append(_step(seq, key, label, text, kept, removed, {'rule_ids': [rid] if rid else ['liquidity_equity', 'liquidity_etf']}))
        kept -= removed
    steps.append(_step(6, 'final', 'Catalogue final', 'Titres retenus : leurs historiques sont importés puis entretenus automatiquement', kept, 0, {}))
    return steps


# ───────── instantanés ─────────
def snapshot(conn, stage, job_id=None):
    steps = catalogue_funnel(conn) if stage == 'catalogue' else yahoo_funnel(conn)
    import json
    now = datetime.datetime.utcnow().replace(microsecond=0)
    with conn.cursor() as cur:
        cur.executemany('INSERT INTO funnel_steps(job_id,stage,seq,step_key,label,rule_text,before_n,removed_n,kept_n,info_json,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                        [(job_id, stage, s['seq'], s['key'], s['label'], s['rule'][:400], s['before'], s['removed'], s['kept'], json.dumps(s['info'], ensure_ascii=False), now) for s in steps])
        # on garde les 12 derniers instantanés de chaque entonnoir
        cur.execute("SELECT DISTINCT created_at FROM funnel_steps WHERE stage=%s ORDER BY created_at DESC LIMIT 12", (stage,))
        keep = [r['created_at'] for r in cur.fetchall()]
        if len(keep) == 12:
            cur.execute('DELETE FROM funnel_steps WHERE stage=%s AND created_at < %s', (stage, keep[-1]))
    conn.commit()
    return steps


def stored(conn, job_id, stage=None):
    import json
    with conn.cursor() as cur:
        cur.execute('SELECT stage, seq, step_key `key`, label, rule_text `rule`, before_n `before`, removed_n removed, kept_n kept, info_json, created_at FROM funnel_steps WHERE job_id=%s ' +
                    ('AND stage=%s ' if stage else '') + 'ORDER BY stage, seq', (job_id, stage) if stage else (job_id,))
        rows = cur.fetchall()
    for r in rows:
        r['info'] = json.loads(r.pop('info_json') or '{}')
    return rows


def last_run(conn, stage):
    """Entonnoir de la dernière exécution qui en a produit un (avec le traitement concerné), sinon l'état actuel."""
    with conn.cursor() as cur:
        cur.execute("""SELECT f.job_id, f.created_at, j.job_type, j.status, j.started_at, j.finished_at FROM funnel_steps f LEFT JOIN jobs j ON j.id=f.job_id
                       WHERE f.stage=%s ORDER BY f.created_at DESC, f.id DESC LIMIT 1""", (stage,))
        last = cur.fetchone()
    live = catalogue_funnel(conn) if stage == 'catalogue' else yahoo_funnel(conn)
    return {'stage': stage, 'steps': live, 'run': last}


# ───────── titres d'une étape ─────────
def _like(q):
    return '%' + q.replace('%', '').replace('_', '').strip() + '%'


def items(conn, stage, step, q='', kind='', mic='', page=1, quality=''):
    page = max(1, int(page))
    rates = latest_rates(conn) if stage == 'yahoo' else None
    where, args = [], []
    if q:
        where.append('(LOWER(NAME_COL) LIKE %s OR LOWER(SYMBOL_COL) LIKE %s OR LOWER(ISIN_COL) LIKE %s)')
        args += [_like(q.lower())] * 3
    if kind:
        where.append('KIND_COL=%s'); args.append(kind)
    if mic:
        where.append('MIC_COL=%s'); args.append(mic)
    extra = ' AND '.join(where)
    with conn.cursor() as cur:
        if stage == 'catalogue':
            if step == 'raw':
                cond = '1=1'
            elif step == 'kept':
                cond = 'r.removed_step IS NULL'
            elif step == 'primary':
                cond = "r.removed_step IS NULL AND NOT EXISTS (SELECT 1 FROM listings l WHERE l.mic=r.mic AND l.symbol=r.symbol AND l.is_primary=1)"
            elif step == 'to_yahoo':
                cond = "EXISTS (SELECT 1 FROM listings l WHERE l.mic=r.mic AND l.symbol=r.symbol AND l.is_primary=1 AND l.status IN ('candidate','selected'))"
            elif step in crules.BY_ID:
                cond = 'r.removed_step=%s'; args = [step] + args
            else:
                raise ValueError('Étape inconnue')
            cond_all = cond + (' AND ' + extra.replace('NAME_COL', 'r.name').replace('SYMBOL_COL', 'r.symbol').replace('ISIN_COL', 'COALESCE(r.isin,"")').replace('KIND_COL', 'r.kind').replace('MIC_COL', 'r.mic') if extra else '')
            cur.execute(f'SELECT COUNT(*) n FROM catalogue_raw r WHERE {cond_all}', args)
            total = cur.fetchone()['n']
            cur.execute(f'SELECT r.kind, r.mic, r.symbol, r.isin, r.name, r.country, r.category, r.currency, r.removed_step, r.removed_reason FROM catalogue_raw r WHERE {cond_all} ORDER BY r.name, r.mic LIMIT {PAGE} OFFSET {(page - 1) * PAGE}', args)
            rows = cur.fetchall()
        else:
            if step not in YAHOO_WHERE:
                raise ValueError('Étape inconnue')
            cond = YAHOO_WHERE[step].replace('%', '%%')
            cond_all = cond + (' AND ' + extra.replace('NAME_COL', 'i.name').replace('SYMBOL_COL', 'l.symbol').replace('ISIN_COL', 'COALESCE(i.isin,"")').replace('KIND_COL', 'i.kind').replace('MIC_COL', 'l.mic') if extra else '')
            join = 'LEFT JOIN series_state s ON s.listing_id=l.id' if step == 'history' else ''
            if step == 'history' and quality:
                cond_all += ' AND COALESCE(s.quality,"none")=%s'; args.append(quality)
            cur.execute(f'SELECT COUNT(*) n FROM listings l JOIN instruments i ON i.id=l.instrument_id {join} WHERE {cond_all}', args)
            total = cur.fetchone()['n']
            cur.execute(f"""SELECT l.id, l.symbol, l.mic, l.currency, l.status, l.excluded_reason, l.is_primary, i.name, i.isin, i.kind, i.country, p.price, p.currency price_currency, p.avg_volume_3m, p.quote_at, p.price_time,
                                   {'s.quality,' if step == 'history' else ''} (SELECT COUNT(*) FROM portfolio_transactions t WHERE t.listing_id=l.id) held
                            FROM listings l JOIN instruments i ON i.id=l.instrument_id LEFT JOIN latest_prices p ON p.listing_id=l.id {join}
                            WHERE {cond_all} ORDER BY i.name, l.mic LIMIT {PAGE} OFFSET {(page - 1) * PAGE}""", args)
            rows = cur.fetchall()
            for r in rows:
                f = to_eur_factor(r['price_currency'] or r['currency'], rates)
                price = None if r['price'] is None else float(r['price'])
                r['price'] = price
                r['price_eur'] = price * f if price is not None and f else None
                r['liquidity_eur'] = price * r['avg_volume_3m'] * f if price is not None and r['avg_volume_3m'] is not None and f else None
                r['held'] = bool(r['held'])
                r['is_primary'] = bool(r['is_primary'])
    return {'total': total, 'page': page, 'pages': max(1, -(-total // PAGE)), 'rows': rows}


# ───────── pourquoi un titre précis a disparu ─────────
def explain(conn, q):
    q = (q or '').strip()
    if len(q) < 2:
        raise ValueError('Saisissez au moins 2 caractères (nom, symbole ou ISIN)')
    ccfg, ycfg = settings.catalogue_rules(conn), settings.prefilter_rules(conn)
    applied = settings.get(conn, 'rules_applied', {})
    pending = {'catalogue': settings.digest(ccfg) != (applied.get('catalogue') or {}).get('hash'), 'yahoo': settings.digest(ycfg) != (applied.get('prefilter') or {}).get('hash')}
    rates = latest_rates(conn)
    with conn.cursor() as cur:
        cur.execute("""SELECT id, kind, mic, symbol, isin, name, country, category, delisted, removed_step, removed_reason FROM catalogue_raw
                       WHERE UPPER(symbol)=%s OR isin=%s OR LOWER(name) LIKE %s ORDER BY (UPPER(symbol)=%s) DESC, name LIMIT 8""", (q.upper(), q.upper(), _like(q.lower()), q.upper()))
        raws = cur.fetchall()
        out = []
        for r in raws:
            trace, removed_at = [], r['removed_step']
            reached = True
            for rule in crules.RULES:
                if removed_at == rule['id']:
                    trace.append({'key': rule['id'], 'label': rule['label'], 'result': 'removed', 'detail': r['removed_reason'], 'rule': crules.rule_text(rule['id'], ccfg)})
                    reached = False
                elif not reached:
                    trace.append({'key': rule['id'], 'label': rule['label'], 'result': 'not_reached', 'detail': 'non évaluée : la ligne a déjà été écartée', 'rule': ''})
                else:
                    on = ccfg[rule['id']]['enabled'] or rule.get('locked')
                    trace.append({'key': rule['id'], 'label': rule['label'], 'result': 'passed', 'detail': 'passe' if on else 'règle désactivée', 'rule': crules.rule_text(rule['id'], ccfg)})
            item = {'raw': {k: r[k] for k in ('kind', 'mic', 'symbol', 'isin', 'name', 'country', 'category')}, 'catalogue': trace, 'listing': None, 'yahoo': []}
            cur.execute("""SELECT l.id, l.status, l.excluded_reason, l.is_primary, l.primary_reason, l.currency, p.price, p.currency price_currency, p.avg_volume_3m, p.quote_at, p.price_time,
                                  (SELECT COUNT(*) FROM portfolio_transactions t WHERE t.listing_id=l.id) held
                           FROM listings l LEFT JOIN latest_prices p ON p.listing_id=l.id WHERE l.mic=%s AND l.symbol=%s""", (r['mic'], r['symbol'][:24]))
            l = cur.fetchone()
            if l and removed_at not in ('incomplete', 'duplicates', 'types', 'markets'):
                price = None if l['price'] is None else float(l['price'])
                f = to_eur_factor(l['price_currency'] or l['currency'], rates)
                pe = price * f if price is not None and f else None
                liq = pe * l['avg_volume_3m'] if pe is not None and l['avg_volume_3m'] is not None else None
                item['listing'] = {'id': l['id'], 'status': l['status'], 'reason': l['excluded_reason'], 'primary': bool(l['is_primary']), 'primary_reason': l['primary_reason'], 'held': bool(l['held']),
                                   'price_eur': pe, 'avg_volume_3m': l['avg_volume_3m'], 'liquidity_eur': liq}
                y = item['yahoo']
                if l['status'] == 'excluded' and not (l['excluded_reason'] or '').startswith(prefilter.PREFIX):
                    y.append({'key': 'catalogue', 'label': 'Écartée par le catalogue', 'result': 'removed', 'detail': l['excluded_reason']})
                else:
                    y.append({'key': 'secondary', 'label': 'Cotation principale du produit', 'result': 'passed' if (l['is_primary'] or l['status'] == 'excluded') else 'removed',
                              'detail': ('cotation principale' if l['is_primary'] else 'cotation secondaire : le produit est suivi sur une autre place') if l['status'] != 'excluded' else 'principale au moment de la décision'})
                    if l['status'] == 'candidate' and l['is_primary']:
                        y.append({'key': 'no_data', 'label': 'Cours reçu de Yahoo', 'result': 'removed', 'detail': 'aucun cours exploitable : le titre reste candidat'})
                    elif l['status'] != 'candidate':
                        step = prefilter.step_of(l['excluded_reason'])
                        pm, vm = ycfg['price']['min_eur'], None
                        y.append({'key': 'no_data', 'label': 'Cours reçu de Yahoo', 'result': 'passed', 'detail': f'{pe:,.2f} €'.replace(',', ' ') if pe is not None else 'oui'})
                        age = (datetime.datetime.utcnow() - l['price_time']).total_seconds() / 86400 if l['price_time'] else None
                        mx = ycfg['stale']['max_days']
                        y.append({'key': 'stale', 'label': 'Dernier cours récent', 'result': 'removed' if step == 'stale' else 'passed',
                                  'detail': ('âge inconnu' if age is None else f'{age:.0f} jours ') + (f'> {mx:g} jours' if step == 'stale' else f'≤ {mx:g} jours' if ycfg['stale']['enabled'] and age is not None else '(règle désactivée)' if not ycfg['stale']['enabled'] else '')})
                        y.append({'key': 'price', 'label': 'Prix minimum', 'result': 'removed' if step == 'price' else 'passed',
                                  'detail': (f'{pe:,.2f} € ' if pe is not None else '') + (f'< {pm:g} €' if step == 'price' else f'≥ {pm:g} €' if ycfg['price']['enabled'] else 'règle désactivée')})
                        y.append({'key': 'volume', 'label': 'Volume moyen connu', 'result': 'removed' if step == 'volume' else 'passed',
                                  'detail': 'volume inconnu' if l['avg_volume_3m'] is None else f'{l["avg_volume_3m"]:,} titres/jour'.replace(',', ' ')})
                        rid = 'liquidity_etf' if r['kind'] == 'etf' else 'liquidity_equity'
                        mn = ycfg[rid]['min_eur']
                        y.append({'key': 'liquidity', 'label': 'Liquidité minimale', 'result': 'removed' if step == 'liquidity' else 'passed',
                                  'detail': (f'{liq:,.0f} €/jour ' if liq is not None else '') + (f'< {mn:,.0f} €' if step == 'liquidity' else f'≥ {mn:,.0f} €' if ycfg[rid]['enabled'] else '(règle désactivée)')})
                        y[-1]['detail'] = y[-1]['detail'].replace(',', ' ')
                        if l['status'] == 'selected':
                            y.append({'key': 'final', 'label': 'Catalogue final', 'result': 'passed' if l['is_primary'] else 'removed', 'detail': 'oui' if l['is_primary'] else 'non : cotation secondaire'})
            out.append(item)
    return {'query': q, 'results': out, 'pending': pending}
