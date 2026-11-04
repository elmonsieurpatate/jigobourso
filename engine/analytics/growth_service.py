"""V4 orchestration: shared price engine; cached scores before presentation."""
import copy
import datetime as dt
import hashlib
import json
import math

from . import growth, service, explorer_config as C
from engine.shared import settings
from engine.market.calendar import window_calendars


def configuration(conn):
    return growth.validate_settings(settings.get(conn,'explorer_growth',growth.defaults()))


def administration(conn, request):
    action=request.get('action','get')
    if action=='reset':
        value=growth.defaults();settings.put(conn,'explorer_growth',value)
    elif action in ('save','preview'):
        value=growth.validate_settings(request.get('settings'))
        if action=='save':settings.put(conn,'explorer_growth',value)
    elif action=='get':value=configuration(conn)
    else:raise ValueError('Action de réglage inconnue')
    return dict(settings=value,proposed=growth.defaults(),preset=growth.preset(value),
                origin='admin' if settings.get(conn,'explorer_growth') is not None else 'proposition code',
                formula=growth.VERSION,intervals='borne basse exclue, borne haute incluse ; inconnu distinct')


def _json_default(value):
    if isinstance(value,(dt.datetime,dt.date)):return value.isoformat()
    return float(value)


def financial_rows(conn, config):
    # Full financial configuration only. Categories, filters and page never enter
    # this key. A history fingerprint also detects changes without a finished job.
    with conn.cursor() as q:
        q.execute("SELECT listing_id,COUNT(*) n,MAX(price_date) d,SUM(CRC32(CONCAT(price_date,':',close_px,':',COALESCE(adj_close_px,'NULL'),':',COALESCE(volume,'NULL')))) checksum FROM daily_prices GROUP BY listing_id ORDER BY listing_id")
        history=q.fetchall()
        q.execute('SELECT listing_id,event_date,kind,ratio FROM corporate_events ORDER BY listing_id,event_date,kind')
        events=q.fetchall()
        q.execute('SELECT currency,rate_date,to_eur FROM fx_rates ORDER BY currency,rate_date');fx=q.fetchall()
        q.execute('SELECT id,status,is_primary FROM listings ORDER BY id');universe=q.fetchall()
        q.execute('SELECT listing_id,price,currency,price_time,quote_at,avg_volume_3m FROM latest_prices ORDER BY listing_id');quotes=q.fetchall()
    fingerprint=hashlib.sha256(json.dumps([history,events,fx,universe,quotes],default=_json_default,sort_keys=True).encode()).hexdigest()
    version=hashlib.sha256((service.data_version(conn)+'|'+fingerprint).encode()).hexdigest()
    key=hashlib.sha1(('growth-1:'+json.dumps(config,sort_keys=True)).encode()).hexdigest()
    with conn.cursor() as q:
        q.execute('SELECT payload,data_version FROM result_cache WHERE cache_key=%s',(key,));hit=q.fetchone()
    if hit and hit['data_version']==version:return service.unpacked(hit['payload']),version
    with conn.cursor() as q:
        q.execute('SELECT COUNT(*) n FROM result_cache WHERE built_at>%s',(dt.datetime.utcnow()-dt.timedelta(hours=1),))
        if q.fetchone()['n']>=service.MAX_NEW_CONFIGS_PER_HOUR:raise ValueError('Limite de calcul atteinte : réutilisez un réglage appliqué ou réessayez plus tard')
    # Prevent an obsolete path cache surviving a manual history repair. The
    # underlying measurements are still obtained through the existing loader.
    verdicts=service.judge_universe(conn,config)
    rates=service.latest_rates(conn);rows=[];calendars={}
    for v in verdicts:
        u=v['row'];row=service._row(v,rates)
        if u['mic'] not in calendars:
            calendars[u['mic']]=window_calendars(u['mic'],service.expected_close(conn,u['mic']),[1,5,21,63])
        row.update(scores=v['scores'],windows={str(n):ds for n,ds in calendars[u['mic']].items()},last_close_date=str(u['last_close_date']) if u['last_close_date'] else None,
                   proximity=service.criteria_proximity(v['reasons']),
                   quoted_avg_volume=None if u.get('avg_volume_3m') is None else float(u['avg_volume_3m']))
        rows.append(row)
    with conn.cursor() as q:
        q.execute('REPLACE INTO result_cache(cache_key,data_version,built_at,payload) VALUES (%s,%s,%s,%s)',
                  (key,version,dt.datetime.utcnow(),service.packed(rows)))
        q.execute('DELETE FROM result_cache WHERE built_at<%s',(dt.datetime.utcnow()-dt.timedelta(days=3),))
    conn.commit()
    return rows,version


def _reference(config):
    return max(p['sessions'] for p in config['periods'] if p['enabled'] and p['id'] in growth.PRIMARY)


def decorate(row, config, params):
    row=copy.deepcopy(row);n=_reference(config);m=row['measures'].get(str(n)) or {}
    values=dict(m)
    expected=(row['windows'].get(str(n)) or row['windows'].get(n) or [None])[-1]
    values['freshness']=None if not row.get('last_close_date') or not expected else float(row['last_close_date']<expected)
    values['quality']=None if not m else 2 if row['quality']=='break' else 0 if m.get('coverage')==1 else 1
    # Never substitute this provider metadata for a historical series measure.
    price=row.get('price_eur');volume=row.get('quoted_avg_volume')
    values['quoted_turnover']=price*volume if price is not None and volume is not None else None
    if row.get('price_stale'):values['quoted_turnover']=None
    row['badges']={k:growth.classify(values.get(k),cat) for k,cat in params['categories'].items()}
    row['secondary_reference']=dict(sessions=n,dates=row['windows'].get(str(n)) or row['windows'].get(n),
                                   source='historiques Yahoo stockés ; montant coté : métadonnée Yahoo trois mois')
    month=row['measures'].get('21') or {};week=row['measures'].get('5') or {};day=row['measures'].get('1') or {}
    share=month.get('log_net_share')
    gates=[('jour > 0 %',day.get('perf'),0,'>'),('semaine ≥ 3 %',week.get('perf'),3,'>='),
           ('mois ≥ 8 %',month.get('perf'),8,'>='),('R² mois ≥ 0,60',month.get('r2'),.6,'>='),
           ('meilleur jour log / gain net log ≤ 45 %',share,45,'<=')]
    checks=[]
    for label,value,threshold,op in gates:
        state='unknown' if value is None else ('pass' if (value>threshold if op=='>' else value>=threshold if op=='>=' else value<=threshold) else 'fail')
        checks.append(dict(label=label,value=value,threshold=threshold,operator=op,status=state))
    row['v1_comparison']=dict(scope='Critères de trajectoire V1 seulement, sans univers, volumes, actualités ni avis V1',
                              checks=checks,status='fail' if any(c['status']=='fail' for c in checks) else 'unknown' if any(c['status']=='unknown' for c in checks) else 'pass')
    row['slope_changes']=[dict(short=a,long=b,value=(row['measures'].get(str(a)) or {}).get('slope')-(row['measures'].get(str(b)) or {}).get('slope'))
                           for a,b in [(5,21),(21,63)] if (row['measures'].get(str(a)) or {}).get('slope') is not None and (row['measures'].get(str(b)) or {}).get('slope') is not None]
    return row


def explore(conn, request):
    config=C.validate(request['config']);view=request.get('view') or {};params=configuration(conn)
    supported={'secondary','status','sort','dir','kind','market','q','page','page_size','export','owned_ids','description','icon','tradable'}
    unsupported=[k for k,v in view.items() if k not in supported and v not in (None,False,'',[],{})]
    if unsupported or view.get('tradable'):
        raise ValueError('Filtres de l’éditeur historique : '+', '.join(unsupported or ['négociabilité'])+' ; ouvrez l’éditeur complet pour cette recherche, aucun filtre n’a été ignoré')
    if view.get('kind') not in (None,'','equity','etf'):raise ValueError('Type historique : utilisez l’éditeur complet')
    rows,version=financial_rows(conn,config)
    counts={state:sum(r['status']==state for r in rows) for state in ('retained','rejected','unknown')}
    filters=view.get('secondary',params['filters'])
    if not isinstance(filters,dict) or any(k not in params['categories'] for k in filters):raise ValueError('Filtre secondaire inconnu')
    for key,chosen in filters.items():
        allowed={'unknown'}|{'c'+str(i) for i in range(len(params['categories'][key]['labels']))}
        if not isinstance(chosen,list) or any(x not in allowed for x in chosen):raise ValueError('Catégorie de filtre inconnue')
    rows=[decorate(r,config,params) for r in rows]
    scoped=[r for r in rows if (not view.get('kind') or r['kind']==view['kind']) and (not view.get('market') or r['mic']==view['market'])]
    query=str(view.get('q') or '').strip().casefold()[:100]
    if query:scoped=[r for r in scoped if any(query in str(r.get(k) or '').casefold() for k in ('symbol','name','isin'))]
    status=view.get('status','retained')
    if status not in ('retained','rejected','unknown','all'):raise ValueError('Statut inconnu')
    requested=[r for r in scoped if query or status=='all' or r['status']==status]
    visible=[r for r in requested if all(r['badges'][k]['id'] in chosen for k,chosen in filters.items())]
    masked=len(requested)-len(visible)
    excluded=[]
    with conn.cursor() as q:
        q.execute('SELECT status,is_primary,excluded_reason,COUNT(*) n FROM listings WHERE status<>\'selected\' OR is_primary=0 GROUP BY status,is_primary,excluded_reason')
        technical=q.fetchall()
        q.execute('SELECT removed_step,COUNT(*) n FROM catalogue_raw WHERE removed_step IS NOT NULL GROUP BY removed_step')
        catalogue_exclusions=q.fetchall()
        if query:
            like='%'+query.replace('%','').replace('_','')+'%'
            q.execute("SELECT l.id,l.symbol,l.mic,l.status,l.excluded_reason,l.is_primary,i.name,i.kind,i.isin FROM listings l JOIN instruments i ON i.id=l.instrument_id WHERE (l.status<>'selected' OR l.is_primary=0) AND (LOWER(l.symbol) LIKE %s OR LOWER(i.name) LIKE %s OR LOWER(i.isin) LIKE %s) ORDER BY l.symbol LIMIT 51",(like,like,like))
            for item in q.fetchall():
                if view.get('kind') and item['kind']!=view['kind']:continue
                excluded.append(dict(item,status='technical',scores={'simple':None,'complex':None},
                                     reasons=[dict(criterion='technical',result='missing',value=item['status'],threshold='selected + cotation principale',
                                                   origin=item['excluded_reason'] or 'cotation secondaire / données de cotation indisponibles')]))
    key=view.get('sort','simple');reverse=view.get('dir','desc')=='desc'
    def val(row):
        if key in ('simple','complex'):return row['scores'][key]
        if key=='proximity':return tuple(row.get('proximity',[999,999,999]))
        if ':' in key:
            n,metric=key.split(':',1);return (row.get('measures',{}).get(n) or {}).get(metric)
        if key in params['categories']:return row['badges'][key]['value']
        if key=='symbol':return row['symbol']
        return row.get('price_eur')
    known=[r for r in visible if val(r) is not None];unknown=[r for r in visible if val(r) is None]
    known.sort(key=lambda r:r['symbol']);known.sort(key=val,reverse=reverse)
    unknown.sort(key=lambda r:(r['symbol'],r['id']))
    visible=known+unknown+excluded[:50];total=len(visible);size=20000 if view.get('export') else min(100,max(1,int(view.get('page_size',30))))
    page=1 if view.get('export') else max(1,min(max(1,math.ceil(total/size)),int(view.get('page',1))))
    return dict(rows=visible[(page-1)*size:page*size],total=total,page=page,pages=max(1,math.ceil(total/size)),
                counts=dict(available=len(rows),technical=sum(r['n'] for r in technical),**counts,
                            secondary_masked=masked,visible=total,scope=len(scoped)),
                technical=technical,technical_rules=dict(catalogue=settings.catalogue_rules(conn),prefilter=settings.prefilter_rules(conn)),
                catalogue_exclusions=catalogue_exclusions,rules_applied=settings.get(conn,'rules_applied',{}),
                technical_origin=dict(catalogue='admin' if settings.get(conn,'catalogue_rules') is not None else 'défaut code',prefilter='admin' if settings.get(conn,'prefilter') is not None else 'défaut code'),
                count_scope='Cotations connues, univers complet avant pagination ; filtres de type/place/recherche comptés dans scope',
                filters=filters,categories=params['categories'],data_version=version,formula=growth.VERSION,
                search_truncated=len(excluded)>50,export_truncated=bool(view.get('export') and total>size))


def detail(conn,request):
    config=C.validate(request['config']);base=copy.deepcopy(config);base.pop('growth')
    # Reuse all existing price, event, technical, ETF and market-data panels.
    sheet=service.instrument_sheet(conn,dict(request,config=base,fetch_profile=False))
    rows,_=financial_rows(conn,config);row=next((r for r in rows if r['id']==request['listing_id']),None)
    if row:
        sheet['growth']=decorate(row,config,configuration(conn))
        sheet['verdict'].update(status=row['status'],score=row['score'],reasons=row['reasons'])
    return sheet
