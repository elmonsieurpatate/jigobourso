import json,time,secrets,datetime,hashlib,urllib.request,urllib.error
from engine.shared.db import connect
from engine.analytics import ranking_table
c=connect()
with c.cursor() as cur:
 cur.execute('SELECT id FROM users WHERE active=1 ORDER BY is_admin DESC,id LIMIT 1'); uid=cur.fetchone()['id']
token=secrets.token_hex(32); digest=hashlib.sha256(token.encode()).hexdigest(); now=datetime.datetime.utcnow();expiry=now+datetime.timedelta(minutes=5)
try:
 with c.cursor() as cur:cur.execute('INSERT INTO sessions(token_hash,user_id,created_at,last_seen,expires_at,ip,ua) VALUES (%s,%s,%s,%s,%s,%s,%s)',(digest,uid,now,now,expiry,'','ranking-response-diagnostic'))
 c.commit()
 for strategy in ['fast','regular']:
  url='https://jigobourso.turnjoy.dev/api.php?r=ranking/table&strategy='+strategy
  start=time.time()
  try:
   req=urllib.request.Request(url,headers={'Cookie':'jigo_s='+token,'Cache-Control':'no-cache'})
   with urllib.request.urlopen(req,timeout=110) as r:raw=r.read();code=r.status;ctype=r.headers.get('Content-Type')
   try:d=json.loads(raw);summary={'rows':len(d['rows']) if isinstance(d,dict) and isinstance(d.get('rows'),list) else None,'error':d.get('error') if isinstance(d,dict) else None,'type':type(d).__name__}
   except Exception as e:summary={'json_error':str(e),'prefix_kind':'html' if raw.lstrip().startswith(b'<') else 'empty' if not raw else 'other'}
   print(json.dumps({'strategy':strategy,'http':code,'bytes':len(raw),'content_type':ctype,'seconds':round(time.time()-start,1),**summary}),flush=True)
  except Exception as e:print(json.dumps({'strategy':strategy,'request_error':str(e),'seconds':round(time.time()-start,1)}),flush=True)
finally:
 with c.cursor() as cur:cur.execute('DELETE FROM session_policies WHERE token_hash=%s',(digest,));cur.execute('DELETE FROM sessions WHERE token_hash=%s',(digest,))
 c.commit();c.close()
