import json, sqlite3, threading, unittest, time
import app
from schedule_extract import extract_events,subject_from
from test_schedule import ScheduleTests

class StabilityTests(unittest.TestCase):
 def test_connection_closes_and_rollback(self):
  c=app.db()
  with self.assertRaises(RuntimeError):
   with c:
    c.execute("INSERT OR REPLACE INTO settings VALUES('rollback-test','x')")
    raise RuntimeError('rollback')
  with self.assertRaises(sqlite3.ProgrammingError):c.execute('SELECT 1')
  with app.db() as d:
   self.assertIsNone(d.execute("SELECT value FROM settings WHERE key='rollback-test'").fetchone())
   self.assertEqual(d.execute('PRAGMA journal_mode').fetchone()[0].lower(),'wal')
   self.assertEqual(d.execute('PRAGMA busy_timeout').fetchone()[0],30000)
 def test_login_prunes_expired_addresses(self):
  old=time.time()-301
  with app.LOCK:
   app.ATTEMPTS.clear();app.ATTEMPTS['stale']=[old]
  app.app.test_client().post('/api/login',json={'name':'missing','password':'bad'})
  self.assertNotIn('stale',app.ATTEMPTS)
 def test_title_and_range(self):
  self.assertEqual(subject_from('차기 회의 : 10/29'),'')
  self.assertEqual(extract_events('차기 회의 : 2026.10.29'),[])
  es=extract_events('2026.10.29 ~ 2026.10.30 및 통일위원회 수련회\n2026.10.30 통일위원회 수련회')
  self.assertEqual([(x['start'],x['end'],x['title']) for x in es],[('2026-10-29','2026-10-30','통일위원회 수련회')])

class ScheduleSafetyTests(ScheduleTests):
 def test_cross_source_rejected_prevents_reappearance(self):
  text='현대제철 포항지회 : 2026.10.30 확대간부 수련회'
  app.ingest_schedule('cross1','one','image',text)
  e=self.admin.get('/api/schedule').json['pending'][0]
  r=self.admin.post('/api/schedule/reject-candidates',json={'items':[{'id':e['id'],'version':e['version']}]},headers=self.headers)
  self.assertEqual(r.status_code,200)
  app.ingest_schedule('cross2','two','image',text)
  self.assertEqual(self.admin.get('/api/schedule').json['pending'],[])
 def test_bulk_atomic_conflict_and_auth(self):
  for sid,text in [('a','집행부 회의 2026.10.30'),('b','집행부 회의 2026.10.31')]:app.ingest_schedule(sid,sid,'image',text)
  candidates=self.admin.get('/api/schedule').json['pending'];self.assertEqual(len(candidates),2)
  items=[{'id':e['id'],'version':e['version']} for e in candidates]
  self.assertEqual(self.guest.post('/api/schedule/reject-candidates',json={'items':items}).status_code,401)
  bad=[dict(x) for x in items];bad[1]['version']+=1
  self.assertEqual(self.admin.post('/api/schedule/reject-candidates',headers=self.headers,json={'items':bad}).status_code,409)
  self.assertEqual(len(self.admin.get('/api/schedule').json['pending']),2)
  self.assertEqual(self.admin.post('/api/schedule/reject-candidates',headers=self.headers,json={'items':items}).status_code,200)
  self.assertEqual(len(self.admin.get('/api/schedule').json['pending']),0)
