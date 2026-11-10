import os,tempfile,unittest
from unittest.mock import patch
os.environ.setdefault('ARCHIVE_DATA',tempfile.mkdtemp(prefix='law-api-'))
import app,law_api
from werkzeug.security import generate_password_hash
XML='''<?xml version="1.0" encoding="UTF-8"?><법령><기본정보><법령ID>001872</법령ID><법령명_한글>근로기준법</법령명_한글><시행일자>20260101</시행일자><공포일자>20251201</공포일자></기본정보><조문><조문단위><조문내용>제50조(근로시간)</조문내용><항><항내용>① 1주 40시간</항내용><호><호내용>1. 근로시간</호내용><목><목내용>가. 휴게</목내용></목></호></항></조문단위></조문><부칙><부칙내용>부칙 내용</부칙내용></부칙></법령>'''.encode()
class LawTests(unittest.TestCase):
 def setUp(self):
  with app.db() as c:
   c.execute("DELETE FROM settings WHERE key='law_api_oc'");c.execute('DELETE FROM law_import_candidates');c.execute('DELETE FROM law_import_sources');c.execute('DELETE FROM regulation_articles');c.execute('DELETE FROM regulation_documents')
   c.execute("INSERT OR REPLACE INTO users VALUES('lawadmin',?,'admin')",(generate_password_hash('pw-test'),));c.execute("INSERT OR REPLACE INTO users VALUES('lawviewer',?,'viewer')",(generate_password_hash('pw-test'),))
  self.admin=app.app.test_client();self.viewer=app.app.test_client();self.h={'X-CSRF':self.admin.post('/api/login',json={'name':'lawadmin','password':'pw-test'}).json['csrf']};self.vh={'X-CSRF':self.viewer.post('/api/login',json={'name':'lawviewer','password':'pw-test'}).json['csrf']}
 def test_xml_validation_and_order(self):
  result=law_api.prepare_law('labor_act',XML);self.assertEqual(result['body'],'제50조(근로시간)\n① 1주 40시간\n1. 근로시간\n가. 휴게\n부칙 내용');self.assertEqual(result['effective_date'],'20260101')
  for category,data in [('union_act',XML),('labor_act',b'<error/>'),('labor_act',b'<!DOCTYPE a><a/>')]:
   with self.assertRaises(law_api.LawApiError):law_api.prepare_law(category,data)
 def test_import_is_preview_only_and_saves_original(self):
  self.assertEqual(self.viewer.post('/api/regulations/law-preview',json={'category':'labor_act'},headers=self.vh).status_code,403)
  self.assertEqual(self.admin.post('/api/regulations/law-preview',json={'category':'agreement'},headers=self.h).status_code,400)
  result=law_api.prepare_law('labor_act',XML)
  with patch('law_api.fetch_law',return_value=(result,XML)):
   r=self.admin.post('/api/regulations/law-preview',json={'category':'labor_act'},headers=self.h)
  self.assertEqual(r.status_code,200);data=r.json
  self.assertIsNone(self.admin.get('/api/regulations/document?category=labor_act').json['document'])
  bad={'category':'labor_act','body':data['body']+'변경','token':'','candidate':data['candidate']}
  self.assertEqual(self.admin.post('/api/regulations/save',json=bad,headers=self.h).status_code,409)
  good={'category':'labor_act','body':data['body'],'token':'','candidate':data['candidate']}
  self.assertEqual(self.admin.post('/api/regulations/save',json=good,headers=self.h).status_code,200)
  with app.db() as c:
   row=c.execute('SELECT xml,metadata FROM law_import_sources WHERE category=?',('labor_act',)).fetchone();self.assertEqual(row['xml'],XML);self.assertIn('20260101',row['metadata'])
  self.assertEqual(self.admin.post('/api/regulations/save',json=good,headers=self.h).status_code,409)
 def test_missing_key(self):
  with patch.dict(os.environ,{},clear=True):
   with self.assertRaisesRegex(law_api.LawApiError,'LAW_API_OC'):law_api.fetch_law('labor_act')
 def test_saved_key_access_override_and_delete(self):
  path='/api/regulations/law-key'
  self.assertEqual(self.viewer.get(path).status_code,403)
  self.assertEqual(self.viewer.post(path,json={'key':'private-oc'},headers=self.vh).status_code,403)
  self.assertEqual(self.admin.post(path,json={'key':'private-oc'}).status_code,403)
  self.assertEqual(self.admin.post(path,json={'key':'bad value'},headers=self.h).status_code,400)
  self.assertEqual(self.admin.post(path,json={'key':'private-oc'},headers=self.h).status_code,200)
  status=self.admin.get(path);self.assertTrue(status.json['stored']);self.assertNotIn('private-oc',status.get_data(as_text=True))
  self.assertNotIn('private-oc',self.admin.get('/api/settings').get_data(as_text=True))
  result=law_api.prepare_law('labor_act',XML)
  with patch.dict(os.environ,{'LAW_API_OC':'other-env'}),patch('law_api.fetch_law',return_value=(result,XML)) as fetch:
   self.assertEqual(self.admin.post('/api/regulations/law-preview',json={'category':'labor_act'},headers=self.h).status_code,200)
   fetch.assert_called_once_with('labor_act','private-oc')
  self.assertEqual(self.admin.post(path,json={'key':''},headers=self.h).status_code,200)
  with patch.dict(os.environ,{'LAW_API_OC':'other-env'}):
   status=self.admin.get(path).json;self.assertFalse(status['stored']);self.assertTrue(status['configured']);self.assertTrue(status['environment'])
if __name__=='__main__':unittest.main()
