import unittest,json
import app
from test_schedule import ScheduleTests as Base

class SourceReviewTests(unittest.TestCase):
 setUp=Base.setUp
 def test_empty_source_is_reviewable_and_completion_sticks(self):
  app.ingest_schedule('review:empty','일정없는자료','image','공지사항만 있습니다')
  data=self.admin.get('/api/schedule/review-sources').json['sources'];s=next(x for x in data if x['id']=='review:empty')
  self.assertFalse(s['done']);self.assertEqual(s['pending'],0)
  payload=dict(source=s['id'],signature=s['signature'],versions={},action='complete')
  self.assertEqual(self.guest.post('/api/schedule/review-source',json=payload).status_code,401)
  self.assertEqual(self.admin.post('/api/schedule/review-source',json=payload,headers=self.headers).status_code,200)
  app.ingest_schedule(s['id'],'일정없는자료','image','공지사항만 있습니다')
  self.assertTrue(next(x for x in self.admin.get('/api/schedule/review-sources').json['sources'] if x['id']==s['id'])['done'])
 def test_none_rejects_and_conflicts_are_atomic(self):
  app.ingest_schedule('review:events','자료','image','집행부 회의 2026.11.02')
  s=next(x for x in self.admin.get('/api/schedule/review-sources').json['sources'] if x['id']=='review:events')
  e=self.admin.get('/api/schedule').json['pending'][0]
  b=dict(source=s['id'],signature=s['signature'],versions={},action='none')
  self.assertEqual(self.admin.post('/api/schedule/review-source',json=b,headers=self.headers).status_code,409)
  b['versions']={e['id']:e['version']}
  self.assertEqual(self.admin.post('/api/schedule/review-source',json=b,headers=self.headers).status_code,200)
  self.assertEqual(self.admin.get('/api/schedule').json['pending'],[])
 def test_five_categories_preserve_explicit_choices(self):
  self.assertEqual(list(app.CATEGORIES),['회사','집행부','제조직','계열사','그룹사','기타'])
  self.assertEqual(app.categories_for({'publishers':['현대ITC노동조합']}),['계열사'])
  self.assertEqual(app.categories_for({'publishers':['현대자동차지부']}),['그룹사'])
  self.assertEqual(app.categories_for({'publishers':['현대ITC노동조합'],'category':'기타'}),['기타'])
