import unittest
import test_app,app
class MemoTests(unittest.TestCase):
 def setUp(self):
  test_app.Tests.setUp(self)
  with app.db() as c:c.execute('DELETE FROM trend_memo_history');c.execute('DELETE FROM trend_memos')
 def payload(self,**changes):
  d=dict(title='포스코 결의대회 계획',organizations=['포스코','금속노조'],category='집회·투쟁',received='2026-10-28',source='텔레그램 공유',original='  원문 그대로\n주장 및 참가 목표\n',summary='계획 확인',verification='미확인',links=['https://example.com/source'],related=[],important=True);d.update(changes);return d
 def create(self,**changes):
  r=self.c.post('/api/memos/save',headers=self.h,json=self.payload(**changes));self.assertEqual(r.status_code,200,r.json);return r.json['id']
 def test_permissions_original_and_revision(self):
  self.assertEqual(self.v.post('/api/memos/save',headers=self.vh,json=self.payload()).status_code,403)
  self.assertEqual(self.c.post('/api/memos/save',json=self.payload()).status_code,403)
  mid=self.create();old=self.c.get('/api/memos/'+mid).json
  self.assertEqual(old['original'],self.payload()['original'])
  self.assertEqual(self.c.post('/api/memos/save',headers=self.h,json=self.payload(id=mid,version=old['version'],original='수정한 원문')).status_code,200)
  changed=self.c.get('/api/memos/'+mid).json;self.assertEqual(len(changed['history']),1)
  self.assertEqual(self.c.post('/api/memos/save',headers=self.h,json=self.payload(id=mid,version=old['version'])).status_code,409)
  self.assertEqual(self.v.get('/api/memos/'+mid).status_code,403)
 def test_search_followup_and_archive(self):
  mid=self.create();follow=self.create(title='후속 정보',related=[mid],organizations=['현대제철'])
  self.assertEqual(self.c.get('/api/memos?q=참가').json['total'],2)
  self.assertEqual(self.c.get('/api/memos?organization=포스코').json['total'],1)
  self.assertEqual(self.c.get('/api/memos?from=2026-10-29').json['total'],0)
  self.assertEqual(self.c.get('/api/memos/'+mid).json['followups'][0]['id'],follow)
  old=self.c.get('/api/memos/'+mid).json
  self.assertEqual(self.c.post('/api/memos/archive',headers=self.h,json={'id':mid,'version':old['version'],'archived':True}).status_code,200)
  self.assertEqual(self.v.get('/api/memos/'+mid).status_code,403)
  self.assertEqual(self.v.get('/api/memos?archived=1').status_code,403)
  self.assertEqual(self.c.get('/api/memos?archived=1').json['total'],2)
 def test_bad_links_and_memo_schedule_reference(self):
  self.assertEqual(self.c.post('/api/memos/save',headers=self.h,json=self.payload(links=['javascript:alert(1)'])).status_code,400)
  mid=self.create()
  r=self.c.post('/api/schedule/event',headers=self.h,json=dict(title='결의대회',row='1',start='2026-10-29',end='',state='published',memo_id=mid));self.assertEqual(r.status_code,200,r.json)
  event=next(e for e in self.c.get('/api/schedule?month=2026-10').json['events'] if e['id']==r.json['id']);self.assertEqual(event['memo_id'],mid)

 def test_simple_three_field_input_preserves_legacy_metadata(self):
  r=self.c.post('/api/memos/save',headers=self.h,json={'organizations':['현대제철'],'title':'간단 메모','original':'정리할 내용'})
  self.assertEqual(r.status_code,200,r.json)
  self.assertEqual(self.c.get('/api/memos/'+r.json['id']).json['original'],'정리할 내용')
  mid=self.create();old=self.c.get('/api/memos/'+mid).json
  minimal=dict(id=mid,version=old['version'],organizations=['포스코'],title='수정',original='내용 수정')
  self.assertEqual(self.c.post('/api/memos/save',headers=self.h,json=minimal).status_code,200)
  saved=self.c.get('/api/memos/'+mid).json
  for key in ['source','summary','category','received','links','important']:self.assertEqual(saved[key],old[key])
  minimal.pop('version')
  self.assertEqual(self.c.post('/api/memos/save',headers=self.h,json=minimal).status_code,409)

 def test_non_admin_blocked_and_new_memo_enqueued(self):
  guest=app.app.test_client();payload={'title':'일정 공지','original':'2026년 11월 10일 14시 교섭 회의','organizations':[]}
  self.assertEqual(guest.get('/api/memos').status_code,401)
  self.assertEqual(guest.post('/api/memos/save',json=payload).status_code,401)
  self.assertEqual(self.v.get('/api/memos').status_code,403)
  result=self.c.post('/api/memos/save',headers=self.h,json=payload);self.assertEqual(result.status_code,200);self.assertTrue(result.json['schedule_queued'])
  mid=result.json['id'];sid='memo:'+mid
  with app.db() as c:
   source=c.execute('SELECT * FROM schedule_sources WHERE id=?',(sid,)).fetchone();self.assertEqual(source['text'],payload['original']);self.assertEqual(source['kind'],'memo')
  groups=self.c.get('/api/schedule/review-sources').json['groups'];self.assertTrue(any(g['id']==sid and not g['done'] for g in groups))
  app.scan_schedules()
  groups=self.c.get('/api/schedule/review-sources').json['groups'];self.assertTrue(any(g['id']==sid and not g['done'] for g in groups))
  self.assertEqual(self.c.get('/api/schedule/source/'+sid).json['text'],payload['original'])
  with app.db() as c:
   pending=[__import__('json').loads(r['data']) for r in c.execute("SELECT data FROM schedule_events WHERE source=? AND state='pending'",(sid,))]
  self.assertTrue(pending);self.assertEqual(pending[0]['memo_id'],mid)
  detail=self.c.get('/api/memos/'+mid).json
  result=self.c.post('/api/memos/save',headers=self.h,json={'id':mid,'version':detail['version'],'title':'수정','original':'수정'});self.assertFalse(result.json['schedule_queued'])
  with app.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM schedule_sources WHERE id=?',(sid,)).fetchone()[0],1)
 def test_memo_without_date_still_queued(self):
  mid=self.create(title='날짜 없는 메모',original='회의 관련 참고사항')
  app.scan_schedules()
  self.assertTrue(any(g['id']=='memo:'+mid and not g['done'] for g in self.c.get('/api/schedule/review-sources').json['groups']))

if __name__=='__main__':unittest.main()
