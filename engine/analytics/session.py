"""Indicative 15-minute changes, only for unchanged holdings and observed prices."""
import datetime as dt
from bisect import bisect_right


def euro_rate(currency, day, fx):
    currency=currency or ''
    if currency.upper()=='EUR':return 1.0
    base='GBP' if currency.upper() in ('GBP','GBX') else currency.upper()
    pairs=fx.get(base,[]);i=bisect_right([str(d) for d,_ in pairs],day)-1
    if i<0:return None
    date,rate=pairs[i]
    if not 0<rate or (dt.date.fromisoformat(day)-dt.date.fromisoformat(str(date))).days>7:return None
    return rate/(100 if currency in ('GBp','GBX') else 1)


def build(holdings,bars,units,fx,transactions,splits=None,meta=None):
    held={k:q for k,q in holdings.items() if q>1e-12};meta=meta or {};splits=splits or {}
    days=sorted({t[:10] for k in held for t,_ in bars.get(k,[])})
    if not days:return {'dates':[],'lines':[],'gain':[],'value':[],'pct':[],'base':None,'notes':['Aucune barre de 15 minutes enregistrée pour les positions détenues.']}
    day=days[-1];dates=sorted({t for k in held for t,_ in bars.get(k,[]) if t[:10]==day});lines=[];notes=[]
    tx_after=any(str(t['trade_at'])[:10]>=day for t in transactions)
    for k,q in held.items():
        observed={t:p for t,p in bars.get(k,[]) if t[:10]==day}
        reason=None;rate=euro_rate(units.get(k),day,fx)
        if any((int(t['listing_id']) if t.get('listing_id') else 'S'+str(t['symbol']).upper())==k and str(t['trade_at'])[:10]>=day for t in transactions):reason='Transaction pendant ou après cette séance : quantité historique non reconstituée.'
        elif any(d>day for d,_ in splits.get(k,[])):reason='Split postérieur à la séance : unités non comparables.'
        elif not observed:reason='Aucune barre de 15 minutes pour cette séance.'
        elif dates[0] not in observed:reason='Cotation absente au début de la plage commune.'
        elif rate is None:reason='Change quotidien absent ou âgé de plus de sept jours.'
        base=None if reason else q*observed[dates[0]]*rate
        values=[q*observed[t]*rate if not reason and t in observed else None for t in dates]
        gain=[v-base if v is not None and base is not None else None for v in values]
        symbol=meta.get(k,{}).get('symbol') or str(k)
        if reason:notes.append(symbol+' : '+reason)
        lines.append({'key':str(k),'symbol':symbol,'reason':reason,'base':base,'values':values,'gain':gain,
                      'pct':[100*g/base if g is not None and base and base>0 else None for g in gain]})
    values=[sum(l['values'][i] for l in lines) if all(l['values'][i] is not None for l in lines) else None for i in range(len(dates))]
    base=values[0] if values else None
    gain=[sum(l['gain'][i] for l in lines) if not tx_after and all(l['gain'][i] is not None for l in lines) else None for i in range(len(dates))]
    if tx_after:notes.append('Transactions pendant ou après la séance : résultat global exact indisponible. Les titres sans mouvement peuvent rester comparables.')
    notes.append('Variation indicative entre les barres observées du '+day+' ; horodatages UTC, change quotidien figé sur la séance, sans variation de change intraday. Aucun cours manquant n’est simulé.')
    return {'dates':dates,'day':day,'lines':lines,'base':base if not tx_after else None,'value':values,'gain':gain,
            'pct':[100*g/base if g is not None and base and base>0 else None for g in gain],'notes':notes}
