import unittest,json
import test_app,app

class ReviewGroupTests(unittest.TestCase):
 setUp=test_app.Tests.setUp
 img=test_app.Tests.img
 upload=test_app.Tests.upload
 doc=test_app.Tests.doc
 def test_actual_publication_pages_group_and_complete_atomically(self):
  did=self.upload(['red','blue'])
  with app.db() as c:pages=list(c.execute('SELECT hash FROM pages WHERE doc=? ORDER BY position',(did,)))
  for p in pages:app.ingest_schedule('image:'+p['hash'],'same title','image','공지')
  groups=self.c.get('/api/schedule/review-sources').json['groups']
  group=next(g for g in groups if g['id']=='doc:'+did)
  self.assertEqual(len(group['members']),2)
  members=[dict(source=m['id'],signature=m['signature']) for m in group['members']]
  bad=[dict(m) for m in members];bad[1]['signature']='wrong'
  self.assertEqual(self.c.post('/api/schedule/review-source',headers=self.h,json=dict(sources=bad,action='complete',versions={})).status_code,409)
  with app.db() as c:self.assertEqual(c.execute('SELECT count(*) FROM schedule_reviews WHERE source IN (?,?)',(members[0]['source'],members[1]['source'])).fetchone()[0],0)
  self.assertEqual(self.c.post('/api/schedule/review-source',headers=self.h,json=dict(sources=members,action='complete',versions={})).status_code,200)
  group=next(g for g in self.c.get('/api/schedule/review-sources').json['groups'] if g['id']=='doc:'+did)
  self.assertTrue(group['done'])
 def test_blank_end_defaults_to_start_and_explicit_end_preserved(self):
  base=dict(title='당일 일정',row='1',start='2026-10-28',end='',state='published')
  r=self.c.post('/api/schedule/event',headers=self.h,json=base);self.assertEqual(r.status_code,200)
  event=next(e for e in self.c.get('/api/schedule?month=2026-10').json['events'] if e['id']==r.json['id'])
  self.assertEqual(event['start'],event['end'])
  base.update(title='기간 일정',end='2026-10-30')
  r=self.c.post('/api/schedule/event',headers=self.h,json=base);self.assertEqual(r.status_code,200)
  event=next(e for e in self.c.get('/api/schedule?month=2026-10').json['events'] if e['id']==r.json['id'])
  self.assertEqual(event['end'],'2026-10-30')
