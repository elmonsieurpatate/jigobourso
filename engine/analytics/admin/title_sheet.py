"""Fiche d'un titre (page `titre.html`) : verdict, signaux, tradabilité, contexte, profil ETF et scores V4."""
import datetime
import json
import re
from collections import defaultdict
from engine.catalogue.rules import MARKETS, is_leveraged_name
from engine.shared import settings as settings_mod
from engine.market import hours
from engine.market.collect import latest_rates, to_eur_factor
from engine.market.calendar import window_calendars, session_dates
from ..series import signals
from ..explorer import strategy
from ..explorer import explorer_config
from ..series.series import analyze_series, prepare_series, data_corrections
from .universe_verdicts import expanded_parts, extended_metrics, judge_universe
from .service import STATUS_LABELS, request_config, reference_window, scoped_entries
from ..market_views.market_facts import analyst_view, expected_close, last_collection, pea_status, size_class

def instrument_sheet(conn, request):
    """Fiche complète d'une cotation : identité, prix, verdict détaillé (toutes périodes, même inactives), séries, qualité."""
    config = request_config(request)
    lid = int(request['listing_id'])
    rates = latest_rates(conn)
    with conn.cursor() as cur:
        cur.execute("""SELECT l.id, l.symbol, l.mic, l.currency, l.status, l.excluded_reason, l.is_primary, l.primary_reason, i.id AS instrument_id, i.name, i.isin, i.kind, i.country, i.category,
                              p.price, p.price_time, p.quote_at, p.source AS price_source, p.currency AS price_currency, p.avg_volume_3m, p.avg_volume_10d, p.market_cap, p.analyst_rating
                       FROM listings l JOIN instruments i ON i.id=l.instrument_id LEFT JOIN latest_prices p ON p.listing_id=l.id WHERE l.id=%s""", (lid,))
        u = cur.fetchone()
        if not u:
            return {'error': 'Titre introuvable'}
        cur.execute('SELECT price_date, close_px, adj_close_px, volume FROM daily_prices WHERE listing_id=%s ORDER BY price_date', (lid,))
        rows = cur.fetchall()
        daily = [[r['price_date'].isoformat(), float(r['close_px'])] for r in rows]
        daily_volume = [None if r['volume'] is None else int(r['volume']) for r in rows]
        cur.execute("""SELECT l.id, l.mic, l.symbol, l.currency, l.status, l.is_primary FROM listings l WHERE l.instrument_id=%s AND l.id<>%s ORDER BY l.is_primary DESC, l.mic""", (u['instrument_id'], lid))
        siblings = cur.fetchall()
        cur.execute('SELECT quality, closes_count, last_close_date, ma20, ma50, ma50_prev, daily_change, gap_to_ma20, break_dates, coverage_252, observed_252, expected_252, momentum_6m, momentum_12m FROM series_state WHERE listing_id=%s', (lid,))
        state = cur.fetchone() or {}
    price = float(u['price']) if u['price'] is not None else None
    factor = to_eur_factor(u['price_currency'] or u['currency'], rates)
    sheet = {'id': lid, 'symbol': u['symbol'], 'name': u['name'], 'isin': u['isin'], 'kind': u['kind'], 'category': u['category'], 'country': u['country'],
             'mic': u['mic'], 'market': MARKETS.get(u['mic'], u['mic']), 'currency': u['price_currency'] or u['currency'], 'price': price,
             'price_eur': price * factor if price is not None and factor else None, 'price_time': u['price_time'].isoformat(sep=' ') if u['price_time'] else None,
             'price_source': u['price_source'], 'avg_volume_3m': u['avg_volume_3m'], 'market_cap': u['market_cap'],
             'market_cap_class': None if u['kind'] != 'equity' else size_class(u['market_cap'], u['price_currency'] or u['currency'], rates),
             'analyst': analyst_view(u['analyst_rating']) if u['kind'] == 'equity' else None,
             'catalogue_status': u['status'], 'excluded_reason': u['excluded_reason'], 'is_primary': bool(u['is_primary']),
             'other_listings': [{'id': s['id'], 'mic': s['mic'], 'symbol': s['symbol'], 'currency': s['currency'], 'status': s['status'], 'is_primary': bool(s['is_primary'])} for s in siblings],
             'daily': daily[-400:], 'daily_volume': daily_volume[-400:], 'state': {k: (float(v) if hasattr(v, 'as_integer_ratio') and not isinstance(v, int) else v) for k, v in state.items() if k != 'break_dates'},
             'break_dates': state.get('break_dates')}
    sheet.update(_sheet_context(conn, u, state, daily))
    # Verdict : uniquement pour une cotation recommandable ; sinon la fiche explique pourquoi elle ne l'est pas.
    all_windows = sorted({1, 5, 21, 63, 126, 252} | {p['sessions'] for p in config['periods']})
    bars = [(r['price_date'].isoformat(), float(r['close_px']), None if r['adj_close_px'] is None else float(r['adj_close_px'])) for r in rows]
    with conn.cursor() as cur:
        cur.execute("SELECT event_date, ratio FROM corporate_events WHERE listing_id=%s AND kind IN ('split','reverse_split')", (lid,))
        splits = [(r['event_date'].isoformat(), float(r['ratio']) if r['ratio'] else None) for r in cur.fetchall()]
    cutoff = expected_close(conn, u['mic'])
    calendars = window_calendars(u['mic'], cutoff, all_windows) if cutoff else {}
    tech_dates = session_dates(u['mic'], cutoff, 205 if config.get('version')==4 else 55) if cutoff else None
    dates, closes, basis, breaks, full, missing, tech = analyze_series(bars, all_windows, splits, calendars, tech_dates)
    if config.get('version')==4 and explorer_config.needs_extended(config):
        extras=extended_metrics(conn,[u],all_windows).get(lid,{})
        full={n:dict(m,**extras.get(n,{})) if m else None for n,m in full.items()}
    sheet['measures'] = {str(n):dict(m,slope_period=explorer_config.period_slope(m.get('slope'),n)) if m else None for n,m in full.items()}
    sheet['analysis_windows']={str(n):ds for n,ds in calendars.items()}
    sheet['window_coverage'] = {str(n): {k: m.get(k) for k in ('observations', 'expected_closes', 'missing_sessions', 'coverage')}
                                for n, m in full.items() if m and m.get('coverage') is not None}
    sheet['analysis_basis'] = basis
    chart_dates, chart_closes, _, chart_breaks = prepare_series(bars, splits)
    volumes = dict(zip((d for d, _ in daily), daily_volume))
    sheet['daily_raw'] = sheet['daily']
    sheet['daily'] = [[d, c] for d, c in zip(chart_dates, chart_closes)][-400:]
    sheet['daily_volume'] = [volumes.get(d) for d, _ in sheet['daily']]
    sheet['chart_break_dates'] = [chart_dates[i] for i in chart_breaks]
    sheet['data_corrections'] = data_corrections(bars, splits)
    sheet['price_stale'] = hours.price_is_stale(u['mic'], u['price_time'], hours.utcnow(), expected_close(conn, u['mic']), last_collection(conn, u['mic']))
    if sheet['freshness']['stale']:
        sheet['state']['quality'] = 'stale'
    elif state.get('quality') not in ('break', 'insufficient') and (missing or any((m or {}).get('coverage') is not None and (m or {}).get('coverage') < 1 for m in full.values())):
        sheet['state']['quality'] = 'incomplete' if any((m or {}).get('coverage') is not None and (m or {}).get('coverage') < 1 for m in full.values()) else 'calendar_unknown'

    sheet['missing_measures'] = {str(n): why for n, why in missing.items()}
    sheet['signals'] = _sheet_signals(conn, sheet, u, config, chart_closes, state)
    sheet['assessment'] = signals.assessment(sheet['measures'], reference_window(config), sheet['signals'])         # descriptive : aucun effet sur le score, le filtre ni le classement
    sheet['tradability'] = _sheet_tradability(conn, u, rates)
    if u['status'] == 'selected' and u['is_primary']:
        view = request.get('view') or {}
        entries, scoped, _, _ = scoped_entries(conn, config, view)      # même moteur que l'Explorer : mêmes filtres, mêmes critères, même classement
        mine = next((e for e in scoped if e['id'] == lid), None)
        v = judge_universe(conn, config, [lid])[0]
        group = 'etf' if u['kind'] == 'etf' else 'equity'
        sheet['verdict'] = {'score_parts':expanded_parts(mine or {},config),'status': v['status'], 'status_label': STATUS_LABELS[v['status']], 'score': mine['score'] if mine else None, 'rank': mine['rank'] if mine else None,
                            'of': sum(1 for e in scoped if e['group'] == group and e['status'] == 'retained'), 'in_scope': mine is not None,
                            'scope_filtered': len(scoped) != len(entries), 'examined': len(scoped), 'universe': len(entries), 'reasons': v['reasons']}
    elif u['status'] == 'excluded':
        sheet['verdict'] = {'status': 'excluded', 'status_label': STATUS_LABELS['excluded'], 'note': u['excluded_reason'] or 'Exclu des recommandations.'}
    elif u['status'] == 'selected':
        sheet['verdict'] = {'status': 'unknown', 'status_label': 'Cotation secondaire', 'note': 'Ce produit est analysé sur sa cotation principale (voir « Autres cotations »).'}
    else:
        sheet['verdict'] = {'status': 'unknown', 'status_label': 'Non analysé', 'note': 'Aucune cotation Yahoo exploitable pour le moment : ce titre n’est pas encore analysé.'}
    if u['kind'] == 'etf':
        sheet['etf_profile'] = _etf_profile(conn, lid, u['symbol'], bool(request.get('fetch_profile')))     # une seule requête Yahoo, pour l'ETF ouvert, profil de plus de 30 jours ou d'ancienne version
        from ..market_views import etf
        sheet['etf_analysis'] = etf.load(conn, [lid]).get(lid)
        sheet['etf_compare'] = etf.compare(conn, lid)
    sheet['strategy'] = {'name': config.get('name'), 'ranking': config['ranking']['mode'], 'source': request.get('source') or None, 'experimental': config.get('name') in strategy.EXPERIMENTAL or config['ranking']['mode'] in strategy.MOMENTUM_WINDOWS or config['ranking']['mode'] == strategy.RISK_MOMENTUM,
                         'technical': {k: v for k, v in config['technical'].items() if v},
                         'periods': [{'id': p['id'], 'label': strategy.LABELS[p['id']], 'sessions': p['sessions'], 'criteria': {f: p.get(f) for f, _, _ in (explorer_config.CRITERIA if config.get('version')==4 else strategy.CRITERIA) if p.get(f) is not None}} for p in config['periods'] if p['enabled']]}
    sheet['config_periods'] = [{'id': p['id'], 'label': strategy.LABELS[p['id']], 'sessions': p['sessions'], 'enabled': p['enabled']} for p in config['periods']]
    ct = request.get('ct') or {}
    sheet['scores_v4'] = _scores_v4(conn, lid, ct)
    sheet['v4'] = _v4_strategy(conn, lid, ct)
    return sheet


LEVERAGE = re.compile(r'\b(bull|[235]x|x[235]|-[123]x)\b|levier|effet de levier', re.I)       # compléments de rules.is_leveraged_name pour l'avertissement de la fiche


US_NAME = re.compile(r'\b(s&p ?500|nasdaq|russell|dow jones|u\.?s\.?a?\b|united states|america)', re.I)


EUROPEAN_MICS = {'XETR', 'XPAR', 'XAMS', 'XLON', 'XMIL', 'XMAD', 'XSTO', 'XOSL', 'XSWX', 'XBRU', 'XLIS', 'XHEL', 'XCSE', 'XWBO', 'XDUB'}


def _bar_coverage(conn, lid, mic, sessions=5):
    """Part des créneaux de 15 min qui ont une bougie, sur les dernières séances qui en ont au moins une. Indicateur complémentaire : une bougie manquante n'est PAS une absence d'échange
    (le fournisseur renvoie des données incomplètes). None si les horaires ou les barres manquent."""
    from engine.market import intraday
    if not hours.known(mic):
        return None
    tz = hours.spec(mic)[0]
    since = hours.utcnow().replace(tzinfo=None) - datetime.timedelta(days=14)
    with conn.cursor() as cur:
        cur.execute('SELECT slot_start FROM intraday_prices WHERE listing_id=%s AND slot_start>=%s', (lid, since))
        slots = [r['slot_start'] for r in cur.fetchall()]
    by_day = defaultdict(set)
    for t in slots:
        by_day[intraday.local_day(t, tz)].add(t)
    days = sorted(by_day)[-sessions:]
    if len(days) < 2:
        return None
    expected = sum(len(intraday.expected_slot_starts(mic, d)) for d in days)
    have = sum(len(by_day[d] & set(intraday.expected_slot_starts(mic, d))) for d in days)
    return {'sessions': len(days), 'share': round(have / expected, 2) if expected else None}


def _activity_note(u):
    """Compare le volume moyen des 10 derniers jours à celui de 3 mois. Information pédagogique : ne modifie ni le filtre ni ses seuils."""
    v3, v10 = u.get('avg_volume_3m'), u.get('avg_volume_10d')
    if not v3 or v10 is None:
        return []
    ratio = v10 / v3
    if 0.67 <= ratio <= 1.5:
        return []
    word = ('plus actif' if ratio > 1 else 'moins actif')
    return ['Activité récente : volume moyen sur 10 jours de %s titres par jour contre %s sur 3 mois (×%s). Le titre est %s que d’habitude. '
            'Plus de volume ne veut pas dire meilleure liquidité durable, ni moindre volatilité.' % (_n(v10), _n(v3), ('%.1f' % ratio).replace('.', ','), word)]


def _n(x):
    return f'{int(x):,}'.replace(',', ' ')


def _sheet_tradability(conn, u, rates):
    """Explique le statut de négociabilité d'un titre, avec le MÊME calcul que le filtre « Titres facilement négociables » et la pastille du classement."""
    f = to_eur_factor(u['price_currency'] or u['currency'], rates)
    price_eur = None if u['price'] is None or not f else float(u['price']) * f
    daily = price_eur * u['avg_volume_3m'] if price_eur is not None and u['avg_volume_3m'] else None
    age = None if u['quote_at'] is None else max(0.0, (hours.utcnow().replace(tzinfo=None) - u['quote_at']).total_seconds() / 86400)
    sig = signals.liquidity(daily, u['kind'], settings_mod.prefilter_rules(conn), age)
    v, level = sig['values'], sig['level']
    where = 'Pour le retrouver dans les classements, décochez « Titres facilement négociables ».'
    if level == 'bad':
        text = (f'Ce titre n’apparaît pas dans les classements quand le filtre « Titres facilement négociables » est activé : sa valeur quotidienne échangée estimée est de '
                f'{signals._eur(daily)} (seuil : {signals._eur(v["floor_eur"])}). {where}')
    elif level == 'warn':
        text = f'Valeur quotidienne échangée estimée : {signals._eur(daily)}, entre {signals._eur(v["floor_eur"])} et {signals._eur(v["comfort_eur"])}. Le titre reste dans les classements, avec une pastille de vigilance : un ordre important peut être exécuté à un prix moins favorable.'
    elif level == 'ok':
        text = f'Valeur quotidienne échangée estimée : {signals._eur(daily)}. Cela n’assure pas qu’un ordre précis sera facile à revendre.'
    else:
        text = ('Nous ne disposons pas de données suffisamment fiables pour évaluer la facilité d’achat ou de revente de ce titre. Son absence éventuelle des résultats filtrés ne signifie pas qu’il est peu liquide.'
                if sig['reason'] == 'missing' else
                f'Les données de volume de ce titre datent de {age:.0f} jours : nous ne pouvons pas évaluer sa négociabilité. Son absence éventuelle des résultats filtrés ne signifie pas qu’il est peu liquide.')
    notes = []
    cov = _bar_coverage(conn, u['id'], u['mic'])
    if cov and cov['share'] is not None and cov['share'] < 0.7:
        notes.append(f'Cotations intrajournalières espacées : {round(100 * cov["share"])} % des créneaux de 15 minutes ont une bougie sur les {cov["sessions"]} dernières séances. '
                     'Les créneaux sans bougie ne prouvent pas à eux seuls une mauvaise liquidité : le fournisseur peut renvoyer des données incomplètes.')
    if u['kind'] == 'etf' and u['mic'] in EUROPEAN_MICS and US_NAME.search(u['name'] or ''):
        notes.append('D’après son nom, cet ETF suit des actions américaines : ses échanges peuvent être moins fréquents avant l’ouverture de Wall Street. Cela ne signifie pas à lui seul une mauvaise liquidité.')
    notes.extend(_activity_note(u))
    return {'level': level, 'label': sig['label'], 'text': text, 'notes': notes, 'hidden_by_filter': level == 'bad', 'reason': sig.get('reason'),
            'values': {'daily_eur': None if daily is None else round(daily), 'avg_volume_3m': u['avg_volume_3m'], 'avg_volume_10d': u.get('avg_volume_10d'), 'floor_eur': v['floor_eur'], 'comfort_eur': v['comfort_eur'],
                       'volume_at': u['quote_at'].isoformat(sep=' ') if u['quote_at'] else None},
            'source': 'Volume moyen sur 3 mois × cours (estimation Yahoo, pas du volume exécuté).'}


def _sheet_signals(conn, sheet, u, config, closes, state):
    """« Lecture rapide » de la fiche : mêmes seuils que les pastilles du classement, avec les détails pédagogiques de la V1 (séances en hausse, poids du meilleur jour)."""
    from ..series import signals
    ref = reference_window(config)
    m = (sheet.get('measures') or {}).get(str(ref)) or {}
    facts = signals.history_facts(closes, ref) if m.get('coverage') in (None, 1.0) else {}
    quality = 'incomplete' if m.get('coverage') is not None and m.get('coverage') < 1 else state.get('quality')
    price_eur, vol = sheet.get('price_eur'), u.get('avg_volume_3m')
    out = [signals.regularity(m.get('r2'), ref, signals.regularity_extra(facts)), signals.risk(m.get('volatility'), m.get('drawdown'), ref),
           signals.liquidity(price_eur * vol if price_eur is not None and vol else None, u['kind'], settings_mod.prefilter_rules(conn), None if not u.get('quote_at') else max(0.0, (hours.utcnow().replace(tzinfo=None) - u['quote_at']).total_seconds() / 86400)),
           signals.data_quality(quality, sheet.get('data_corrections'), sheet.get('price_stale'), state.get('break_dates'),
                                m.get('coverage', state.get('coverage_252')), m.get('observations', state.get('observed_252')),
                                m.get('expected_closes', state.get('expected_252')))]
    if u['kind'] == 'etf':
        from ..market_views import etf
        analysis = etf.load(conn, [u['id']]).get(u['id'])
        prof = (sheet.get('etf_profile') or {}).get('data') or {}
        out += [signals.similarity(analysis), signals.composition(prof),
                signals.specific_risks(u['name'], u['category'], is_leveraged_name(' '.join(filter(None, [u['name'], u['category']]))))]
    return out


def _sheet_context(conn, u, state, daily):
    """Sources, fraîcheur, éligibilité PEA probable, avertissement produit : tout ce qui situe la donnée."""
    with conn.cursor() as cur:
        cur.execute('SELECT source_commit, loaded_at FROM catalogue_loads ORDER BY id DESC LIMIT 1')
        cat = cur.fetchone()
        cur.execute("SELECT job_type, status, started_at, finished_at FROM jobs WHERE job_type IN (%s,%s) AND status IN ('completed','completed_with_errors') ORDER BY id DESC LIMIT 2",
                    ('daily:' + u['mic'], 'intraday:' + u['mic']))
        collects = {r['job_type'].split(':')[0]: (r['finished_at'] or r['started_at']).isoformat(sep=' ') for r in cur.fetchall()}
        cur.execute('SELECT MAX(last_close_date) d FROM series_state s JOIN listings l ON l.id=s.listing_id WHERE l.mic=%s', (u['mic'],))
        peer_date = cur.fetchone()['d']
        expected = max(expected_close(conn, u['mic']), str(peer_date or ''))
    pea = pea_status(u['kind'], u['country'], u['mic']) == 'probable'
    warn = None
    text = ' '.join(filter(None, [u['name'], u['category']]))
    if u['kind'] == 'etf' and (is_leveraged_name(text) or LEVERAGE.search(text)):
        warn = 'Ce produit semble à effet de levier ou inversé (d’après son nom). Les effets cumulés quotidiens peuvent différer fortement de l’indice : vérifiez son document d’information.'
    last = state.get('last_close_date')
    return {'pea': {'status': 'probable' if pea else ('a_verifier' if u['kind'] == 'etf' else 'non'),
                    'note': 'Action d’une société de l’Espace économique européen, cotée sur une place européenne : éligibilité PEA probable, à confirmer chez le courtier.' if pea else
                            ('Éligibilité PEA d’un ETF : dépend de son indice et de son domicile, à vérifier dans son document d’information.' if u['kind'] == 'etf' else 'Émetteur hors des pays éligibles, ou action cotée hors d’Europe : pas éligible au PEA par défaut.')},
            'product_warning': warn,
            'sources': {'catalogue': 'FinanceDatabase', 'catalogue_loaded_at': cat['loaded_at'].isoformat(sep=' ') if cat else None, 'catalogue_commit': (cat['source_commit'][:8] if cat else None),
                        'prices': 'Yahoo Finance', 'last_daily_collect': collects.get('daily'), 'last_intraday_collect': collects.get('intraday')},
            'freshness': {'last_close_date': last.isoformat() if last else None, 'market_latest_close': expected or None,
                          'closes_count': state.get('closes_count'), 'first_close_date': daily[0][0] if daily else None, 'stale': bool(last and expected and str(last) < expected)}}


PROFILE_MAX_AGE_DAYS = 30


def _etf_profile(conn, listing_id, symbol, allow_fetch):
    """Fiche pédagogique en cache ; rafraîchie à la demande (au plus tous les 30 jours, une tentative par jour en cas d'échec)."""
    from engine.market import etf_profile
    from engine.market.yahoo import YahooClient
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None, microsecond=0)
    with conn.cursor() as cur:
        cur.execute('SELECT fetched_at, version, state, data_json FROM etf_profiles WHERE listing_id=%s', (listing_id,))
        row = cur.fetchone()
    fresh_days = PROFILE_MAX_AGE_DAYS if row and row['state'] == 'ok' else 1
    if allow_fetch and (not row or row['version'] != etf_profile.VERSION or (now - row['fetched_at']).days >= fresh_days):
        try:
            data, state = etf_profile.fetch_profile(YahooClient().transport, symbol), 'ok'
            if data is None:
                state = 'unavailable'
        except Exception:
            data, state = None, 'unavailable'
        if state == 'ok' or not row:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO etf_profiles(listing_id,fetched_at,version,state,data_json) VALUES (%s,%s,%s,%s,%s)
                               ON DUPLICATE KEY UPDATE fetched_at=VALUES(fetched_at), version=VALUES(version), state=VALUES(state), data_json=VALUES(data_json)""",
                            (listing_id, now, etf_profile.VERSION, state, json.dumps(data or {})))
            conn.commit()
            return {'state': state, 'fetched_at': now.isoformat(sep=' '), 'data': data}
    if row:
        from ..market_views.etf import profile_data
        data = profile_data(json.loads(row['data_json']) or {})
        if row['version'] < 2:
            data['holdings'] = [dict(h, weight=None if h['weight'] == 0 else h['weight']) for h in data['holdings']]
            data = profile_data(data)
        return {'state': row['state'], 'fetched_at': row['fetched_at'].isoformat(sep=' '), 'data': data}
    return {'state': 'none', 'fetched_at': None, 'data': None}


def _scores_v4(conn, lid, ct=None):
    """Scores V4 du titre (simple, complexe, rangs généraux, contributions) avec la stratégie V4 du contexte (celle du Classement dont la fiche est ouverte) ; None si le titre n'est pas noté. Lecture seule.
    Mêmes scores et mêmes rangs que le Classement : retenu ou exclu, la note et le rang ne changent pas."""
    from ..scoring import scores
    from . import scores_admin
    ct = ct or {}
    name = 'growth_v4'
    if ct.get('id'):
        scores_admin.refresh(conn)
        name = scores_admin.resolve(conn, ct['id'], int(ct.get('user_id') or 0))
        name = name if scores_admin.known(name) else 'growth_v4'
    try:
        sim = scores_admin.simulate(conn, {'strategy': name, 'listing_id': lid})
    except Exception:                                                                        # noqa: BLE001 : la fiche reste complète sans ce bloc
        return None
    result = sim.get('result')
    if not result:
        return None
    return {'strategy': name, 'ranks': sim.get('ranks'), 'simple': result['simple'], 'complex': result['complex'], 'liquidity': result.get('liquidity'),
            'labels': scores.COMPLEX_LABELS, 'weights_effective': result.get('weights_effective'), 'periods': [dict(id=p['id'], sessions=p['sessions']) for p in sim.get('periods', [])]}


V4_STATUS_LABELS = {'retained': 'Retenue', 'excluded': 'Exclue', 'undetermined': 'Indéterminée'}


def _v4_strategy(conn, lid, ct):
    """Verdict de la stratégie du Classement pour ce titre : même moteur (`criteria`) et mêmes mesures (`strategy_metrics`) que le tableau. Sans contexte fiable : indéterminé, jamais « retenue »."""
    from ..scoring import criteria as CR
    from ..scoring import ranking_table
    ct = ct or {}
    ct_id, state = ct.get('id'), ct.get('state') or 'missing'
    base = {'id': ct_id, 'label': ct.get('label'), 'state': state, 'checks': [], 'active': 0, 'join': None}
    if not ct_id or state in ('missing', 'draft_lost'):
        return dict(base, context='missing', status='undetermined', status_label=V4_STATUS_LABELS['undetermined'], reason='context_missing')
    norm = ranking_table.norm_of({'ct_id': ct_id, 'spec': ct.get('spec')})
    if norm is None:
        return dict(base, context='missing', state='missing', status='undetermined', status_label=V4_STATUS_LABELS['undetermined'], reason='context_missing')
    data = ranking_table._fetch(conn, [lid]).get(lid) or {}
    ev = CR.evaluate(norm, {'m': data.get('m'), 'avg_volume': data.get('avg_volume_3m')})
    return dict(base, context='ok', status=ev['status'], status_label=V4_STATUS_LABELS[ev['status']], checks=ev['checks'], active=ev['active'], join=ev['join'], reason=ev['reason'],
                criteria_free=ev['active'] == 0)
