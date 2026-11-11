import io,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('ARCHIVE_DATA',tempfile.mkdtemp(prefix='er-intake-tests-'))
import app
from PIL import Image
from werkzeug.security import generate_password_hash

class IntakeTests(unittest.TestCase):
 def setUp(self):
  self.c=app.app.test_client();self.guest=app.app.test_client()
  self.folder=Path(tempfile.mkdtemp(prefix='er-inbox-'))
  with app.db() as c:
   for table in ['schedule_jobs','schedule_events','schedule_sources','schedule_seen','file_imports','batch_pages','batches','pages','documents']:c.execute('DELETE FROM '+table)
   c.execute("UPDATE settings SET value=? WHERE key='schedule_inbox'",(json.dumps({'enabled':True,'path':str(self.folder)}),))
   c.execute("INSERT OR REPLACE INTO users VALUES('intake-admin',?,'admin')",(generate_password_hash('test-password-123'),))
  self.headers={'X-CSRF':self.c.post('/api/login',json={'name':'intake-admin','password':'test-password-123'}).json['csrf']}
 def raw(self):
  b=io.BytesIO();Image.new('RGB',(80,100),'red').save(b,format='PNG');return b.getvalue()
 def upload(self,raw=None,name='공문.png'):
  return self.c.post('/api/schedule/intake/upload',data={'files':(io.BytesIO(raw or self.raw()),name)},headers=self.headers)
 def result(self):return {'variants':[{'text':'제목 : 철강업종분과위원회 사업장 상집간부 수련회\n일시 : 2026년 11월12일(목) ~13일(금)'}],'selected':0}
 def test_schedule_only_upload_and_source_preview(self):
  self.assertEqual(self.upload().status_code,202)
  with patch.object(app,'recognize_body',return_value=self.result()):self.assertTrue(app.process_schedule_job())
  with app.db() as c:
   self.assertEqual(c.execute('SELECT count(*) FROM documents').fetchone()[0],0)
   self.assertEqual(c.execute('SELECT count(*) FROM batches').fetchone()[0],0)
  data=self.c.get('/api/schedule?month=2026-11').json;e=data['pending'][0]
  self.assertEqual(e['source_name'],'공문.png')
  self.assertEqual(self.c.get('/api/schedule/source/'+e['source']+'?download=1').data,self.raw())
  self.assertEqual(self.guest.get('/api/schedule/source/'+e['source']+'?download=1').status_code,401)
  self.assertEqual(self.guest.get('/api/documents').json,[])
  self.assertEqual(self.upload(name='renamed.png').json['duplicates'],1)
 def test_permissions(self):
  self.assertEqual(self.guest.get('/api/schedule/intake').status_code,401)
  self.assertEqual(self.guest.post('/api/schedule/intake/upload').status_code,401)
  self.assertEqual(self.c.post('/api/schedule/intake/upload').status_code,403)
 def test_failure_retry_and_recovery(self):
  self.upload()
  with patch.object(app,'recognize_body',side_effect=RuntimeError('인식 오류')):app.process_schedule_job()
  job=self.c.get('/api/schedule/intake').json['jobs'][0];self.assertEqual(job['state'],'failed')
  self.assertEqual(self.c.post('/api/schedule/intake/'+job['hash']+'/retry',json={},headers=self.headers).status_code,200)
  with app.db() as c:c.execute("UPDATE schedule_jobs SET state='running'")
  app.recover_schedule_jobs()
  with patch.object(app,'recognize_body',return_value=self.result()):app.process_schedule_job()
  self.assertEqual(self.c.get('/api/schedule/intake').json['jobs'][0]['state'],'done')
 def test_folder_stability_and_renamed_duplicate(self):
  (self.folder/'letter.png').write_bytes(self.raw());app.scan_schedule_inbox(now=0)
  self.assertEqual(self.c.get('/api/schedule/intake').json['jobs'],[])
  app.scan_schedule_inbox(now=16)
  self.assertEqual(len(self.c.get('/api/schedule/intake').json['jobs']),1)
  (self.folder/'renamed.png').write_bytes(self.raw());app.scan_schedule_inbox(now=20);app.scan_schedule_inbox(now=36)
  self.assertEqual(len(self.c.get('/api/schedule/intake').json['jobs']),1)
 def test_folder_overlap_rejected_both_directions(self):
  with app.db() as c:old=json.loads(c.execute("SELECT value FROM settings WHERE key='inbox'").fetchone()[0])
  other=Path(tempfile.mkdtemp(prefix='er-archive-inbox-'))
  try:
   with app.db() as c:c.execute("UPDATE settings SET value=? WHERE key='inbox'",(json.dumps({'enabled':True,'path':str(other)}),))
   self.assertEqual(self.c.post('/api/schedule/intake/config',json={'enabled':True,'path':str(other)},headers=self.headers).status_code,400)
   self.assertEqual(self.c.post('/api/inbox',json={'enabled':True,'path':str(self.folder)},headers=self.headers).status_code,400)
  finally:
   with app.db() as c:c.execute("UPDATE settings SET value=? WHERE key='inbox'",(json.dumps(old),))
 def test_corrupt_input_does_not_queue(self):
  self.assertEqual(self.upload(b'bad','bad.png').status_code,400)
  self.assertEqual(self.upload(b'SCDSA004','protected.hwp').status_code,400)
  self.assertEqual(self.c.get('/api/schedule/intake').json['jobs'],[])
 def test_hwp_filename_and_original(self):
  raw=bytes.fromhex('d0cf11e0a1b11ae1')+b'fake-ole-for-mocked-parser'
  self.assertEqual(self.upload(raw,'회의결과(1).hwp').status_code,202)
  with patch('schedule_intake.hwp_text',return_value='집행부 회의 : 2026.11.12'):app.process_schedule_job()
  e=self.c.get('/api/schedule?month=2026-11').json['pending'][0]
  self.assertEqual(e['source_name'],'회의결과(1).hwp')
  r=self.c.get('/api/schedule/source/'+e['source']+'?download=1')
  self.assertEqual(r.data,raw);self.assertIn('attachment',r.headers['Content-Disposition'])

if __name__=='__main__':unittest.main()
