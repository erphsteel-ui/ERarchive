import json,os,tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault('ARCHIVE_DATA',tempfile.mkdtemp(prefix='er-migration-'))
import app
from schedule_extract import hwp_text

class MigrationTests(unittest.TestCase):
 def setUp(self):
  with app.db() as c:
   for table in ('schedule_events','schedule_sources','schedule_seen'):c.execute('DELETE FROM '+table)
 def test_migration_reloads_original_and_preserves_human_rows(self):
  files=list((Path(__file__).parent.parent/'upload').glob('*회의자료.hwp'))
  if not files:self.skipTest('real HWP fixture not available')
  raw=files[0].read_bytes();digest=hashlib.sha256(raw).hexdigest();name=digest+'.hwp';sid='hwp:'+digest
  (app.DATA/'schedule_sources'/name).write_bytes(raw)
  old='*전국노동자대회\n11/8\n11/9\n11/10\n11/11'
  with app.db() as c:
   c.execute('INSERT INTO schedule_sources(id,name,kind,text,path,created,status,reference) VALUES(?,?,?,?,?,?,?,?)',(sid,files[0].name,'hwp',old,name,app.stamp(),'legacy','2026-10-26'))
   c.execute('INSERT INTO schedule_seen VALUES(?,?)',(sid,'0.15.1:legacy'))
   for day,state,version,reviewed in [(8,'pending',1,False),(9,'pending',2,True),(10,'published',1,False),(11,'rejected',1,False)]:
    d={'start':f'2026-11-{day:02}','end':f'2026-11-{day:02}','title':'전국노동자대회' if day!=9 else '관리자 직접 수정','row':'1','reviewed':reviewed,'automatic':True}
    c.execute('INSERT INTO schedule_events VALUES(?,?,?,?,?,?,?,?)',(str(day),sid,str(day),json.dumps(d,ensure_ascii=False),state,version,app.stamp(),app.stamp()))
   before={r['id']:dict(r) for r in c.execute("SELECT * FROM schedule_events WHERE id!='8'")}
  app.ingest_schedule(sid,files[0].name,'hwp',old,name,'2026-10-26')
  with app.db() as c:
   self.assertEqual(c.execute("SELECT state FROM schedule_events WHERE id='8'").fetchone()[0],'superseded')
   for eid,row in before.items():self.assertEqual(dict(c.execute('SELECT * FROM schedule_events WHERE id=?',(eid,)).fetchone()),row)
   es=[json.loads(r[0]) for r in c.execute("SELECT data FROM schedule_events WHERE state='pending'")]
   self.assertTrue(any(e['start']=='2026-11-07' and e['title']=='전국노동자대회' for e in es))
   self.assertFalse(any(e['start']=='2026-11-08' and e['title']=='전국노동자대회' for e in es))
   stored=c.execute('SELECT text FROM schedule_sources WHERE id=?',(sid,)).fetchone()[0]
  self.assertEqual(app.ingest_schedule(sid,files[0].name,'hwp',stored,name,'2026-10-26'),0)
 def test_untouched_noise_on_human_date_is_still_retired(self):
  app.ingest_schedule('same','회의','image','단체교섭 2026.11.07\n간담회 2026.11.07')
  with app.db() as c:
   records=c.execute('SELECT * FROM schedule_events').fetchall();human=records[0];untouched=records[1]
   d=json.loads(human['data']);d['reviewed']=True
   c.execute('UPDATE schedule_events SET data=?,version=2 WHERE id=?',(json.dumps(d),human['id']))
   c.execute("UPDATE schedule_seen SET signature='legacy'")
  app.ingest_schedule('same','회의','image','단체교섭 2026.11.07')
  with app.db() as c:
   self.assertEqual(c.execute('SELECT state FROM schedule_events WHERE id=?',(human['id'],)).fetchone()[0],'pending')
   self.assertEqual(c.execute('SELECT state FROM schedule_events WHERE id=?',(untouched['id'],)).fetchone()[0],'superseded')

if __name__=='__main__':unittest.main()
