import os,tempfile,unittest,subprocess,sys,json
os.environ.setdefault('ARCHIVE_DATA',tempfile.mkdtemp(prefix='reg-fulltext-'))
import app
from werkzeug.security import generate_password_hash
class FullTextTests(unittest.TestCase):
 def setUp(self):
  with app.db() as c:
   c.execute('DELETE FROM regulation_articles');c.execute('DELETE FROM regulation_documents');c.execute('DELETE FROM regulation_deleted_categories')
   c.execute("INSERT OR REPLACE INTO users VALUES('ftadmin',?,'admin')",(generate_password_hash('admin-password'),));c.execute("INSERT OR REPLACE INTO users VALUES('ftreader',?,'viewer')",(generate_password_hash('reader-password'),))
  self.admin=app.app.test_client();self.viewer=app.app.test_client();self.guest=app.app.test_client()
  self.h={'X-CSRF':self.admin.post('/api/login',json={'name':'ftadmin','password':'admin-password'}).json['csrf']}
  self.vh={'X-CSRF':self.viewer.post('/api/login',json={'name':'ftreader','password':'reader-password'}).json['csrf']}
 def test_original_roundtrip_permissions_conflict_delete(self):
  raw='목 차\r\n제1조(목적)\r\n\r\n제1조【목적】\r\n\t본문 & <script> \u00a0\r\n부칙\r\n근로시간 근로시간\r\n'
  payload={'category':'agreement','body':raw,'token':''}
  self.assertEqual(self.viewer.post('/api/regulations/save',json=payload,headers=self.vh).status_code,403)
  self.assertEqual(self.admin.post('/api/regulations/save',json=payload).status_code,403)
  self.assertEqual(self.admin.post('/api/regulations/save',json=payload,headers=self.h).status_code,200)
  self.assertEqual(self.guest.get('/api/regulations/fulltexts').json['documents'][0]['body'],raw)
  doc=self.admin.get('/api/regulations/document?category=agreement').json['document'];self.assertEqual(doc['body'],raw)
  self.assertEqual(self.admin.post('/api/regulations/save',json=payload,headers=self.h).status_code,409)
  self.assertEqual(self.admin.post('/api/regulations/delete',json={'category':'agreement','token':doc['token']},headers=self.h).status_code,200)
  self.assertEqual(self.guest.get('/api/regulations/fulltexts').json['documents'],[])
 def test_plain_text_is_accepted(self):
  self.assertEqual(self.admin.post('/api/regulations/save',json={'category':'union_act','body':'형식 없는 본문\n원문 그대로','token':''},headers=self.h).status_code,200)
  with app.db() as c:self.assertEqual(c.execute("SELECT count(*) FROM regulation_articles").fetchone()[0],0)
if __name__=='__main__':unittest.main()
