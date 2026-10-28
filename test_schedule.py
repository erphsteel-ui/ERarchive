import io,json,os,tempfile,unittest,datetime
os.environ.setdefault('ARCHIVE_DATA',tempfile.mkdtemp(prefix='er-schedule-'))
import app
from schedule_extract import extract_events,hwp_text
from werkzeug.security import generate_password_hash

class ScheduleTests(unittest.TestCase):
 def setUp(self):
  with app.db() as c:
   c.execute('DELETE FROM schedule_events');c.execute('DELETE FROM schedule_sources');c.execute('DELETE FROM schedule_seen')
   c.execute("INSERT OR REPLACE INTO users VALUES('calendar-admin',?,'admin')",(generate_password_hash('schedule-test-123'),))
  self.admin=app.app.test_client();self.guest=app.app.test_client()
  self.headers={'X-CSRF':self.admin.post('/api/login',json={'name':'calendar-admin','password':'schedule-test-123'}).json['csrf']}
 def save(self,**changes):
  data=dict(title='단체교섭',row='1',start='2026-10-30',end='2026-11-02',time='14:00',end_time='',place='회의실',kind='교섭',status='예정',state='published');data.update(changes)
  return self.admin.post('/api/schedule/event',json=data,headers=self.headers)
 def test_approval_permissions_and_overlap(self):
  app.ingest_schedule('image:test','홍보물','image','교섭회의\n일시: 2026년 10월 30일 14시\n장소: 당진 회의실')
  self.assertEqual(self.guest.get('/api/schedule?month=2026-10').json['events'],[])
  admin=self.admin.get('/api/schedule?month=2026-10').json
  candidate=admin['pending'][0]
  self.assertEqual(self.guest.get('/api/schedule/source/image:test').status_code,401)
  self.assertEqual(self.guest.post('/api/schedule/event',json={}).status_code,401)
  self.assertEqual(self.admin.post('/api/schedule/event',json={}).status_code,403)
  self.assertEqual(self.save(id=candidate['id'],version=1).status_code,200)
  visible=self.guest.get('/api/schedule?month=2026-11').json
  self.assertEqual(len(visible['events']),1);self.assertNotIn('pending',visible)
  self.assertNotIn('quote',visible['events'][0]);self.assertNotIn('source',visible['events'][0])
  self.assertEqual(self.save(id=candidate['id'],version=1).status_code,409)
 def test_idempotent_exclusion_and_changed_text(self):
  text='간담회 2026.10.26 10시'
  self.assertEqual(app.ingest_schedule('hwp:hash','회의.hwp','hwp',text),1)
  e=self.admin.get('/api/schedule?month=2026-10').json['pending'][0]
  self.assertEqual(self.save(id=e['id'],version=e['version'],state='rejected').status_code,200)
  self.assertEqual(app.ingest_schedule('hwp:hash','renamed.hwp','hwp',text),0)
  self.assertEqual(app.ingest_schedule('hwp:hash','renamed.hwp','hwp',text+'\n안내'),0)
  self.assertEqual(self.admin.get('/api/schedule?month=2026-10').json['pending'],[])
 def test_validation_and_rows_protection(self):
  for change in [dict(start='2026-02-30'),dict(end='2025-01-01'),dict(row=''),dict(time='28:00'),dict(title='')]:self.assertEqual(self.save(**change).status_code,400)
  self.assertEqual(self.save().status_code,200)
  rows=self.admin.get('/api/schedule').json['rows']
  self.assertEqual(self.admin.post('/api/schedule/rows',json={'rows':rows[1:],'previous':rows},headers=self.headers).status_code,400)
  self.assertEqual(self.admin.post('/api/schedule/rows',json={'rows':rows,'previous':[]},headers=self.headers).status_code,409)
 def test_duplicate_hint(self):
  for sid in ['one','two']:app.ingest_schedule(sid,'회의','image','집행부 회의 2026.10.26 10시')
  self.assertEqual(len(self.admin.get('/api/schedule').json['pending']),1)
 def test_date_range_and_ambiguity(self):
  events=extract_events('문체 수련회\n일시: 2026년 10월 29일(목) 14시 ~ 10월 30일(금) 12시\n장소: 봉수산 자연휴양림')
  self.assertEqual(len(events),1);e=events[0]
  self.assertEqual((e['start'],e['end'],e['time'],e['end_time']),('2026-10-29','2026-10-30','',''))
  self.assertEqual(e['place'],'')
  e=extract_events('교육활동가대회 2026년 10월21일(수) 13시 ~ 10월21일(목)')[0]
  self.assertIn('종료 날짜와 요일 불일치',e['warnings'])
  self.assertEqual(extract_events('회의 10/26 오전 9시30분',reference='2026-10-19'),[])
  self.assertEqual(extract_events('회의 2026.02.30'),[])
 def test_numbered_headings_and_quarters_are_not_dates(self):
  self.assertEqual(extract_events('☞ 2-1. 교육위원회 회의 결과\n보고: 3/4분기 노사협의회'),[])
 def test_neighboring_event_does_not_supply_title_or_location(self):
  text='☞ 1. 첫 회의\n일시/장소 : 2026년 10월 22일 14시 / 서울 회의실\n☞ 2. 열사영상 시사회 개최\n일시/장소 : 2026년 10월 23일 15시 / 아산 회의실\n차기회의 : 2026년 10월 26일 09:30\n장소 : 충남지부 회의실'
  events=extract_events(text)
  self.assertEqual([e['title'] for e in events],['열사영상 시사회'])
  self.assertEqual(events[0]['place'],'')
 def test_heading_and_dated_detail_merge_richer_fields(self):
  events=extract_events('☞ 2-3. 11월 7일 금속노동자대회\n⇨ 일시/장소 : 2026년 11월 7일(토) 14시 서울 / 확대간부 및 참가희망 조합원',reference='2026-10-19')
  self.assertEqual(len(events),1)
  self.assertEqual(events[0]['time'],'')
  self.assertEqual(events[0]['title'],'금속노동자대회')
 def test_upgrade_replaces_only_untouched_proposals(self):
  text='차기 교섭 일정 : 10/29(목) 예정'
  app.ingest_schedule('image:upgrade','자료','image',text,reference='2026-10-21')
  with app.db() as c:
   c.execute("UPDATE schedule_seen SET signature='legacy' WHERE id='image:upgrade'")
   c.execute("UPDATE schedule_events SET data=?,fingerprint='legacy' WHERE source='image:upgrade'",(json.dumps(dict(start='2026-10-21',end='2026-10-21',title='발행일 2026년10월21일',row='',warnings=[],quote='발행일')),))
  self.assertEqual(app.ingest_schedule('image:upgrade','자료','image',text,reference='2026-10-21'),1)
  e=self.admin.get('/api/schedule').json['pending'][0]
  self.assertEqual(e['title'],'차기 교섭')
  self.assertEqual(self.save(id=e['id'],version=e['version'],start=e['start'],end=e['end'],title='관리자가 고친 제목',state='pending').status_code,200)
  with app.db() as c:c.execute("UPDATE schedule_seen SET signature='legacy' WHERE id='image:upgrade'")
  app.ingest_schedule('image:upgrade','자료','image',text,reference='2026-10-21')
  es=self.admin.get('/api/schedule').json['pending'];self.assertEqual(len(es),1);self.assertEqual(es[0]['title'],'관리자가 고친 제목')
 def test_rebuild_empty_proposal_set_retires_noise(self):
  app.ingest_schedule('noise','자료','image','회의 2026.10.26')
  app.ingest_schedule('noise','자료','image','홈페이지 www.example.test 발행일 2026.10.26')
  self.assertEqual(self.admin.get('/api/schedule').json['pending'],[])
 def test_rebuild_invalidates_open_editor_version(self):
  app.ingest_schedule('changed','자료','image','차기 교섭 2026.10.29')
  e=self.admin.get('/api/schedule').json['pending'][0]
  app.ingest_schedule('changed','자료','image','차기 교섭 2026.10.29\n새 안내')
  self.assertEqual(self.save(id=e['id'],version=e['version']).status_code,409)
 def test_drm_rejection(self):
  with self.assertRaises(ValueError):hwp_text(b'SCDSA004'+b'\0'*100)

if __name__=='__main__':unittest.main()
