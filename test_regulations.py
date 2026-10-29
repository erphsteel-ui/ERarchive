import os,tempfile,unittest
os.environ.setdefault('ARCHIVE_DATA',tempfile.mkdtemp(prefix='er-regulations-'))
import app
from regulations import parse_articles
from werkzeug.security import generate_password_hash

class RegulationTests(unittest.TestCase):
 def setUp(self):
  with app.db() as c:
   c.execute('DELETE FROM regulation_versions')
   c.execute("INSERT OR REPLACE INTO users VALUES('regadmin',?,'admin')",(generate_password_hash('reg-admin-password'),))
   c.execute("INSERT OR REPLACE INTO users VALUES('regreader',?,'viewer')",(generate_password_hash('reg-reader-password'),))
  self.admin=app.app.test_client();self.reader=app.app.test_client();self.guest=app.app.test_client()
  self.h={'X-CSRF':self.admin.post('/api/login',json={'name':'regadmin','password':'reg-admin-password'}).json['csrf']}
  self.rh={'X-CSRF':self.reader.post('/api/login',json={'name':'regreader','password':'reg-reader-password'}).json['csrf']}
 def payload(self,**changes):
  data={'category':'agreement','base_version':0,'title':'단체협약 시험본','effective_date':'2026-01-01','source':'시험 자료','body':'제1장 총칙\n제1조 (목적)\n첫 번째 본문\n제2조의2 (휴가)\n휴가 내용'};data.update(changes);return data
 def test_permissions_versions_history_and_conflict(self):
  self.assertEqual(self.guest.get('/api/regulations?category=agreement').json['entry'],None)
  self.assertEqual(self.guest.post('/api/regulations',json=self.payload()).status_code,401)
  self.assertEqual(self.reader.post('/api/regulations',json=self.payload(),headers=self.rh).status_code,403)
  self.assertEqual(self.admin.post('/api/regulations',json=self.payload(),headers=self.h).status_code,200)
  self.assertEqual(self.admin.post('/api/regulations',json=self.payload(),headers=self.h).status_code,409)
  self.assertEqual(self.admin.post('/api/regulations',json=self.payload(base_version=1,body='제1장 총칙\n제1조 (목적)\n변경된 본문'),headers=self.h).status_code,200)
  data=self.guest.get('/api/regulations?category=agreement').json
  self.assertEqual(data['entry']['version'],2);self.assertEqual(len(data['versions']),2)
  history=self.guest.get('/api/regulations/history?category=agreement&article=1').json['items']
  self.assertEqual([x['version'] for x in history],[2,1]);self.assertIn('첫 번째 본문',history[1]['text'])
  old=self.guest.get('/api/regulations?category=agreement&version=1').json['entry']
  self.assertEqual(old['articles'][1]['key'],'2의2');self.assertEqual(old['source'],'시험 자료')
 def test_validation_and_unstructured_text(self):
  self.assertEqual(self.admin.post('/api/regulations',json=self.payload(effective_date='2026-02-30'),headers=self.h).status_code,400)
  self.assertEqual(self.guest.get('/api/regulations?category=unknown').status_code,400)
  items=parse_articles('정리되지 않은 원문\n두 번째 줄')
  self.assertEqual(len(items),1);self.assertEqual(items[0]['text'],'정리되지 않은 원문\n두 번째 줄')
  self.assertEqual(parse_articles('제1조 (목적)\n가\n제 2 장 복무\n제2조의 3 (휴가)\n나')[1]['chapter'],'제 2 장 복무')
