import unittest
import datetime as dt
from unittest.mock import patch
import urllib.error
import test_app,app,news

class NewsTests(unittest.TestCase):
 def setUp(self):
  clock=patch('news.utc_now',return_value=dt.datetime(2026,10,28,6,tzinfo=dt.timezone.utc));clock.start();self.addCleanup(clock.stop)
  previews=patch.object(app,'start_news_previews',return_value=False);previews.start();self.addCleanup(previews.stop)
  press=patch.object(app,'start_steel_press',return_value=False);press.start();self.addCleanup(press.stop)
  test_app.Tests.setUp(self)
  with app.db() as c:c.execute('DELETE FROM news_articles')
  (app.DATA/'news_config.json').unlink(missing_ok=True)
 def config(self):
  return self.c.post('/api/news/config',headers=self.h,json={'mode':'classic','client_id':'private-id','secret':'private-secret','query':'현대제철'})
 def sample(self):return {'title':'<b>현대제철</b> 노사 교섭','description':'안내 &amp; 내용','originallink':'https://news.example.com/a?id=10&utm_source=test','pubDate':'Wed, 28 Oct 2026 10:00:00 +0900'}
 def test_permission_and_config_secrets(self):
  guest=app.app.test_client()
  self.assertEqual(guest.get('/api/news').status_code,200)
  self.assertEqual(guest.get('/api/news/config').status_code,401)
  self.assertEqual(self.v.get('/api/news/config').status_code,403)
  self.assertEqual(self.c.post('/api/news/config',json={}).status_code,403)
  self.assertEqual(self.config().status_code,200)
  data=self.c.get('/api/news/config').json
  self.assertTrue(data['configured']);self.assertNotIn('secret',data);self.assertNotIn('client_id',data)
 def test_fetch_dedup_and_preserve_decisions(self):
  self.config()
  with patch('news.fetch_news',return_value=[self.sample()]):
   self.assertEqual(self.c.post('/api/news/fetch',headers=self.h,json={}).json['added'],1)
   row=self.c.get('/api/news').json['items'][0]
   self.assertEqual(row['title'],'현대제철 노사 교섭');self.assertEqual(row['category'],'노사관계')
   self.assertEqual(row['description'],'안내 & 내용')
   self.assertEqual(self.c.post('/api/news/article',headers=self.h,json={'id':row['id'],'version':row['version'],'field':'excluded','value':True}).status_code,200)
   self.assertEqual(self.c.post('/api/news/fetch',headers=self.h,json={}).json['added'],0)
   self.assertEqual(self.v.get('/api/news?excluded=1').json['total'],0)
   self.assertEqual(self.c.get('/api/news?excluded=1').json['total'],1)
   self.assertEqual(self.c.post('/api/news/article',headers=self.h,json={'id':row['id'],'version':row['version'],'field':'important','value':True}).status_code,409)
 def test_error_does_not_leak_keys_or_html(self):
  self.assertEqual(self.c.post('/api/news/fetch',headers=self.h,json={}).status_code,400)
  self.config()
  with patch('news.fetch_news',side_effect=urllib.error.HTTPError('https://example.com',403,'private-secret',{},None)):
   r=self.c.post('/api/news/fetch',headers=self.h,json={});self.assertEqual(r.status_code,502);self.assertNotIn('private-secret',r.get_data(as_text=True))
  self.assertEqual(news.canonical('javascript:alert(1)'),'')

 def test_category_counts_respect_other_filters(self):
  with app.db() as c:
   for i,(category,title,important) in enumerate([('안전','현대제철 안전',1),('노사관계','현대제철 교섭',0),('기타','다른 뉴스',0)]):
    c.execute('INSERT INTO news_articles(id,url,title,description,publisher,published,category,important,excluded,relevance,filter_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(str(i),'https://example.com/'+str(i),title,'내용','example.com','2026-10-28T01:00:00+00:00',category,important,0,'keep',''))
  data=self.v.get('/api/news?category=안전&q=현대제철').json
  self.assertEqual(data['total'],1);self.assertEqual(data['category_counts'][''],2)
  self.assertEqual(data['category_counts']['안전'],1);self.assertEqual(data['category_counts']['노사관계'],1)
  self.assertEqual(data['category_counts']['기타'],0)
  self.assertEqual(self.v.get('/api/news?important=1').json['category_counts'][''],1)

class MultiSearchTests(unittest.TestCase):
 def test_separate_terms_and_url_dedup(self):
  shared={'originallink':'https://example.com/a?utm_source=x'}
  with patch('news.fetch_news_term',side_effect=[[shared,{'link':'https://example.com/b'}],[{'originallink':'https://example.com/a'}, {'link':'https://example.com/c'}]]) as fetch:
   result=news.fetch_news({'query':' 현대제철, 포스코\n현대제철 '})
  self.assertEqual([call.args[1] for call in fetch.call_args_list],['현대제철','포스코'])
  self.assertEqual(len(result),3)
 def test_all_keywords_results_exceed_100(self):
  with patch('news.fetch_news_term',side_effect=[[{'link':f'https://example.com/{i}'} for i in range(100)],[{'link':f'https://example.com/{i}'} for i in range(100,200)]]):
   self.assertEqual(len(news.fetch_news({'query':'현대제철,포스코'})),200)
 def test_query_limit(self):
  for value in ['',','.join(str(i) for i in range(21))]:
   with self.assertRaises(ValueError):news.search_terms(value)

class HeadlineTests(unittest.TestCase):
 setUp=NewsTests.setUp
 def test_headlines_rank_all_issues_before_pagination_and_filter_exclusions(self):
  import hashlib
  with app.db() as c:
   for i in range(105):
    url='https://example.com/'+str(i);pid=hashlib.sha256(url.encode()).hexdigest()
    c.execute('INSERT INTO news_articles(id,url,title,description,publisher,published,category,important,excluded,relevance,filter_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(pid,url,'현대제철 기업자료 '+str(i),'본문','example.com',f'2026-10-28T01:{i//60:02d}:{i%60:02d}+00:00','기타',int(i==0),0,'keep','test'))
  data=self.v.get('/api/news?offset=100').json
  self.assertEqual(len(data['headlines']),4);self.assertEqual(data['headlines'][0]['title'],'현대제철 기업자료 0')
  self.assertEqual(data['headlines'][1]['title'],'현대제철 기업자료 104')
  self.assertNotIn('related_articles',data['headlines'][0])
  with app.db() as c:c.execute("UPDATE news_articles SET excluded=1 WHERE important=1")
  self.assertNotIn('현대제철 기업자료 0',[r['title'] for r in self.c.get('/api/news?excluded=1').json['headlines']])
  self.assertEqual(self.v.get('/api/news?category=안전').json['headlines'],self.v.get('/api/news').json['headlines'])
  self.assertEqual(self.c.get('/api/news?view=review').json['headlines'],self.v.get('/api/news').json['headlines'])
 def test_headlines_global_72_hours_keyword_priority_and_photo(self):
  import hashlib
  examples=[('현대제철 포항 노사 환경정화 활동','2026-10-27T01:00:00+00:00','노사관계',0),('현대제철 당진 투자 계획 발표','2026-10-28T01:00:00+00:00','경영(투자·실적)',0),('포스코 노조 교섭 난항','2026-10-28T02:00:00+00:00','노사관계',1),('현대제철 인천 화재 사고','2026-10-24T01:00:00+00:00','안전',1)]
  with app.db() as c:
   for i,(title,date,category,important) in enumerate(examples):
    url='https://example.com/'+str(i);pid=hashlib.sha256(url.encode()).hexdigest()
    c.execute('INSERT INTO news_articles(id,url,title,description,publisher,published,category,important,excluded,relevance,filter_reason,preview) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(pid,url,title,'','example.com',date,category,important,0,'keep','test','ready' if i==0 else ''))
    if i==0:(app.DATA/'news_previews'/(pid+'.jpg')).write_bytes(b'image')
  headlines=self.v.get('/api/news').json['headlines']
  self.assertEqual([r['title'] for r in headlines],[x[0] for x in examples[:3]])
  self.assertTrue(headlines[0]['has_image'])
  self.assertEqual(self.v.get('/api/news?q=nomatch&category=安全&offset=100').status_code,400)
  self.assertEqual(self.v.get('/api/news?q=nomatch&category=안전&offset=100').json['headlines'],headlines)
