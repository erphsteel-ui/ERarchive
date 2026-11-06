import datetime as dt, unittest
from unittest.mock import patch
from email.utils import format_datetime
import test_news,app,news
from news_filter import should_drop,demoted,strict_drop
from news_grouping import category,group_articles,title_similarity

class PipelineRules(unittest.TestCase):
 def item(self,i,title,category_name=None,date='2026-10-28T01:00:00+00:00',description=''):
  return {'id':str(i),'title':title,'description':description,'category':category_name or category(title,description),'published':date,'important':0,'excluded':0,'relevance':'keep','publisher':'example.com','url':'https://example.com/'+str(i)}
 def test_drop_and_demotion(self):
  for word in ['레드엔젤스','여자축구','양궁단','스틸러스','[특징주]','목표가↑','목표가↓','부고','인사']:
   with self.subTest(word=word):self.assertTrue(should_drop('현대제철 '+word))
  for word in ['견학','장학금','성료','봉사활동','기부','캠페인','모집']:
   self.assertTrue(demoted('현대제철 '+word));self.assertEqual(category('현대제철 '+word),'기타')
  self.assertTrue(demoted('현대모비스 연구 발표','현대제철도 참여했다'))
  self.assertEqual(category('포스코퓨처엠 투자 발표','현대제철도 참여했다'),'기타')
  self.assertEqual(category('현대제철 투자 발표','지역사회 봉사활동'),'경영(투자·실적)')
 def test_title_priority_and_body_weights(self):
  self.assertEqual(category('노조 노동자 사망 사고','투자 발표'),'안전')
  self.assertEqual(category('노조 교섭 결의대회','지역사회 고로 가동'),'노사관계')
  self.assertEqual(category('정부 관세 대응','제철소 투자'),'정책')
  self.assertEqual(category('전기로 투자','지역사회'),'경영(투자·실적)')
  self.assertEqual(category('새 소식','노조 파업 교섭, 투자 발표'),'노사관계')
 def test_strict_posco_and_other_filter(self):
  self.assertTrue(strict_drop('포스코 장학금 전달','', '기타'))
  self.assertFalse(strict_drop('포스코 노조 파업 돌입','', '노사관계'))
  self.assertFalse(strict_drop('포스코 입장 발표','임단협 교섭이 이어졌다', '노사관계'))
  self.assertFalse(strict_drop('포스코 장학금 전달','현대제철도 함께 참여', '기타'))
  self.assertTrue(strict_drop('지역 축제 개최','', '기타'))
  self.assertFalse(strict_drop('포항 철강산단 소식','', '기타'))
 def test_macro_topics_are_bounded_by_representative_and_ten_days(self):
  a=self.item('a','포스코 노조 파업 돌입',date='2026-10-28T01:00:00+00:00')
  b=self.item('b','포스코 교섭 사측 입장',date='2026-10-20T01:00:00+00:00')
  c=self.item('c','포스코 임단협 지역 반응',date='2026-10-17T01:00:00+00:00')
  groups=group_articles([a,b,c]);self.assertEqual(sorted(x['article_count'] for x in groups),[1,2]);self.assertEqual(groups[0]['issue_label'],'포스코 노사관계·교섭 동향')
  a=self.item('a','현대제철 사망 사고 조사')
  b=self.item('b','현대제철 중대재해 노동부 감독',date='2026-10-21T01:00:00+00:00')
  groups=group_articles([a,b]);self.assertEqual(len(groups),1);self.assertEqual(groups[0]['issue_label'],'현대제철 안전·중대재해 사고')
 def test_normalization_and_blackhole(self):
  pairs=[('최병욱 국힘 입당 지역발전협의회 개최','최병욱 국민의힘 입당 지역발전협의회 개최'),('하청노동자 사망…5년간 7명 숨져','5년간 7명 숨져 하청노동자 사망')]
  for a,b in pairs:self.assertEqual(len(group_articles([self.item('a',a),self.item('b',b)])),1)
  items=[self.item(str(i),'현대제철 포항 공장 투자 프로젝트 '+str(i)) for i in range(100)]
  self.assertGreater(len(group_articles(items)),80)
  a=self.item('a','루이지애나 수소 환원 설비 증설 착공 확정','경영(투자·실적)');a['important']=1
  b=self.item('b','루이지애나 수소 환원 설비 투자 전력 관세','경영(투자·실적)')
  c=self.item('c','루이지애나 전력 관세 문제 탄소 공급','경영(투자·실적)')
  self.assertGreaterEqual(title_similarity(a['title'],b['title']),.45)
  self.assertGreaterEqual(title_similarity(b['title'],c['title']),.45)
  self.assertLess(title_similarity(a['title'],c['title']),.45)
  self.assertEqual(len(group_articles([a,b,c])),2)
  far=self.item('far',pairs[0][1],date='2026-11-01T01:00:00+00:00')
  self.assertEqual(len(group_articles([self.item('a',pairs[0][0]),far])),2)
 def test_headline_quota_diversity_and_today(self):
  records=[self.item('a','현대제철 당진공장 신규 투자 계획','경영(투자·실적)'),self.item('b','현대제철 포항공장 노동조합 교섭 일정','노사관계'),self.item('c','포스코 광양공장 중대재해 사망사고','안전'),self.item('d','정부 산업용 전기요금 개편','정책'),self.item('e','현대제철 장학금 행사 성료','기타')]
  result=news.headline_groups(records,dt.datetime(2026,10,28,6,tzinfo=dt.timezone.utc))
  self.assertEqual(len(result),4);self.assertGreaterEqual(sum(news.headline_company(x) for x in result),2)
  self.assertNotIn('e',[x['id'] for x in result]);self.assertEqual(result[2]['id'],'c')
  one=self.item('f','현대제철 최병욱 국힘 지역발전협의회 발언','기타');two=self.item('g','현대제철 최병욱 국민의힘 지역발전협의회 소식','기타')
  result=news.headline_groups([one,two],dt.datetime(2026,10,28,6,tzinfo=dt.timezone.utc));self.assertEqual(len(result),1)

class PipelineCollection(unittest.TestCase):
 setUp=test_news.NewsTests.setUp
 config=test_news.NewsTests.config
 sample=test_news.NewsTests.sample
 def test_drop_does_not_persist_and_promotion_is_lowered(self):
  self.config();sample=self.sample();bad=dict(sample,title='현대제철 여자축구 우승',originallink='https://example.com/sports');promo=dict(sample,title='현대제철 장학금 전달',originallink='https://example.com/promo');normal=dict(sample,originallink='https://example.com/labor')
  with patch('news.fetch_news',return_value=[bad,promo,normal]):result=self.c.post('/api/news/fetch',headers=self.h,json={}).json
  self.assertEqual(result['filtered'],1)
  with app.db() as c:self.assertFalse(c.execute("SELECT 1 FROM news_articles WHERE url='https://example.com/sports'").fetchone())
  items=self.v.get('/api/news').json['items'];self.assertEqual(items[-1]['title'],'현대제철 장학금 전달');self.assertEqual(items[-1]['category'],'기타')
 def test_existing_news_reclassification_preserves_manual_decisions(self):
  with app.db() as c:
   c.execute("UPDATE settings SET value='old' WHERE key IN ('news_filter_version','news_category_version')")
   c.execute("INSERT INTO news_articles(id,url,title,description,publisher,published,category,important,excluded,version,relevance,filter_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",('old','https://example.com/old','현대제철 노동자 끼임 사망','노사 교섭','example.com','2026-10-28T01:00:00+00:00','기타',1,1,7,'review','old'))
   news.reclassify_news(c)
   row=c.execute("SELECT category,important,excluded,version FROM news_articles WHERE id='old'").fetchone()
   self.assertEqual(tuple(row),('안전',1,1,7))
