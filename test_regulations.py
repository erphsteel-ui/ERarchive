import io,os,tempfile,unittest,zipfile
from unittest.mock import patch
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
 def test_search_all_categories_uses_latest_registered_version(self):
  def save(category,body,base=0):
   return self.admin.post('/api/regulations',json=self.payload(category=category,base_version=base,body=body),headers=self.h)
  self.assertEqual(save('labor_act','제1조 (근로시간)\n근로시간 규정').status_code,200)
  self.assertEqual(save('labor_decree','제2조 (근로시간)\n시행령 내용').status_code,200)
  self.assertEqual(save('agreement','제3조 (근로시간)\n과거 내용').status_code,200)
  self.assertEqual(save('agreement','제3조 (협약)\n변경된 근로시간',1).status_code,200)
  self.assertEqual(save('work_rules','제4조 (휴가)\n휴가 내용').status_code,200)
  result=self.guest.get('/api/regulations/search?q=근로시간').json
  self.assertEqual([item['category'] for item in result['items']],['labor_act','labor_decree','agreement'])
  self.assertEqual(result['items'][-1]['version'],2)
  self.assertNotIn('과거 내용',result['items'][-1]['articles'][0]['text'])
  self.assertEqual({item['category'] for item in result['missing']},{'union_act','union_decree'})
  self.assertEqual(self.guest.get('/api/regulations/search?q=과거').json['items'],[])
  self.assertEqual(self.guest.get('/api/regulations/search?q=').status_code,400)
 def test_import_docx_and_hwp_requires_admin_and_does_not_save(self):
  xml='''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>제1장 총칙</w:t></w:r></w:p><w:p><w:r><w:t>제1조 (근로시간)</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>하루 근로시간</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'''
  buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w') as archive:archive.writestr('word/document.xml',xml)
  def upload(client,headers,raw,name):return client.post('/api/regulations/extract',data={'file':(io.BytesIO(raw),name)},headers=headers,content_type='multipart/form-data')
  self.assertEqual(upload(self.guest,{},buf.getvalue(),'rules.docx').status_code,401)
  self.assertEqual(upload(self.reader,self.rh,buf.getvalue(),'rules.docx').status_code,403)
  result=upload(self.admin,self.h,buf.getvalue(),'rules.docx');self.assertEqual(result.status_code,200)
  self.assertEqual(result.json['text'],'제1장 총칙\n제1조 (근로시간)\n하루 근로시간')
  with patch('regulations.hwp_text',return_value='제1조 시험 내용') as parser:
   result=upload(self.admin,self.h,b'test-hwp','rules.hwp');self.assertEqual(result.json['text'],'제1조 시험 내용');parser.assert_called_once_with(b'test-hwp')
  self.assertEqual(upload(self.admin,self.h,b'invalid','rules.docx').status_code,400)
  self.assertEqual(upload(self.admin,self.h,b'invalid','rules.doc').status_code,400)
  self.assertIsNone(self.guest.get('/api/regulations?category=agreement').json['entry'])
