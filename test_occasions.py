import os,tempfile,unittest,datetime
os.environ.setdefault('ARCHIVE_DATA',tempfile.mkdtemp(prefix='occasions-'))
import app
from werkzeug.security import generate_password_hash
class OccasionTests(unittest.TestCase):
 def setUp(self):
  with app.db() as c:
   c.execute('DELETE FROM occasion_notices');c.execute("INSERT OR REPLACE INTO users VALUES('occadmin',?,'admin')",(generate_password_hash('example-password'),));c.execute("INSERT OR REPLACE INTO users VALUES('occviewer',?,'viewer')",(generate_password_hash('example-password'),))
  self.admin=app.app.test_client();self.viewer=app.app.test_client();self.guest=app.app.test_client();self.h={'X-CSRF':self.admin.post('/api/login',json={'name':'occadmin','password':'example-password'}).json['csrf']};self.vh={'X-CSRF':self.viewer.post('/api/login',json={'name':'occviewer','password':'example-password'}).json['csrf']}
 def test_create_visibility_update_conflict_and_delete(self):
  date=(datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date()+datetime.timedelta(days=2)).isoformat();body={'title':'결혼식','kind':'경사','date':date,'note':'안내'}
  self.assertEqual(self.guest.post('/api/occasions/save',json=body).status_code,401);self.assertEqual(self.viewer.post('/api/occasions/save',json=body,headers=self.vh).status_code,403);self.assertEqual(self.admin.post('/api/occasions/save',json=body).status_code,403)
  result=self.admin.post('/api/occasions/save',json=body,headers=self.h);self.assertEqual(result.status_code,200);item=self.guest.get('/api/occasions').json['items'][0];self.assertEqual(item['title'],'결혼식')
  self.assertEqual(self.admin.post('/api/occasions/save',json={**body,'id':item['id'],'version':1,'title':'수정'},headers=self.h).status_code,200)
  self.assertEqual(self.admin.post('/api/occasions/delete',json={'id':item['id'],'version':1},headers=self.h).status_code,409)
  self.assertEqual(self.admin.post('/api/occasions/delete',json={'id':item['id'],'version':2},headers=self.h).status_code,200);self.assertEqual(self.guest.get('/api/occasions').json['items'],[])
 def test_input_validation_and_calendar_separation(self):
  self.assertEqual(self.admin.post('/api/occasions/save',json={'title':'x','kind':'경사','date':'2026-02-30'},headers=self.h).status_code,400)
  self.assertEqual(self.admin.post('/api/occasions/save',json={'title':'x','kind':'경사','date':'2999-01-01'},headers=self.h).status_code,200)
  self.assertFalse(any(e['title']=='x' for e in self.guest.get('/api/schedule?month=2999-01').json['events']))
 def test_structured_fields_past_and_legacy(self):
  today=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date();past=(today-datetime.timedelta(days=1)).isoformat();future=(today+datetime.timedelta(days=1)).isoformat()
  old={'title':'기존 내용','kind':'기타','date':past,'note':'이전 안내'}
  self.assertEqual(self.admin.post('/api/occasions/save',json=old,headers=self.h).status_code,200)
  body={'category':'조사','subType':'부고','targetName':'홍길동 수석','relation':'부친','title':'','date':future,'location':'포항','content':'안내\nhttps://example.com'}
  self.assertEqual(self.admin.post('/api/occasions/save',json=body,headers=self.h).status_code,200)
  data=self.guest.get('/api/occasions').json['items'];self.assertEqual(len(data),1);self.assertEqual(data[0]['title'],'홍길동 수석 부친부고');self.assertEqual(data[0]['content'],body['content'])
  pastrows=self.guest.get('/api/occasions?period=past').json['items'];self.assertEqual(pastrows[0]['title'],'기존 내용');self.assertEqual(pastrows[0]['subType'],'');self.assertEqual(pastrows[0]['content'],'이전 안내')
  self.assertEqual(self.guest.get('/api/occasions?period=bad').status_code,400)
  update={'id':data[0]['id'],'version':1,'title':'수정','kind':'조사','date':future,'note':'변경'}
  self.assertEqual(self.admin.post('/api/occasions/save',json=update,headers=self.h).status_code,200)
  changed=self.guest.get('/api/occasions').json['items'][0];self.assertEqual(changed['targetName'],'홍길동 수석');self.assertEqual(changed['location'],'포항')
 def test_schema_migrates_existing_rows(self):
  import sqlite3,subprocess,sys,json
  with tempfile.TemporaryDirectory(prefix='old-occasion-') as folder:
   c=sqlite3.connect(os.path.join(folder,'archive.db'));c.execute('CREATE TABLE occasion_notices(id TEXT PRIMARY KEY,title TEXT NOT NULL,kind TEXT NOT NULL,event_date TEXT NOT NULL,note TEXT NOT NULL,version INTEGER NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL)');c.execute("INSERT INTO occasion_notices VALUES('old','기존 제목','기타','2999-01-01','기존 안내',1,'a','a')");c.commit();c.close()
   env=dict(os.environ,ARCHIVE_DATA=folder);code="import app,json; print(json.dumps(app.app.test_client().get('/api/occasions').json,ensure_ascii=False))"
   data=json.loads(subprocess.check_output([sys.executable,'-c',code],cwd=os.path.dirname(__file__),env=env,text=True));item=data['items'][0]
   self.assertEqual((item['title'],item['content'],item['category']),('기존 제목','기존 안내','기타'));self.assertEqual(item['targetName'],'')
if __name__=='__main__':unittest.main()
