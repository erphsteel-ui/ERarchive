import unittest,datetime as dt,threading
from unittest.mock import patch
import steel_press as s,test_app,app

class ParserTests(unittest.TestCase):
 def test_two_actual_layout_patterns(self):
  steel='<section id="section-list"><ul><li><h4 class="titles"><a href="/news/articleView.html?idxno=10">철강 &amp; 뉴스</a></h4><span class="byline"><em>2026-10-28 05:00</em></span></li></ul></section>'
  ferro='<div class="list-block"><div class="list-titles"><a href="/news/articleView.html?idxno=11"><strong>철강 뉴스</strong></a></div><div class="list-dated">기자 | 2026-10-28 16:13</div></div>'
  self.assertEqual(s.parse_list(steel,'steeldaily')[0]['title'],'철강 & 뉴스')
  self.assertEqual(s.parse_list(steel,'steeldaily')[0]['published'],'2026-10-27T20:00:00+00:00')
  self.assertEqual(s.parse_list(ferro,'ferrotimes')[0]['source'],'ferrotimes')
  table=ferro.replace('class="list-block"','class="table-row"').replace('class="list-titles"','class="list-titles table-cell"').replace('<a href=', '<small>[뉴스]</small><a href=')
  self.assertEqual(s.parse_list(table,'ferrotimes')[0]['title'],'철강 뉴스')
  with self.assertRaises(ValueError):s.parse_list(steel.replace('/news/articleView.html?idxno=10','https://evil.example/news/articleView.html?idxno=10'),'steeldaily')
 def test_korean_day_dedup_and_stop_old_pages(self):
  now=dt.datetime(2026,10,28,8,tzinfo=dt.timezone.utc)
  rows=[dict(id='morning',published='2026-10-27T20:00:00+00:00'),dict(id='future',published='2026-10-28T12:00:00+00:00'),dict(id='old',published='2026-10-27T14:00:00+00:00')]
  with patch('steel_press.fetch_page',return_value=rows) as fetch:
   self.assertEqual([x['id'] for x in s.collect_source('steeldaily',now)],['morning']);self.assertEqual(fetch.call_count,1)
class PressAPITests(unittest.TestCase):
 def setUp(self):
  test_app.Tests.setUp(self)
  clock=patch('steel_press.utc_now',return_value=dt.datetime(2026,10,28,8,tzinfo=dt.timezone.utc));clock.start();self.addCleanup(clock.stop)
  with app.db() as c:c.execute('DELETE FROM steel_press_articles');c.execute('DELETE FROM steel_press_status')
 def test_permissions_partial_failure_and_cached_listing(self):
  self.assertEqual(self.v.post('/api/news/steel-press/fetch',headers=self.vh,json={}).status_code,403)
  def collect(source,now):
   if source=='ferrotimes':raise OSError('blocked')
   return [dict(id='test',title='공개 제목',url='https://www.steeldaily.co.kr/news/articleView.html?idxno=10',published='2026-10-27T20:00:00+00:00')]
  with patch('steel_press.collect_source',side_effect=collect):
   self.assertEqual(self.c.post('/api/news/steel-press/fetch',headers=self.h,json={}).status_code,200)
   for thread in threading.enumerate():
    if thread.name=='steel-press':thread.join(2)
  data=app.steel_press_listing();self.assertFalse(data['running']);self.assertEqual(len(data['sources'][0]['items']),1)
  self.assertTrue(data['sources'][1]['error']);self.assertIn('google.com/search',data['sources'][1]['google_url'])
