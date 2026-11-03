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
if __name__=='__main__':unittest.main()
