import io,json,os,tempfile,unittest,datetime
from unittest.mock import patch
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
  self.assertEqual(self.guest.post('/api/schedule/event',json={}).status_code,403)
  self.assertEqual(self.admin.post('/api/schedule/event',json={}).status_code,403)
  self.assertEqual(self.save(id=candidate['id'],version=1).status_code,200)
  visible=self.guest.get('/api/schedule?month=2026-11').json
  self.assertEqual(len(visible['events']),1);self.assertNotIn('pending',visible)
  self.assertNotIn('quote',visible['events'][0]);self.assertNotIn('source',visible['events'][0])
  self.assertEqual(self.save(id=candidate['id'],version=1).status_code,409)
 def test_team_member_can_create_but_not_edit(self):
  with app.db() as c:c.execute("INSERT OR REPLACE INTO users VALUES('calendar-member',?,'viewer')",(generate_password_hash('schedule-test-123'),))
  member=app.app.test_client();headers={'X-CSRF':member.post('/api/login',json={'name':'calendar-member','password':'schedule-test-123'}).json['csrf']}
  body=dict(title='현장 교섭',row='1',start='2026-10-30',end='',kind='일정',status='예정',state='published')
  self.assertEqual(self.guest.post('/api/schedule/event',json=body).status_code,403)
  response=member.post('/api/schedule/event',json=body,headers=headers);self.assertEqual(response.status_code,200)
  item=self.guest.get('/api/schedule?month=2026-10').json['events'][0]
  self.assertEqual(member.post('/api/schedule/event',json={**body,'id':item['id'],'version':item['version']},headers=headers).status_code,403)
 def test_team_member_can_select_each_schedule_kind(self):
  with app.db() as c:c.execute("INSERT OR REPLACE INTO users VALUES('calendar-member',?,'viewer')",(generate_password_hash('schedule-test-123'),))
  member=app.app.test_client();headers={'X-CSRF':member.post('/api/login',json={'name':'calendar-member','password':'schedule-test-123'}).json['csrf']}
  body=dict(title='일정',row='1',start='2026-10-30',end='',status='예정',state='published')
  kinds=['일정','교육','회의','교섭','행사','집회','기타']
  for kind in kinds:self.assertEqual(member.post('/api/schedule/event',json={**body,'kind':kind},headers=headers).status_code,200,kind)
  self.assertEqual(member.post('/api/schedule/event',json={**body,'kind':'임의'},headers=headers).status_code,403)
  self.assertCountEqual([item['kind'] for item in self.guest.get('/api/schedule?month=2026-10').json['events']],kinds)
 def test_guest_can_create_with_csrf_but_not_edit(self):
  response=self.guest.get('/api/me');token=response.json['csrf'];self.assertTrue(token)
  body=dict(title='비로그인 일정',row='1',start='2026-10-30',end='',kind='일정',category='meeting',status='예정',state='published',dday=False)
  self.assertEqual(self.guest.post('/api/schedule/event',json=body,headers={'X-CSRF':'wrong'}).status_code,403)
  created=self.guest.post('/api/schedule/event',json=body,headers={'X-CSRF':token});self.assertEqual(created.status_code,200)
  visible=self.guest.get('/api/schedule?month=2026-10').json['events'];item=next(e for e in visible if e['id']==created.json['id']);self.assertEqual(item['category'],'meeting')
  self.assertEqual(self.guest.post('/api/schedule/event',json={**body,'id':item['id'],'version':item['version']},headers={'X-CSRF':token}).status_code,403)
  self.assertEqual(self.guest.post('/api/schedule/event',json={**body,'state':'pending'},headers={'X-CSRF':token}).status_code,403)
  self.assertEqual(self.guest.post('/api/schedule/rows',json={},headers={'X-CSRF':token}).status_code,401)
 def test_category_override_roundtrip_and_reset(self):
  created=self.save(title='안전 교육',category='meeting');self.assertEqual(created.status_code,200)
  item=self.guest.get('/api/schedule?month=2026-10').json['events'][0];self.assertEqual(item['category'],'meeting')
  self.assertEqual(self.save(id=item['id'],version=item['version'],title=item['title'],category='wrong').status_code,400)
  self.assertEqual(self.save(id=item['id'],version=item['version'],title=item['title'],category='').status_code,200)
  item=self.guest.get('/api/schedule?month=2026-10').json['events'][0];self.assertNotIn('category',item)
 def test_created_and_updated_timestamps_visible_for_readers(self):
  self.assertEqual(self.save().status_code,200)
  item=self.guest.get('/api/schedule?month=2026-10').json['events'][0]
  self.assertTrue(item['createdAt']);self.assertTrue(item['updatedAt'])
  self.assertEqual(self.save(id=item['id'],version=item['version'],title='수정 일정').status_code,200)
  updated=self.guest.get('/api/schedule?month=2026-10').json['events'][0]
  self.assertEqual(updated['createdAt'],item['createdAt']);self.assertTrue(updated['updatedAt'])
 def test_calendar_day_order_is_shared_scoped_and_admin_only(self):
  with app.db() as c:c.execute('DELETE FROM schedule_day_order')
  ids=[self.save(title=title,start='2026-11-05',end='2026-11-05').json['id'] for title in ('가','나','다')]
  request={'date':'2026-11-05','group':'pohang','ids':[ids[2],ids[0],ids[1]],'previous':[]}
  self.assertEqual(self.guest.post('/api/schedule/day-order',json=request).status_code,401)
  self.assertEqual(self.admin.post('/api/schedule/day-order',json={**request,'group':'dangjin'},headers=self.headers).status_code,409)
  self.assertEqual(self.admin.post('/api/schedule/day-order',json={**request,'date':'2026-11-06'},headers=self.headers).status_code,409)
  self.assertEqual(self.admin.post('/api/schedule/day-order',json=request,headers=self.headers).status_code,200)
  self.assertEqual(self.guest.get('/api/schedule?month=2026-11').json['day_orders']['2026-11-05|pohang'],request['ids'])
  self.assertEqual(self.admin.post('/api/schedule/day-order',json=request,headers=self.headers).status_code,409)
  self.assertEqual(self.admin.post('/api/schedule/day-order',json={**request,'previous':request['ids'],'ids':ids},headers=self.headers).status_code,200)
  self.assertEqual(self.guest.get('/api/schedule?month=2026-10').json['day_orders'],{})
 def test_combined_other_branch_day_order_preserves_original_rows(self):
  with app.db() as c:c.execute('DELETE FROM schedule_day_order')
  ids=[self.save(title=name,row=row,start='2026-11-05',end='2026-11-05').json['id'] for row,name in [('2','당진 일정'),('3','인천 일정'),('4','당냉 일정'),('5','순천 일정')]]
  request={'date':'2026-11-05','group':'otherbranch','ids':ids[::-1],'previous':[]}
  self.assertEqual(self.admin.post('/api/schedule/day-order',json=request,headers=self.headers).status_code,200)
  result=self.guest.get('/api/schedule?month=2026-11').json
  self.assertEqual(result['day_orders']['2026-11-05|otherbranch'],ids[::-1])
  self.assertEqual({e['row'] for e in result['events']},{'2','3','4','5'})
 def test_dday_permissions_filter_and_preservation(self):
  with app.db() as c:c.execute("INSERT OR REPLACE INTO users VALUES('calendar-member',?,'viewer')",(generate_password_hash('schedule-test-123'),))
  member=app.app.test_client();headers={'X-CSRF':member.post('/api/login',json={'name':'calendar-member','password':'schedule-test-123'}).json['csrf']}
  base=dict(title='기간 일정',row='1',start='2026-11-02',end='2026-11-04',kind='일정',status='예정',state='published',dday=True)
  self.assertEqual(self.guest.post('/api/schedule/event',json=base).status_code,403)
  created=member.post('/api/schedule/event',json=base,headers=headers);self.assertEqual(created.status_code,200)
  self.assertEqual(member.post('/api/schedule/event',json={**base,'dday':'yes'},headers=headers).status_code,400)
  self.assertEqual(self.save(title='게시 전',state='pending',dday=True).status_code,200)
  self.assertEqual(self.save(title='취소 일정',status='취소',dday=True).status_code,200)
  self.assertEqual(self.save(title='일반 일정').status_code,200)
  with patch('schedule.korean_today',return_value=datetime.date(2026,10,29)):
   public=self.guest.get('/api/schedule/ddays').json['items'];admin=self.admin.get('/api/schedule/ddays').json['items']
   self.assertEqual([x['title'] for x in public],['기간 일정']);self.assertEqual([x['id'] for x in public],[x['id'] for x in admin]);self.assertNotIn('source',public[0]);self.assertNotIn('quote',public[0])
  with patch('schedule.korean_today',return_value=datetime.date(2026,11,2)):self.assertEqual(len(self.guest.get('/api/schedule/ddays').json['items']),1)
  with patch('schedule.korean_today',return_value=datetime.date(2026,11,3)):self.assertEqual(self.guest.get('/api/schedule/ddays').json['items'],[])
  item=next(e for e in self.admin.get('/api/schedule?month=2026-11').json['events'] if e['id']==created.json['id'])
  self.assertEqual(member.post('/api/schedule/event',json={**base,'id':item['id'],'version':item['version']},headers=headers).status_code,403)
  self.assertEqual(self.save(id=item['id'],version=item['version'],start=base['start'],end=base['end'],dday=False).status_code,200)
  with patch('schedule.korean_today',return_value=datetime.date(2026,10,29)):self.assertEqual(self.guest.get('/api/schedule/ddays').json['items'],[])
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
