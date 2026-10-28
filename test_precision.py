import io,json,os,tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('ARCHIVE_DATA',tempfile.mkdtemp(prefix='er-precision-test-'))
import app,vl_adapter
from PIL import Image
from werkzeug.security import generate_password_hash

class PrecisionTests(unittest.TestCase):
 def setUp(self):
  self.c=app.app.test_client();self.guest=app.app.test_client();self.folder=Path(tempfile.mkdtemp())
  with app.db() as c:
   for table in ('precision_jobs','schedule_jobs','schedule_events','schedule_sources','schedule_seen','file_imports','batch_pages','batches','pages','documents'):c.execute('DELETE FROM '+table)
   c.execute("INSERT OR REPLACE INTO users VALUES('precision-admin',?,'admin')",(generate_password_hash('test-password-123'),))
   c.execute("UPDATE settings SET value=? WHERE key='precision_inbox'",(json.dumps({'enabled':True,'path':str(self.folder)}),))
  self.headers={'X-CSRF':self.c.post('/api/login',json={'name':'precision-admin','password':'test-password-123'}).json['csrf']}
  stream=io.BytesIO();Image.new('RGB',(40,50),'blue').save(stream,format='PNG');self.raw=stream.getvalue()
 def queue(self):return app.enqueue_precision(self.raw,'교섭속보.png')[0]
 def process(self):
  with patch.object(app,'recognize_body',return_value={'variants':[{'text':'원래 본문'}]}),patch('vl_adapter.recognize',return_value={'text':'교섭 2026.11.04','raw':{'parsing_res_list':[]},'seconds':2.0}):self.assertTrue(app.process_precision_job())
 def detail(self,h):return self.c.get('/api/precision/'+h).json
 def review(self,h,**changes):
  d=self.detail(h);b=dict(action='apply',version=d['version'],token=d['token'],text=d['result'],destination='schedule');b.update(changes)
  return self.c.post('/api/precision/'+h+'/review',json=b,headers=self.headers)
 def page(self):
  h=hashlib.sha256(self.raw).hexdigest();(app.DATA/'images'/'precision-test.png').write_bytes(self.raw)
  with app.db() as c:
   c.execute('INSERT INTO documents VALUES(?,?,?,?,1)',('precision-doc',json.dumps({'title':'수정한 제목','date':'2026-10-26','state':'published'}),app.stamp(),app.stamp()))
   c.execute('INSERT INTO pages VALUES(?,?,?,?,?,?,0)',('precision-page','precision-doc','precision-test.png',h,'관리자 교정 본문','완료'))
  return h
 def test_folder_stability_dedup_and_admin_only(self):
  (self.folder/'a.png').write_bytes(self.raw);app.scan_precision_inbox(now=0);app.scan_precision_inbox(now=14)
  self.assertEqual(self.c.get('/api/precision').json['jobs'],[])
  app.scan_precision_inbox(now=16);(self.folder/'b.png').write_bytes(self.raw);app.scan_precision_inbox(now=20);app.scan_precision_inbox(now=36)
  jobs=self.c.get('/api/precision').json['jobs'];self.assertEqual(len(jobs),1)
  self.assertEqual(self.guest.get('/api/precision').status_code,401)
  self.assertEqual(self.guest.get('/api/precision/'+jobs[0]['hash']+'/image').status_code,401)
  self.assertEqual(self.c.post('/api/precision/config',json={}).status_code,403)
 def test_completed_vl_does_not_overwrite_and_approval_preserves_metadata(self):
  h=self.page();self.queue();self.process()
  self.assertEqual(self.detail(h)['current'],'관리자 교정 본문');self.assertEqual(self.detail(h)['baseline'],'관리자 교정 본문')
  self.assertEqual(self.review(h).status_code,200)
  with app.db() as c:
   self.assertEqual(c.execute('SELECT text FROM pages').fetchone()[0],'교섭 2026.11.04')
   d=c.execute('SELECT meta,version FROM documents').fetchone();self.assertEqual(json.loads(d[0])['title'],'수정한 제목');self.assertEqual(d[1],2)
   self.assertEqual(c.execute('SELECT text FROM text_history').fetchone()[0],'관리자 교정 본문')
  self.assertEqual(app.enqueue_precision(self.raw,'renamed.png')[1],False)
 def test_concurrent_edit_rejected_without_overwrite(self):
  h=self.page();self.queue();self.process();d=self.detail(h)
  with app.db() as c:c.execute("UPDATE pages SET text='다른 창에서 교정'")
  self.assertEqual(self.review(h,token=d['token']).status_code,409)
  self.assertEqual(self.detail(h)['current'],'다른 창에서 교정')
 def test_keep_preserves_old_text(self):
  h=self.page();self.queue();self.process();self.assertEqual(self.review(h,action='keep').status_code,200)
  self.assertEqual(self.detail(h)['current'],'관리자 교정 본문')
 def test_new_schedule_only_after_review(self):
  h=self.queue();self.process()
  with app.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM schedule_sources').fetchone()[0],0)
  self.assertEqual(self.review(h).status_code,200);app.scan_schedules()
  with app.db() as c:
   self.assertEqual(c.execute('SELECT count(*) FROM documents').fetchone()[0],0)
   self.assertEqual(c.execute('SELECT count(*) FROM batches').fetchone()[0],0)
   self.assertTrue(c.execute("SELECT 1 FROM schedule_events WHERE state='pending'").fetchone())
  self.assertEqual(self.detail(h)['target'],'source')
 def test_new_archive_no_second_ocr_or_automatic_publish(self):
  h=self.queue();self.process();self.assertEqual(self.review(h,destination='archive').status_code,200)
  with patch.object(app,'recognize_body',side_effect=AssertionError('must not rerun')):app.process_batch()
  with app.db() as c:
   self.assertEqual(c.execute('SELECT count(*) FROM documents').fetchone()[0],0)
   self.assertEqual(c.execute('SELECT state FROM batches').fetchone()[0],'review')
   self.assertEqual(json.loads(c.execute('SELECT result FROM batch_pages').fetchone()[0])['variants'][1]['text'],'교섭 2026.11.04')
 def test_failure_retry_and_recovery_pause(self):
  h=self.queue()
  with patch.object(app,'recognize_body',return_value={'variants':[]}),patch('vl_adapter.recognize',side_effect=ValueError('모델 누락')):app.process_precision_job()
  self.assertEqual(self.detail(h)['state'],'failed')
  self.assertEqual(self.c.post('/api/precision/'+h+'/retry',json={},headers=self.headers).status_code,200)
  with app.db() as c:
   c.execute("UPDATE precision_jobs SET state='running'")
   c.execute("UPDATE settings SET value=? WHERE key='precision_inbox'",(json.dumps({'enabled':False,'path':str(self.folder)}),))
  app.recover_precision_jobs();self.assertFalse(app.process_precision_job());self.assertEqual(self.detail(h)['state'],'queued')
 def test_vl_uploaded_real_result_parser(self):
  path=Path(__file__).parent.parent/'upload'/'test_res.json'
  if not path.exists():self.skipTest('local real VL fixture unavailable')
  text=vl_adapter.parse_result(json.loads(path.read_text()));self.assertIn('현대제철비정규직지회',text);self.assertIn('교섭',text)
 def test_worker_real_subprocess_json_only_and_offline(self):
  import sys
  tmp=Path(tempfile.mkdtemp());image=tmp/'input.png';image.write_bytes(self.raw)
  fake="""import json,socket
from pathlib import Path
class Result:
 def save_to_json(self,out):
  Path(out,'result.json').write_text(json.dumps({'parsing_res_list':[{'block_content':'교섭속보 실제 하위 프로세스 검증'}]},ensure_ascii=False),encoding='utf-8')
class PaddleOCRVL:
 def __init__(self,**kw):
  assert kw['pipeline_version']=='v1.6'
  assert kw['vl_rec_model_name']=='PaddleOCR-VL-1.6-0.9B'
  assert kw['layout_detection_model_name']=='PP-DocLayoutV3'
  assert kw['device']=='cpu'
  try:socket.create_connection(('example.com',443))
  except OSError:pass
  else:raise AssertionError('network must be blocked')
 def predict(self,path):return [Result()]
"""
  (tmp/'paddleocr.py').write_text(fake)
  with patch.dict(os.environ,{'PYTHONPATH':str(tmp)}),patch('vl_adapter.status',return_value={'ready':True}),patch('vl_adapter.paths',return_value=(tmp,Path(sys.executable),tmp/'PP-DocLayoutV3',tmp/'PaddleOCR-VL-1.6')):
   result=vl_adapter.recognize(image)
  self.assertIn('실제 하위 프로세스 검증',result['text'])
 def test_folder_conflicts_both_ways(self):
  for endpoint in ('inbox','schedule/intake/config'):
   self.assertEqual(self.c.post('/api/'+endpoint,json={'path':str(self.folder),'enabled':True},headers=self.headers).status_code,400)

if __name__=='__main__':unittest.main()
