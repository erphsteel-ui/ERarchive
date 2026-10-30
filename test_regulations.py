import os,tempfile,unittest,subprocess,sys,json,io,zipfile
from unittest.mock import patch
os.environ.setdefault('ARCHIVE_DATA',tempfile.mkdtemp(prefix='er-regulations-'))
import app,regulations
from regulations_index import parse_document
from werkzeug.security import generate_password_hash

class RegulationTests(unittest.TestCase):
 def setUp(self):
  with app.db() as c:
   c.execute('DELETE FROM regulation_articles');c.execute('DELETE FROM regulation_documents')
   c.execute("INSERT OR REPLACE INTO users VALUES('regadmin',?,'admin')",(generate_password_hash('reg-admin-password'),))
   c.execute("INSERT OR REPLACE INTO users VALUES('regreader',?,'viewer')",(generate_password_hash('reg-reader-password'),))
  self.admin=app.app.test_client();self.reader=app.app.test_client();self.guest=app.app.test_client()
  self.h={'X-CSRF':self.admin.post('/api/login',json={'name':'regadmin','password':'reg-admin-password'}).json['csrf']}
  self.rh={'X-CSRF':self.reader.post('/api/login',json={'name':'regreader','password':'reg-reader-password'}).json['csrf']}
 def save(self,category,body,token=''):
  return self.admin.post('/api/regulations/save',json={'category':category,'body':body,'token':token},headers=self.h)
 def test_read_access_and_admin_write_permissions(self):
  self.assertEqual(self.guest.get('/api/regulations/archive').status_code,200)
  self.assertEqual(self.reader.get('/api/regulations/archive').status_code,200)
  self.assertEqual(self.reader.get('/api/regulations/document?category=labor_act').status_code,403)
  self.assertEqual(self.admin.get('/api/regulations/archive').status_code,200)
 def test_preservation_and_parser_boundaries(self):
  inline=parse_document('제50조(근로시간) ① 1주 40시간\n제51조 [휴일] 휴일 안내')
  self.assertEqual(inline[0]['title'],'제50조(근로시간)');self.assertIn('① 1주 40시간',inline[0]['text'])
  raw='머리말\n\n제1장 총칙\n제2절 근로조건\n제1조(목적)\n① 본문은 제2조에 따른다.\n제2조 [근로시간]\n1. 근로시간\n가. 세부 내용\n제2조의2(휴가)\n② 휴가\n부칙\n시행 관련\n[별표 1]\n표 내용\n'
  parts=parse_document(raw)
  self.assertEqual(''.join(item['text'] for item in parts),raw)
  self.assertEqual([p['number'] for p in parts if p['kind']=='article'],['1','2','2의2'])
  self.assertEqual(next(p for p in parts if p['number']=='1')['chapter'],'제1장 총칙')
  self.assertEqual(next(p for p in parts if p['number']=='1')['section'],'제2절 근로조건')
  components=next(p for p in parts if p['number']=='2')['components']
  self.assertEqual([part['kind'] for part in components],['호','목'])
  self.assertTrue(any(p['kind']=='appendix' and '부칙' in p['text'] for p in parts))
  self.assertTrue(any(p['kind']=='appendix' and '별표' in p['text'] for p in parts))
  self.assertTrue(any(p['review'] and '머리말' in p['text'] for p in parts))
  self.assertEqual(len([p for p in parse_document('제1조 에 따른다\n평문\n') if p['kind']=='article']),0)
  self.assertEqual(self.save('agreement',raw).status_code,200)
  with app.db() as c:
   stored=c.execute("SELECT body FROM regulation_documents WHERE category='agreement'").fetchone()[0]
   rebuilt=''.join(row[0] for row in c.execute("SELECT body FROM regulation_articles WHERE category='agreement' ORDER BY position"))
  self.assertEqual(stored,raw);self.assertEqual(rebuilt,raw)
 def test_preview_permissions_replace_and_search(self):
  body='제56조(연장근로)\n① 급여와 근로시간\n제 2 조 [휴가]\n첫 내용\n'
  self.assertEqual(self.guest.post('/api/regulations/save',json={}).status_code,401)
  self.assertEqual(self.reader.post('/api/regulations/preview',json={},headers=self.rh).status_code,403)
  preview=self.admin.post('/api/regulations/preview',json={'category':'labor_act','body':body},headers=self.h).json
  self.assertEqual(preview['article_count'],2);self.assertEqual(''.join(x['text'] for x in preview['items']),body)
  self.assertEqual(self.save('labor_act',body).status_code,200)
  self.assertEqual(self.save('union_act','제3조(근로시간)\n근로시간 언급').status_code,200)
  for term in ('제56조','56조','제 56 조'):
   result=self.admin.get('/api/regulations/archive',query_string={'q':term}).json;self.assertEqual(result['items'][0]['number'],'56')
  result=self.admin.get('/api/regulations/archive?q=근로시간').json
  self.assertEqual(result['items'][0]['category'],'union_act');self.assertEqual(result['counts']['labor_act'],1);self.assertEqual(result['counts']['union_act'],1)
  filtered=self.admin.get('/api/regulations/archive?q=근로시간&category=labor_act').json
  self.assertEqual(len(filtered['items']),1);self.assertEqual(filtered['total'],2)
  token=self.admin.get('/api/regulations/document?category=labor_act').json['document']['token']
  self.assertEqual(self.save('labor_act','제7조(새 조문)\n새 원문',token).status_code,200)
  self.assertEqual(self.save('labor_act','제8조(충돌)',token).status_code,409)
  self.assertEqual(self.admin.get('/api/regulations/archive?q=연장근로').json['items'],[])
  self.assertEqual(len(self.admin.get('/api/regulations/archive?category=labor_act').json['items']),1)
  self.assertEqual(self.admin.get('/api/regulations/document?category=labor_act').json['document']['body'],'제7조(새 조문)\n새 원문')
 def test_failed_update_rolls_back_and_html_is_data(self):
  body='제1조(목적)\n<script>alert(1)</script>'
  self.assertEqual(self.save('agreement',body).status_code,200)
  token=self.admin.get('/api/regulations/document?category=agreement').json['document']['token']
  original=regulations.store_document
  def fail(*args):original(*args);raise RuntimeError('test failure')
  with patch('regulations.store_document',side_effect=fail):
   with self.assertLogs(app.app.logger,level='ERROR'):self.assertEqual(self.save('agreement','제2조(교체)',token).status_code,500)
  result=self.admin.get('/api/regulations/archive?category=agreement').json
  self.assertIn('<script>alert(1)</script>',result['items'][0]['body']);self.assertEqual(result['items'][0]['number'],'1')
  self.assertEqual(self.admin.get('/api/regulations/document?category=agreement').json['document']['body'],body)
 def test_legacy_migration_is_safe_and_non_destructive(self):
  with tempfile.TemporaryDirectory(prefix='er-migrate-') as folder:
   script='''import os,sqlite3,json\np=os.path.join(os.environ["ARCHIVE_DATA"],"archive.db");c=sqlite3.connect(p);c.execute("CREATE TABLE regulation_versions(category TEXT,version INTEGER,title TEXT,effective_date TEXT,source TEXT,body TEXT,created TEXT,actor TEXT,PRIMARY KEY(category,version))");c.executemany("INSERT INTO regulation_versions VALUES(?,?,?,?,?,?,?,?)",[("labor_act",1,"법","","","제1조(옛 내용)\\n원문","2025-01-01","a"),("labor_act",2,"법","","","제2조(현재 내용)\\n보존","2026-01-01","a"),("work_rules",1,"구분 불명","","","제1조(구분 불명)\\n원문","2026-01-01","a"),("labor_decree",1,"시행령","","","원문","2026-01-01","a")]);c.commit();c.close();import app\nwith app.db() as c:\n row=c.execute("SELECT body FROM regulation_documents WHERE category='labor_act'").fetchone();print(json.dumps({'body':row[0],'legacy':c.execute('SELECT count(*) FROM regulation_versions').fetchone()[0],'unknown':c.execute("SELECT count(*) FROM regulation_documents WHERE category IN ('work_general','work_technical')").fetchone()[0],'indexed':''.join(r[0] for r in c.execute("SELECT body FROM regulation_articles WHERE category='labor_act' ORDER BY position"))},ensure_ascii=False))'''
   env=dict(os.environ,ARCHIVE_DATA=folder);out=subprocess.check_output([sys.executable,'-c',script],cwd=os.path.dirname(__file__),env=env,text=True)
   data=json.loads(out);self.assertEqual(data['body'],'제2조(현재 내용)\n보존');self.assertEqual(data['legacy'],4);self.assertEqual(data['unknown'],0);self.assertEqual(data['indexed'],data['body'])
 def test_file_extraction_and_permissions(self):
  for encoding in ('utf-8-sig','cp949'):
   result=self.admin.post('/api/regulations/extract',data={'file':(io.BytesIO('제50조(근로시간)\n주 40시간'.encode(encoding)),'rules.txt')},headers=self.h)
   self.assertEqual(result.status_code,200);self.assertIn('근로시간',result.json['text'])
  buffer=io.BytesIO()
  with zipfile.ZipFile(buffer,'w') as archive:archive.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>제50조(근로시간)</w:t></w:r></w:p><w:p><w:r><w:t>주 40시간</w:t></w:r></w:p></w:body></w:document>')
  result=self.admin.post('/api/regulations/extract',data={'file':(io.BytesIO(buffer.getvalue()),'rules.docx')},headers=self.h)
  self.assertEqual(result.json['text'],'제50조(근로시간)\n주 40시간')
  for filename in ('bad.docx','bad.hwp'):
   self.assertEqual(self.admin.post('/api/regulations/extract',data={'file':(io.BytesIO(b'bad'),filename)},headers=self.h).status_code,400)
  self.assertEqual(self.reader.post('/api/regulations/extract',data={},headers=self.rh).status_code,403)
  self.assertEqual(self.admin.post('/api/regulations/extract',data={'file':(io.BytesIO(b'x'*(10*1024*1024+1)),'big.txt')},headers=self.h).status_code,413)
 def test_manual_append_counts_and_conflict(self):
  self.assertEqual(self.save('agreement','머리말\n제1조(목적)\n근로시간 협의').status_code,200)
  token=self.admin.get('/api/regulations/document?category=agreement').json['document']['token']
  data={'category':'agreement','mode':'manual','title':'운영 지침','body':'근로시간 안내 <b>문자열</b>','token':token}
  self.assertEqual(self.admin.post('/api/regulations/save',json=data,headers=self.h).status_code,200)
  self.assertEqual(self.admin.post('/api/regulations/save',json=data,headers=self.h).status_code,409)
  result=self.guest.get('/api/regulations/archive?q=근로시간&category=agreement').json
  self.assertEqual(result['total'],2);self.assertEqual(result['counts']['agreement'],2)
  self.assertEqual({x['kind'] for x in result['items']},{'article','manual'})
  self.assertIn('<b>문자열</b>',result['items'][1]['body'])
  with app.db() as c:self.assertEqual(c.execute("SELECT count(*) FROM regulation_articles WHERE kind='unstructured'").fetchone()[0],1)
  data['title']='';self.assertEqual(self.admin.post('/api/regulations/save',json=data,headers=self.h).status_code,400)
if __name__=='__main__':unittest.main()
