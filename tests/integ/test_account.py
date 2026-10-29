"""HTTP round-trips with real PHP and disposable MariaDB; mail captured outside web root."""
import datetime as dt,json,os,re,socket,subprocess,sys,time
from pathlib import Path
import pytest
from engine.shared.db import connect
from tests.integ.test_api import world,Client,login,ROOT
pytestmark=pytest.mark.integration
if not os.environ.get('JIGO_TEST_DATABASE'):pytest.skip('disposable DB only',allow_module_level=True)
MAILDIR=None
@pytest.fixture(scope='module')
def server(tmp_path_factory):
 global MAILDIR
 MAILDIR=tmp_path_factory.mktemp('account-mail')
 s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close()
 p=subprocess.Popen(['php','-S',f'127.0.0.1:{port}','-t',ROOT+'/app/public'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=dict(os.environ,JIGO_ENGINE_ROOT=ROOT,JIGO_PYTHON=sys.executable,JIGO_TEST_MAIL_DIR=str(MAILDIR)))
 for _ in range(50):
  try:socket.create_connection(('127.0.0.1',port),.2).close();break
  except OSError:time.sleep(.1)
 yield f'http://127.0.0.1:{port}'
 p.terminate();p.wait()

@pytest.fixture(autouse=True)
def clean_mail(server):
 for p in MAILDIR.glob('*.json'):p.unlink()

def set_email():
 c=connect()
 with c.cursor() as q:q.execute("UPDATE users SET email='alice@example.test' WHERE username='alice'")
 c.commit();c.close()

def link():
 messages=[json.loads(p.read_text()) for p in MAILDIR.glob('*.json')]
 assert len(messages)==1
 raw=re.search(r'#token=([a-f0-9]{64})',messages[0]['body']).group(1)
 return raw,messages[0]

def test_login_by_email_and_pseudo_share_account_and_password(world):
 set_email()
 a=login(world,'alice','alice-secret-1234');b=login(world,'ALICE@example.test','alice-secret-1234')
 assert a.call('auth/me')[1]['user']['id']==b.call('auth/me')[1]['user']['id']
 for ident in ('alice','alice@example.test','unknown@example.test'):
  status,data=Client(world).call('auth/login',{'username':ident,'password':'wrong'})
  assert status==401 and data['error']=='E-mail, pseudo ou mot de passe incorrect'

def test_reset_round_trip_one_use_revokes_sessions_preserves_finances(world):
 set_email();a=login(world,'alice','alice-secret-1234');anon=Client(world)
 pf=a.call('portfolio/create',{'name':'Preserve'})[1]['id']
 assert a.call('tx/add',{'portfolio_id':pf,'listing_id':1,'side':'buy','quantity':1,'unit_price':100,'trade_at':'2026-10-01'})[0]==200
 assert anon.call('auth/recover',{'email':'alice@example.test'})[0]==200
 raw,msg=link();assert msg['to']=='alice@example.test'
 c=connect()
 with c.cursor() as q:
  q.execute('SELECT token_hash FROM account_tokens');assert raw not in q.fetchone()['token_hash']
 c.close()
 assert anon.call('auth/reset',{'token':raw,'new':'new-secret-12345'})[0]==200
 assert anon.call('auth/reset',{'token':raw,'new':'other-secret-12345'})[0]==422
 assert a.call('portfolio',params=f'&id={pf}')[0]==401
 fresh=login(world,'alice@example.test','new-secret-12345')
 assert fresh.call('portfolio',params=f'&id={pf}')[1]['positions'][0]['cost']==100

@pytest.mark.parametrize('kind',['expired','tampered','password_changed'])
def test_invalid_reset_links_never_change_password(world,kind):
 set_email();a=login(world,'alice','alice-secret-1234');anon=Client(world)
 assert anon.call('auth/recover',{'email':'alice@example.test'})[0]==200
 raw,_=link()
 if kind=='expired':
  c=connect()
  with c.cursor() as q:q.execute("UPDATE account_tokens SET expires_at='2020-01-01'")
  c.commit();c.close()
 elif kind=='tampered':raw=('a' if raw[0]!='a' else 'b')+raw[1:]
 else:assert a.call('auth/password',{'current':'alice-secret-1234','new':'changed-secret-1234'})[0]==200
 assert anon.call('auth/reset',{'token':raw,'new':'invalid-secret-1234'})[0]==422

def test_recovery_generic_response_and_limits(world):
 set_email();c=Client(world)
 known=c.call('auth/recover',{'email':'alice@example.test'})
 unknown=c.call('auth/recover',{'email':'unknown@example.test'})
 assert known==unknown and len(list(MAILDIR.glob('*.json')))==1
 for _ in range(2):assert c.call('auth/recover',{'email':'unknown@example.test'})[0]==200
 assert c.call('auth/recover',{'email':'unknown@example.test'})[0]==429

def test_email_change_is_verified_and_username_keeps_same_account(world):
 set_email();a=login(world,'alice','alice-secret-1234');uid=a.call('auth/me')[1]['user']['id']
 r=a.call('auth/account',{'username':'new_alice','email':'new@example.test','current':'alice-secret-1234'})
 assert r[0]==200 and r[1]['email_pending']
 assert a.call('auth/me')[1]['user']['email']=='alice@example.test'
 raw,msg=link();assert msg['to']=='new@example.test'
 assert Client(world).call('auth/verify-email',{'token':raw})[0]==200
 assert Client(world).call('auth/verify-email',{'token':raw})[0]==422
 u=login(world,'new@example.test','alice-secret-1234').call('auth/me')[1]['user']
 assert u['id']==uid and u['username']=='new_alice'
 assert a.call('auth/me')[1]['user']['id']==uid # no forced logout for profile changes

def test_wrong_password_cannot_change_profile(world):
 set_email();a=login(world,'alice','alice-secret-1234')
 assert a.call('auth/account',{'username':'changed','email':'new@example.test','current':'wrong'})[0]==403
 assert a.call('auth/me')[1]['user']['username']=='alice'
 assert not list(MAILDIR.glob('*.json'))

@pytest.mark.parametrize('remember,days',[(False,1),(True,30)])
def test_session_cookie_and_absolute_expiry(world,remember,days):
 c=Client(world);assert c.call('auth/login',{'username':'alice','password':'alice-secret-1234','remember':remember})[0]==200
 cookies=list(c.opener.handlers[4].cookiejar) if False else list(next(h.cookiejar for h in c.opener.handlers if hasattr(h,'cookiejar')))
 cookie=next(x for x in cookies if x.name=='jigo_s')
 assert (cookie.expires is not None)==remember
 con=connect()
 with con.cursor() as q:
  q.execute('SELECT absolute_expiry,persistent FROM session_policies');r=q.fetchone()
 assert r['persistent']==int(remember)
 assert abs((r['absolute_expiry']-dt.datetime.utcnow()).total_seconds()-days*86400)<10
 c.call('auth/me')
 with con.cursor() as q:q.execute('SELECT expires_at FROM sessions');assert q.fetchone()['expires_at']==r['absolute_expiry']
 con.close()

def test_mail_failure_does_not_leave_a_usable_reset_link(world):
 set_email()
 code="require "+repr(ROOT+'/app/lib/account.php')+"; $u=q(\"SELECT * FROM users WHERE username='alice'\")->fetch(); echo json_encode(issue_account_link($u,'reset',$u['email']));"
 r=subprocess.run(['php','-r',code],env=dict(os.environ,JIGO_TEST_MAIL_FAIL='1'),capture_output=True,text=True)
 assert r.returncode==0 and json.loads(r.stdout) is False
 c=connect()
 with c.cursor() as q:
  q.execute('SELECT COUNT(*) n FROM account_tokens WHERE used_at IS NULL');assert q.fetchone()['n']==0
 c.close()

def test_old_sessions_without_policy_survive_migration(world):
 a=login(world,'alice','alice-secret-1234');c=connect()
 with c.cursor() as q:q.execute('DELETE FROM session_policies')
 c.commit();c.close()
 assert a.call('auth/me')[1]['user']['username']=='alice'
