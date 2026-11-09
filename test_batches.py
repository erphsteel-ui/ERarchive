import json,unittest,copy
from unittest.mock import patch
import test_app,app,batches
class BatchTests(unittest.TestCase):
 setUp=test_app.Tests.setUp
 img=test_app.Tests.img
 def upload(self):
  r=self.c.post('/api/batches',headers=self.h,data={'files':[(self.img(color),name) for color,name in [('red','a.jpg'),('blue','a_01.jpg'),('green','b.jpg'),('yellow','b_01.jpg')]]})
  self.assertEqual(r.status_code,202,r.json);return r.json['id']
 def get(self,bid):return self.c.get('/api/batches/'+bid).json
 def process(self):
  r={'raw':'강철의 함성','regions':{},'variants':[{'text':'본문 검색 테스트'}],'selected':0,'status':'완료'}
  with patch.object(app,'recognize_body',return_value=r) as mock:
   while app.process_batch():pass
  return mock.call_count
 def test_background_review_atomic_publish(self):
  bid=self.upload();self.assertEqual(self.get(bid)['state'],'queued');self.assertEqual(self.c.get('/api/documents').json,[])
  self.assertEqual(self.process(),4);b=self.get(bid);self.assertEqual(b['state'],'review');self.assertEqual([len(g['pages']) for g in b['groups']],[2,2])
  for i,g in enumerate(b['groups']):g['meta']['title']='홍보물 '+str(i)
  body={'version':b['version'],'groups':b['groups'],'action':'published','confirmed':True}
  bad=copy.deepcopy(body);bad['groups'][0]['pages'].append(bad['groups'][1]['pages'][0]);self.assertEqual(self.c.post('/api/batches/'+bid+'/save',json=bad,headers=self.h).status_code,400)
  self.assertEqual(self.c.get('/api/documents').json,[])
  self.assertEqual(self.c.post('/api/batches/'+bid+'/save',json=body,headers=self.h).status_code,200)
  self.assertEqual(self.c.post('/api/batches/'+bid+'/save',json=body,headers=self.h).status_code,200)
  docs=self.v.get('/api/documents').json;self.assertEqual(len(docs),2);self.assertEqual([len(d['pages']) for d in docs],[2,2]);self.assertIn('검색',docs[0]['pages'][0]['text'])
 def test_excluded_pages_persist_and_publish_only_included(self):
  bid=self.upload();self.process();b=self.get(bid);g=b['groups'][0];excluded=g['pages'][0];g['excluded']=[excluded]
  b['groups'][1]['excluded']=list(b['groups'][1]['pages'])
  payload={'version':b['version'],'groups':b['groups'],'action':'review'}
  r=self.c.post('/api/batches/'+bid+'/save',headers=self.h,json=payload);self.assertEqual(r.status_code,200)
  b=self.get(bid);self.assertEqual(b['groups'][0]['excluded'],[excluded])
  r=self.c.post('/api/batches/'+bid+'/save',headers=self.h,json={'version':b['version'],'groups':b['groups'],'action':'published','confirmed':True});self.assertEqual(r.status_code,200)
  docs=self.v.get('/api/documents').json;self.assertEqual(len(docs),1);self.assertEqual(len(docs[0]['pages']),1);self.assertNotEqual(docs[0]['pages'][0]['id'],excluded)
 def test_password_change_requires_auth_and_correct_current_password(self):
  self.assertEqual(self.c.post('/api/change-password',headers=self.h,json={'current':'wrong','new':'1234'}).status_code,400)
  self.assertEqual(self.v.post('/api/change-password',headers=self.vh,json={'current':'wrong','new':'1234'}).status_code,403)
  with app.db() as c:
   from werkzeug.security import generate_password_hash
   name=c.execute("SELECT name FROM users WHERE role='admin'").fetchone()['name']
   c.execute('UPDATE users SET password=? WHERE name=?',(generate_password_hash('old-password'),name))
  self.assertEqual(self.c.post('/api/change-password',headers=self.h,json={'current':'old-password','new':'1234'}).status_code,200)
  self.assertEqual(self.c.post('/api/login',json={'name':name,'password':'1234'}).status_code,200)
 def test_invalid_exclusion_rejected(self):
  bid=self.upload();self.process();b=self.get(bid);b['groups'][0]['excluded']=['unknown']
  r=self.c.post('/api/batches/'+bid+'/save',headers=self.h,json={'version':b['version'],'groups':b['groups'],'action':'review'});self.assertEqual(r.status_code,400)
 def test_permissions_duplicate_and_recovery(self):
  bid=self.upload();b=self.get(bid);guest=app.app.test_client()
  for path in ['/api/batches','/api/batches/'+bid,'/api/batch-image/'+b['pages'][0]['id']]:self.assertEqual(guest.get(path).status_code,401)
  self.assertEqual(self.v.get('/api/batches').status_code,403)
  r=self.c.post('/api/batches',headers=self.h,data={'files':(self.img('red'),'duplicate.png')});self.assertEqual(r.status_code,409)
  r=self.c.post('/api/upload',headers=self.h,data={'files':(self.img('red'),'duplicate.png')});self.assertEqual(r.status_code,409)
  with patch.object(app,'recognize_body',return_value={'raw':'ok','variants':[{'text':'ok'}],'selected':0,'status':'ok'}):app.process_batch()
  with app.db() as c:
   c.execute("UPDATE batch_pages SET state='running' WHERE id=?",(b['pages'][1]['id'],))
  app.recover_batches();self.assertEqual(self.process(),3)
 def test_retry_and_save_review_conflict(self):
  bid=self.upload()
  with patch.object(app,'recognize_body',side_effect=RuntimeError('test failure')):app.process_batch()
  self.process();b=self.get(bid);self.assertEqual(sum(p['state']=='failed' for p in b['pages']),1)
  body={'version':b['version'],'groups':b['groups'],'action':'review'}
  self.assertEqual(self.c.post('/api/batches/'+bid+'/save',headers=self.h,json=body).status_code,200)
  self.assertEqual(self.c.post('/api/batches/'+bid+'/save',headers=self.h,json=body).status_code,409)
  b=self.get(bid);self.assertEqual(self.c.post('/api/batches/'+bid+'/retry',headers=self.h,json={'version':b['version']}).status_code,200);self.assertEqual(self.process(),1)
 def test_publish_without_draft_or_recognized_title(self):
  bid=self.upload();self.process();b=self.get(bid)
  for g in b['groups']:g['meta']['title']=''
  r=self.c.post('/api/batches/'+bid+'/save',headers=self.h,json={'version':b['version'],'groups':b['groups'],'action':'published','confirmed':True})
  self.assertEqual(r.status_code,200);docs=self.v.get('/api/documents').json
  self.assertEqual(len(docs),2);self.assertTrue(all(d['state']=='published' and d['title']=='제목 미상' for d in docs))
 def test_regroup_reuses_ocr_and_checks_version(self):
  bid=self.upload();self.process();b=self.get(bid)
  with patch.object(app,'recognize_body',side_effect=AssertionError('must not OCR again')):
   r=self.c.post('/api/batches/'+bid+'/regroup',headers=self.h,json={'version':b['version']})
  self.assertEqual(r.status_code,200);self.assertEqual(self.get(bid)['version'],b['version']+1)
  self.assertEqual(self.c.post('/api/batches/'+bid+'/regroup',headers=self.h,json={'version':b['version']}).status_code,409)
  self.assertEqual(self.v.post('/api/batches/'+bid+'/regroup',headers=self.vh,json={}).status_code,403)
 def test_kakao_timestamp_and_page_suffix(self):
  meta={'publishers':[],'title':'','issue':'','date':''}
  pages=[{'id':'a','name':'KakaoTalk_20261007_103638483.jpg','meta':meta},{'id':'b','name':'KakaoTalk_20261007_103638483_01.jpg','meta':meta},{'id':'c','name':'KakaoTalk_20261007_113638483.jpg','meta':meta}]
  grouped=batches.group_pages(pages,'auto');self.assertEqual([g['pages'] for g in grouped],[['a','b'],['c']])
 def test_conflicting_evidence_never_groups(self):
  base={'publishers':['포스코노조'],'issue':'26-01호','title':'소식','date':'2026-10-01'}
  pages=[{'id':'1','name':'a.jpg','meta':base},{'id':'2','name':'a_01.jpg','meta':dict(base,issue='26-02호')}]
  self.assertEqual(len(batches.group_pages(pages,'auto')),2)
  pages[1]['meta']=dict(base);pages[1]['name']='other.jpg';self.assertEqual(len(batches.group_pages(pages,'auto')),1)
  pages[1]['meta']=dict(base,date='2026-10-02');self.assertEqual(len(batches.group_pages(pages,'auto')),2)
if __name__=='__main__':unittest.main()
