import os,tempfile,unittest
os.environ.setdefault('ARCHIVE_DATA',tempfile.mkdtemp(prefix='er-ip-'))
import app
from werkzeug.security import generate_password_hash
class ViewerIpTests(unittest.TestCase):
 def setUp(self):
  with app.db() as c:
   c.execute("DELETE FROM settings WHERE key IN ('viewer_ip_allowlist','viewer_ip_restriction_enabled')")
   c.execute("INSERT OR REPLACE INTO users VALUES('ipadmin',?,'admin')",(generate_password_hash('ip-password'),))
   c.execute("INSERT OR REPLACE INTO users VALUES('ipviewer',?,'viewer')",(generate_password_hash('ip-password'),))
  self.local=app.app.test_client();self.remote=app.app.test_client();self.admin=app.app.test_client();self.viewer=app.app.test_client()
  self.outside={'REMOTE_ADDR':'10.2.3.4'}
  response=self.admin.post('/api/login',json={'name':'ipadmin','password':'ip-password'},environ_overrides=self.outside);self.h={'X-CSRF':response.json['csrf']}
 def test_default_deny_login_and_management(self):
  self.assertEqual(self.remote.get('/api/me',environ_overrides=self.outside).status_code,200)
  self.assertFalse(self.admin.get('/api/viewer-ips',environ_overrides=self.outside).json['enabled'])
  self.assertEqual(self.remote.get('/api/viewer-ips',environ_overrides=self.outside).status_code,401)
  self.assertEqual(self.admin.post('/api/viewer-ips',json={'addresses':[],'enabled':True},headers=self.h,environ_overrides=self.outside).status_code,200)
  self.assertEqual(self.local.get('/api/me').status_code,200)
  self.assertEqual(self.remote.get('/api/me',environ_overrides=self.outside).status_code,403)
  self.assertEqual(self.remote.get('/api/documents',environ_overrides=self.outside,headers={'X-Forwarded-For':'127.0.0.1'}).status_code,403)
  self.assertEqual(self.remote.get('/',environ_overrides=self.outside).status_code,200)
  self.assertEqual(self.admin.get('/api/viewer-ips',environ_overrides=self.outside).status_code,200)
  self.assertEqual(self.admin.post('/api/viewer-ips',json={'addresses':['10.2.3.5']},environ_overrides=self.outside).status_code,403)
  self.assertEqual(self.admin.post('/api/viewer-ips',json={'addresses':['10.2.3.5']},headers=self.h,environ_overrides=self.outside).status_code,200)
  self.assertEqual(self.remote.get('/api/me',environ_overrides={'REMOTE_ADDR':'10.2.3.5'}).status_code,200)
  self.assertEqual(self.remote.get('/api/me',environ_overrides=self.outside).status_code,403)
  self.assertEqual(self.admin.get('/api/documents',environ_overrides=self.outside).status_code,200)
 def test_viewer_account_and_revocation(self):
  self.assertEqual(self.admin.post('/api/viewer-ips',json={'addresses':[],'enabled':True},headers=self.h,environ_overrides=self.outside).status_code,200)
  viewer=self.viewer.post('/api/login',json={'name':'ipviewer','password':'ip-password'},environ_overrides=self.outside);self.assertEqual(viewer.status_code,200)
  self.assertEqual(self.viewer.get('/api/documents',environ_overrides=self.outside).status_code,403)
  self.assertEqual(self.admin.post('/api/viewer-ips',json={'addresses':['10.2.3.4','10.2.3.4','2001:db8::1']},headers=self.h,environ_overrides=self.outside).status_code,200)
  self.assertEqual(self.viewer.get('/api/documents',environ_overrides=self.outside).status_code,200)
  self.assertEqual(self.viewer.get('/api/viewer-ips',environ_overrides=self.outside).status_code,403)
  self.assertEqual(self.remote.get('/api/me',environ_overrides={'REMOTE_ADDR':'::ffff:10.2.3.4'}).status_code,200)
  self.assertEqual(self.remote.get('/api/me',environ_overrides={'REMOTE_ADDR':'2001:db8::1'}).status_code,200)
  self.assertEqual(self.admin.post('/api/viewer-ips',json={'addresses':[]},headers=self.h,environ_overrides=self.outside).status_code,200)
  self.assertEqual(self.viewer.get('/api/me',environ_overrides=self.outside).status_code,403)
 def test_invalid_or_network_ranges_rejected(self):
  for address in ['10.0.0.0/24','*','127.0.0.1\n10.0.0.1','0.0.0.0','239.1.1.1']:
   self.assertEqual(self.admin.post('/api/viewer-ips',json={'addresses':[address]},headers=self.h,environ_overrides=self.outside).status_code,400)
  self.assertEqual(self.remote.get('/api/me',environ_overrides={'REMOTE_ADDR':'::1'}).status_code,200)
  self.assertEqual(self.admin.post('/api/viewer-ips',json={'addresses':[],'enabled':'false'},headers=self.h,environ_overrides=self.outside).status_code,400)
 def test_existing_list_survives_disable_and_reenable(self):
  with app.db() as c:
   c.execute("INSERT INTO settings(key,value) VALUES('viewer_ip_allowlist','[\"10.2.3.5\"]')")
  state=self.admin.get('/api/viewer-ips',environ_overrides=self.outside).json
  self.assertEqual(state['addresses'],['10.2.3.5'])
  self.assertFalse(state['enabled'])
  self.assertEqual(self.remote.get('/api/documents',environ_overrides=self.outside).status_code,200)
  for enabled,expected in [(True,403),(False,200),(True,403)]:
   self.assertEqual(self.admin.post('/api/viewer-ips',json={'addresses':state['addresses'],'enabled':enabled},headers=self.h,environ_overrides=self.outside).status_code,200)
   self.assertEqual(self.remote.get('/api/me',environ_overrides=self.outside).status_code,expected)
   self.assertEqual(self.remote.get('/api/me',environ_overrides={'REMOTE_ADDR':'10.2.3.5'}).status_code,200)
  self.assertEqual(self.admin.get('/api/viewer-ips',environ_overrides=self.outside).json['addresses'],['10.2.3.5'])
if __name__=='__main__':unittest.main()
