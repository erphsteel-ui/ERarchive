import os,tempfile,unittest,io,json
from unittest.mock import patch
os.environ['ARCHIVE_DATA']=tempfile.mkdtemp(prefix='er-test-')
import app
from PIL import Image
from werkzeug.security import generate_password_hash
class Tests(unittest.TestCase):
 def setUp(self):
  self.c=app.app.test_client();self.v=app.app.test_client()
  with app.db() as c:
   c.execute('DELETE FROM file_imports');c.execute('DELETE FROM batches');c.execute('DELETE FROM pages');c.execute('DELETE FROM documents');c.execute('DELETE FROM users')
   for u,r in [('admin','admin'),('reader','viewer')]: c.execute('INSERT INTO users VALUES(?,?,?)',(u,generate_password_hash('example-password'),r))
  self.h={'X-CSRF':self.c.post('/api/login',json={'name':'admin','password':'example-password'}).json['csrf']}
  self.vh={'X-CSRF':self.v.post('/api/login',json={'name':'reader','password':'example-password'}).json['csrf']}
 def img(self,color):
  b=io.BytesIO();Image.new('RGB',(40,40),color).save(b,format='PNG');b.seek(0);return b
 def upload(self,colors=['red','blue']):
  r=self.c.post('/api/upload',data={'files':[(self.img(x),x+'.png') for x in colors]},headers=self.h)
  self.assertEqual(r.status_code,200,r.json);return r.json['id']
 def doc(self,did): return next(d for d in self.c.get('/api/documents').json if d['id']==did)
 def save(self,d,state='published'):
  d=dict(d);d['state']=state;d['title']='분류된 자료';d['order']=[p['id'] for p in d['pages']];return self.c.post('/api/documents/'+d['id'],json=d,headers=self.h)
 def test_company_category_and_statement_kind(self):
  did=self.upload(['purple']);doc=self.doc(did);doc.update(category='회사',kind='담화문')
  self.assertEqual(self.save(doc).status_code,200)
  saved=self.doc(did);self.assertEqual(saved['categories'],['회사']);self.assertEqual(saved['kind'],'담화문')
 def test_permissions_and_visibility(self):
  self.assertEqual(app.app.test_client().get('/api/documents').json,[])
  did=self.upload();d=self.doc(did);pid=d['pages'][0]['id']
  self.assertEqual(self.v.get('/api/documents').json,[])
  self.assertEqual(self.v.get('/api/image/'+pid).status_code,404)
  self.assertEqual(self.v.post('/api/documents/'+did,json=d,headers=self.vh).status_code,403)
  self.assertEqual(self.c.post('/api/documents/'+did,json=d).status_code,403)
  self.assertEqual(self.save(d).status_code,200)
  self.assertEqual(len(self.v.get('/api/documents').json),1)
  self.assertNotIn('note',self.v.get('/api/documents').json[0])
  self.assertEqual(self.v.get('/api/image/'+pid).status_code,200)
 def test_inline_title_permission_and_version(self):
  did=self.upload(['purple']);before=self.doc(did)
  url='/api/documents/'+did+'/title';payload={'version':before['version'],'title':'새 제목'}
  self.assertEqual(self.v.post(url,json=payload,headers=self.vh).status_code,403)
  self.assertEqual(self.c.post(url,json=payload,headers=self.h).status_code,200)
  after=self.doc(did);self.assertEqual(after['title'],'새 제목');self.assertEqual(after['version'],before['version']+1)
  for key in ('state','kind','category','publishers','pages'):self.assertEqual(after.get(key),before.get(key))
  self.assertEqual(self.c.post(url,json=payload,headers=self.h).status_code,409)
  self.assertEqual(self.c.post(url,json={'version':after['version'],'title':'  '},headers=self.h).status_code,400)
 def test_anonymous_boundaries(self):
  guest=app.app.test_client()
  self.assertEqual(guest.get('/api/me').json['role'],'viewer')
  did=self.upload(['orange']);d=self.doc(did);pid=d['pages'][0]['id']
  self.assertEqual(guest.get('/api/documents').json,[])
  self.assertEqual(guest.get('/api/image/'+pid).status_code,404)
  for path in ['/api/upload','/api/settings','/api/documents/'+did,'/api/documents/'+did+'/delete','/api/documents/'+did+'/split','/api/documents/'+did+'/merge']:
   self.assertEqual(guest.post(path,json={}).status_code,401,path)
  self.assertEqual(guest.get('/api/audit').status_code,401)
  self.assertEqual(self.save(d).status_code,200)
  visible=guest.get('/api/documents').json[0]
  for field in ['note','company','site','period']: self.assertNotIn(field,visible)
  self.assertEqual(guest.get('/api/image/'+pid).status_code,200)
 def test_conservative_classification(self):
  orgs=['금속노조 충남지부 현대제철지회','금속노조 현대자동차지부','전국금속노동조합']
  self.assertEqual(app.suggest('본문',orgs,'강 철 의 함 성')['publishers'],[orgs[0]])
  self.assertEqual(app.suggest('본문',orgs,'현자지부 소식')['publishers'],[orgs[1]])
  self.assertEqual(app.suggest('전국금속노동조합',orgs,'오늘의 소식')['publishers'],[])
  self.assertEqual(app.suggest('',orgs,'전국금속노동조합과 함께 투쟁한다')['publishers'],[])
  self.assertEqual(app.suggest('',orgs,'발행처: 전국금속노동조합')['publishers'],[orgs[2]])
  self.assertEqual(app.suggest('',orgs,'강철의 함성\n전국금속노동조합')['publishers'],[])
  self.assertEqual(app.suggest('',orgs,'')['title'],'')
  self.assertEqual(app.suggest('',orgs,'실천하는 노조')['title'],'')
 def test_regional_ocr_and_alias(self):
  org='금속노조 충남지부 현대제철지회'
  regions={'header':'실천하는노조\n2026.10.21.', 'title':'강철의 함성', 'issuer':'전국금속노동조합 충남지부\n현대제철지회'}
  result=app.suggest('',[org,'전국금속노동조합'],regions)
  self.assertEqual(result['title'],'강철의 함성');self.assertEqual(result['publishers'],[org])
  full='전국금속노동조합 충남지부 현대제철지회'
  self.assertEqual(app.suggest('',[full],regions)['publishers'],[full])
  with tempfile.TemporaryDirectory() as tmp:
   path=app.Path(tmp)/'sample.png';Image.new('RGB',(1200,1800),'white').save(path)
   with patch.object(app,'ocr',side_effect=[('head','ok'),('title','ok'),('issuer','ok')]) as run:
    self.assertEqual(app.tesseract_header_ocr(path),{'header':'head','title':'title','issuer':'issuer'})
    self.assertEqual([call.args[1] for call in run.call_args_list],[3,7,11])
 def test_reclassification_preview(self):
  did=self.upload(['purple']);before=self.doc(did)
  with app.db() as c:
   c.execute('UPDATE ocr_runs SET result=?',(json.dumps({'regions':{'header':'','title':'강철의 함성','issuer':''}}),))
  with patch.object(app,'header_ocr',side_effect=AssertionError('stored OCR must be reused')):
   r=self.c.post('/api/documents/'+did+'/recognize',json={},headers=self.h)
  self.assertEqual(r.status_code,200);self.assertEqual(r.json['title'],'강철의 함성')
  self.assertEqual(before,self.doc(did))
  self.assertEqual(app.app.test_client().post('/api/documents/'+did+'/recognize',json={}).status_code,401)
  self.assertEqual(self.v.post('/api/documents/'+did+'/recognize',json={},headers=self.vh).status_code,403)
  self.assertEqual(self.c.post('/api/documents/'+did+'/recognize',json={}).status_code,403)
 def test_reader_categories(self):
  cases={'금속노조 충남지부 현대제철지회':'집행부','금속노조 인천지부 현대제철지회':'집행부','민주노동자회':'제조직','단하나':'제조직','현대자동차지부':'그룹사','기아차지부':'그룹사','포스코노동조합':'기타','노사협의회':'기타'}
  for pub,category in cases.items():self.assertEqual(app.categories_for({'publishers':[pub]}),[category])
  self.assertEqual(app.categories_for({'publishers':[]}),['기타'])
  self.assertEqual(app.categories_for({'publishers':['단하나'],'category':'기타'}),['기타'])
  did=self.upload(['yellow']);d=self.doc(did);d['category']='제조직';self.assertEqual(self.save(d).status_code,200)
  self.assertEqual(self.doc(did)['categories'],['제조직'])
  d=self.doc(did);d['category']='invalid';self.assertEqual(self.save(d).status_code,400)
 def test_duplicate_and_invalid(self):
  self.upload(['red']);r=self.c.post('/api/upload',data={'files':(self.img('red'),'again.png')},headers=self.h);self.assertEqual(r.status_code,409)
  r=self.c.post('/api/upload',data={'files':(io.BytesIO(b'<script>bad</script>'),'bad.jpg')},headers=self.h);self.assertEqual(r.status_code,400)
 def test_order_text_and_conflict(self):
  did=self.upload();d=self.doc(did);old=dict(d);d['pages'].reverse();d['texts']={d['pages'][0]['id']:'주휴수당 검색 테스트'}
  self.assertEqual(self.save(d).status_code,200);n=self.doc(did);self.assertEqual(n['pages'][0]['id'],d['pages'][0]['id']);self.assertIn('주휴수당',n['pages'][0]['text']);self.assertEqual(self.save(old).status_code,409)
 def test_split_merge_delete(self):
  did=self.upload();d=self.doc(did)
  r=self.c.post('/api/documents/'+did+'/split',json={'pages':[d['pages'][1]['id']]},headers=self.h);self.assertEqual(r.status_code,200);nid=r.json['id'];self.assertEqual(len(self.doc(nid)['pages']),1)
  r=self.c.post('/api/documents/'+did+'/merge',json={'source':nid},headers=self.h);self.assertEqual(r.status_code,200);self.assertEqual(len(self.doc(did)['pages']),2)
  self.assertEqual(self.c.post('/api/documents/'+did+'/delete',json={},headers=self.h).status_code,200);self.assertEqual(self.c.get('/api/documents').json,[])
 def test_ocr_unavailable_and_masthead(self):
  d=self.doc(self.upload(['green']));self.assertTrue(d['pages'][0]['status'])
  s=app.suggest('강철의 함성\n금속노조 충남지부 현대제철지회\n2026.10.21. 26-29호\n임단협', ['금속노조 충남지부 현대제철지회'])
  self.assertEqual(s['date'],'2026-10-21');self.assertEqual(s['publishers'],['금속노조 충남지부 현대제철지회']);self.assertEqual(s['title'],'강철의 함성')
 def test_account_and_static(self):
  self.assertEqual(self.c.get('/').status_code,200);self.assertEqual(self.c.get('/static/app.js').status_code,200)
  self.assertEqual(self.v.get('/api/audit').status_code,403)
  self.assertEqual(self.v.post('/api/settings',json={'organizations':[]},headers=self.vh).status_code,403)
  self.assertEqual(self.c.post('/api/logout',json={},headers=self.h).status_code,200);self.assertEqual(self.c.get('/api/documents').status_code,200)
if __name__=='__main__':unittest.main()
