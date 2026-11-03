"""Explicit, rate-limited, one-listing reuse of the normal history collectors."""
import datetime as dt
import time
from engine.shared import settings
from engine.jobs.tasks import fetch_daily, fetch_intraday


def refresh(conn, listing_id, client=None, now=None):
    lid=int(listing_id);now=now or dt.datetime.now(dt.timezone.utc);key='portfolio_refresh_'+str(lid)
    with conn.cursor() as q:
        q.execute('SELECT GET_LOCK(%s,0) ok',(key,))
        if not q.fetchone()['ok']:return {'message':'Une collecte de ce titre est déjà en cours.','cooldown':True}
    try:
        stamp=settings.get(conn,key,0)
        if time.time()-float(stamp)<900:return {'message':'Ce titre a déjà été actualisé récemment. Réessayez après quinze minutes.','cooldown':True}
        with conn.cursor() as q:
            q.execute('SELECT listing_id,mic,symbol,held FROM v_collect_set WHERE listing_id=%s',(lid,));rows=q.fetchall()
        if not rows:return {'message':'Ce titre ne fait pas partie du jeu de collecte actuel.','asked':0}
        settings.put(conn,key,time.time())
        if client is None:
            from engine.market.yahoo import YahooClient
            client=YahooClient()
        daily=fetch_daily(conn,client,rows,now)
        intraday=fetch_intraday(conn,client,rows,now)
        return {'message':f"Collecte ciblée : {daily['added']} clôture(s) et {intraday['added']} barre(s) ajoutée(s). Les données absentes chez le fournisseur restent indisponibles.",
                'daily':daily,'intraday':intraday,'listing_id':lid}
    finally:
        with conn.cursor() as q:q.execute('SELECT RELEASE_LOCK(%s)',(key,))
