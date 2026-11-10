"""Isolated end-to-end checks for authentication and reader administration."""
import os,subprocess,sys,tempfile,textwrap,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
class AuthAccessTests(unittest.TestCase):
 def test_login_access_revocation_and_expiry(self):
  with tempfile.TemporaryDirectory() as folder:
   env=os.environ.copy();env.pop('ERARCHIVE_REQUIRE_VOLUME',None);env['ERARCHIVE_DATA_DIR']=folder
   code=textwrap.dedent('''
    import io,time,app
    from werkzeug.security import generate_password_hash
    with app.db() as c:c.execute('INSERT INTO users VALUES(?,?,?)',('admin',generate_password_hash('admin-password-123'),'admin'))
    admin=app.app.test_client();guest=app.app.test_client();reader=app.app.test_client();second=app.app.test_client()
    assert guest.get('/').status_code==200
    for route in ['/api/me','/api/documents','/api/schedule?month=2026-12','/api/regulations/fulltexts','/api/image/missing']:
     assert guest.get(route).status_code==401,route
    assert guest.get('/healthz').status_code==200
    assert app.app.permanent_session_lifetime.days==30
    auth=admin.post('/api/login',json={'name':'admin','password':'admin-password-123'});assert auth.status_code==200
    ah={'X-CSRF':auth.json['csrf']}
    assert admin.post('/api/users',json={'action':'create','name':'reader1','password':'short'},headers=ah).status_code==400
    for i in range(1,6):
     assert admin.post('/api/users',json={'action':'create','name':f'reader{i}','password':'reader-password-123'},headers=ah).status_code==200
    assert len(admin.get('/api/users').json['users'])==6
    assert admin.post('/api/users',json={'action':'disable','name':'admin'},headers=ah).status_code==403
    assert admin.post('/api/users',json={'action':'create','name':'reader1','password':'reader-password-123'},headers=ah).status_code==409
    r=reader.post('/api/login',json={'name':'reader1','password':'reader-password-123'});assert r.status_code==200
    rh={'X-CSRF':r.json['csrf']}
    s=second.post('/api/login',json={'name':'reader1','password':'reader-password-123'});assert s.status_code==200
    assert reader.get('/api/schedule?month=2026-12').status_code==200
    assert reader.post('/api/schedule/event',json={},headers=rh).status_code==403
    assert reader.get('/api/users').status_code==403
    assert reader.post('/api/users',json={'action':'disable','name':'reader2'},headers=rh).status_code==403
    assert admin.post('/api/users',json={'action':'disable','name':'reader1'},headers=ah).status_code==200
    assert reader.get('/api/documents').status_code==401 and second.get('/api/documents').status_code==401
    assert reader.post('/api/login',json={'name':'reader1','password':'reader-password-123'}).status_code==401
    assert admin.post('/api/users',json={'action':'enable','name':'reader1'},headers=ah).status_code==200
    r=reader.post('/api/login',json={'name':'reader1','password':'reader-password-123'});assert r.status_code==200
    assert admin.post('/api/users',json={'action':'reset','name':'reader1','password':'replacement-pass-123'},headers=ah).status_code==200
    assert reader.get('/api/me').status_code==401
    assert reader.post('/api/login',json={'name':'reader1','password':'reader-password-123'}).status_code==401
    r=reader.post('/api/login',json={'name':'reader1','password':'replacement-pass-123'});assert r.status_code==200
    rh={'X-CSRF':r.json['csrf']}
    assert reader.post('/api/change-password',json={'current':'replacement-pass-123','new':'new-password-123'},headers=rh).status_code==200
    assert reader.get('/api/me').status_code==200
    with app.db() as c:c.execute("UPDATE auth_sessions SET expires=? WHERE name='reader1'",(int(time.time())-1,))
    assert reader.get('/api/documents').status_code==401
    assert reader.post('/api/login',json={'name':'reader1','password':'new-password-123'}).status_code==200
    assert admin.post('/api/users',json={'action':'revoke','name':'reader1'},headers=ah).status_code==200
    assert reader.get('/api/me').status_code==401
   ''')
   p=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=env,text=True,capture_output=True)
   self.assertEqual(p.returncode,0,p.stderr)
if __name__=='__main__':unittest.main()
