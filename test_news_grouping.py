import unittest,datetime as dt,io,socket,threading
from unittest.mock import patch
from PIL import Image
import test_news,app,news
from news_grouping import category,group_articles
from news_preview import fetch_public,make_preview

class CategoryGroupingTests(unittest.TestCase):
 def item(self,id,title,date='2026-10-28T01:00:00+00:00'):
  return dict(id=id,title=title,published=date,category=category(title),important=0,has_image=False)
 def test_title_precedes_generic_body(self):
  self.assertEqual(category('현대제철 30일 3분기 실적 발표…11월 3일 국내 NDR','현대제철 공장의 생산 계획을 설명했다'),'경영(투자·실적)')
  self.assertEqual(category('현대제철 포항공장 노사, 환경정화 활동으로 지역사회 상생 실천','공장 생산 및 투자'),'노사관계')
  self.assertEqual(category('현대제철 공장 화재 발생'),'안전')
  self.assertEqual(category('철강 관세와 전기요금 대책'),'정책')
 def test_same_event_conservative_grouping(self):
  a=self.item('a','현대제철 포항공장 노사, 환경정화 활동으로 지역사회 상생 실천')
  b=self.item('b',"쓰레기 줍고 둘레길 걸으며…현대제철 포항공장 노사 '상생 행보'")
  self.assertEqual(len(group_articles([a,b])),1)
  different=self.item('c','현대제철 당진공장 노사, 환경정화 활동으로 지역사회 상생 실천')
  self.assertEqual(len(group_articles([a,different])),2)
  later=dict(a,id='later',published='2026-11-01T01:00:00+00:00')
  self.assertEqual(len(group_articles([a,later])),2)
  x=self.item('x','현대제철 파업 2일 예고');y=self.item('y','현대제철 파업 3일 돌입')
  self.assertEqual(len(group_articles([x,y])),2)
class PreviewTests(unittest.TestCase):
 def test_private_address_is_never_connected(self):
  answer=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',80))]
  with patch('news_preview.socket.getaddrinfo',return_value=answer),patch('news_preview.socket.create_connection') as connect:
   with self.assertRaises(ValueError):fetch_public('http://example.com/news',100)
   connect.assert_not_called()
 def test_public_meta_image_resized(self):
  b=io.BytesIO();Image.new('RGB',(1200,800),'red').save(b,'PNG')
  responses=[(b'<meta property="og:image" content="/photo.png">','text/html','https://example.com/news'),(b.getvalue(),'image/png','https://example.com/photo.png')]
  with patch('news_preview.fetch_public',side_effect=responses):result=make_preview('https://example.com/news')
  with Image.open(io.BytesIO(result)) as im:self.assertEqual(im.format,'JPEG');self.assertLessEqual(im.width,480)
class PreviewAPITests(unittest.TestCase):
 setUp=test_news.NewsTests.setUp
 config=test_news.NewsTests.config
 sample=test_news.NewsTests.sample
 def test_background_preview_and_private_visibility(self):
  self.config()
  with patch('news.fetch_news',return_value=[self.sample()]):self.c.post('/api/news/fetch',headers=self.h,json={})
  b=io.BytesIO();Image.new('RGB',(40,30),'red').save(b,'JPEG')
  with patch('news.make_preview',return_value=b.getvalue()):
   self.assertEqual(self.c.post('/api/news/previews',headers=self.h,json={}).status_code,200)
   for thread in threading.enumerate():
    if thread.name=='news-preview':thread.join(2)
  n=self.c.get('/api/news').json['items'][0];self.assertTrue(n['has_image'])
  with self.v.get('/api/news-image/'+n['id']) as r:self.assertEqual(r.status_code,200)
  self.c.post('/api/news/article',headers=self.h,json=dict(id=n['id'],version=n['version'],field='excluded',value=True))
  self.assertEqual(self.v.get('/api/news-image/'+n['id']).status_code,404)

 def test_group_listing_and_atomic_exclusion(self):
  self.config();a=self.sample();b=dict(a,originallink='https://second.example.com/same')
  with patch('news.fetch_news',return_value=[a,b]):self.c.post('/api/news/fetch',headers=self.h,json={})
  data=self.c.get('/api/news').json;self.assertEqual(data['article_total'],2);self.assertEqual(data['total'],1)
  n=data['items'][0];items=[{'id':x['id'],'version':x['version']} for x in [n]+n['related_articles']]
  bad=[dict(x) for x in items];bad[1]['version']+=1
  self.assertEqual(self.c.post('/api/news/group-action',headers=self.h,json=dict(items=bad,excluded=True)).status_code,409)
  self.assertEqual(self.v.get('/api/news').json['article_total'],2)
  self.assertEqual(self.c.post('/api/news/group-action',headers=self.h,json=dict(items=items,excluded=True)).status_code,200)
  self.assertEqual(self.v.get('/api/news').json['total'],0)

class EventGroupingTests(CategoryGroupingTests):
 def article(self,id,title,body='',date='2026-10-27T01:00:00+00:00'):
  return dict(self.item(id,title,date),description=body)
 def test_strike_notice_numbers_and_wording(self):
  a=self.article('a','포스코 노사, 28차례 교섭에도 평행선…노조 무기한 파업 예고','다음 달 2일 오후 7시부터 파업에 돌입한다.')
  b=self.article('b','기본급 7.1% vs 2.5% 격차 못 좁혀… 포스코 노조 무기한 파업 예고','11월 2일부터 무기한 파업을 예고했다.')
  c=self.article('c','포스코 노조 11월 2일 무기한 파업 선언','임금 인상과 성과급이 쟁점이다.')
  self.assertEqual(len(group_articles([a,b,c])),1)
  different=self.article('d','포스코 노조 무기한 파업 예고','11월 3일부터 파업')
  self.assertEqual(len(group_articles([a,different])),1)
  update=self.article('u','포스코 노사 교섭 타결…파업 철회','11월 2일 파업을 철회했다.')
  self.assertEqual(len(group_articles([a,update])),1)
 def test_accident_same_date_not_age_number(self):
  a=self.article('a','현대제철 당진공장서 협력업체 근로자 기계에 끼어 숨져','지난 18일 오전 10시 43분 40대 노동자가 설비를 보수하다 숨졌다.', '2026-10-19T01:00:00+00:00')
  b=self.article('b','현대제철 당진공장서 40대 노동자 설비에 끼여 숨져','오늘(18일) 오전 10시 40분 사고가 발생했다.', '2026-10-18T12:00:00+00:00')
  self.assertEqual(a['category'],'안전');self.assertEqual(b['category'],'안전')
  self.assertEqual(len(group_articles([a,b])),1)
  different=dict(b,id='different',published='2026-10-19T01:00:00+00:00',description='오늘(19일) 오전 사고가 발생했다.')
  self.assertEqual(len(group_articles([a,different])),1)
 def test_views_are_other_and_do_not_merge(self):
  for title in ['[경상칼럼]포스코 노조, 철강 위기 앞에 무엇을 지킬 것인가','이상휘 국회의원, 포스코 노사에 대화 촉구','금속노조, 포스코 파업 관련 성명 발표','포스코 파업에 지역사회 대응 나서']:
   self.assertEqual(category(title),'노사관계')
  a=self.article('a','[칼럼]포스코 파업과 지역경제')
  b=self.article('b','[기고]포스코 파업과 지역경제')
  # Reactions and commentary on the same labor issue share the topic.
  self.assertEqual(len(group_articles([a,b])),1)

class IssueTimelineTests(CategoryGroupingTests):
 def test_labor_followups_across_14_days_and_actor_in_excerpt(self):
  a=self.item('a','포스코 노사 임금교섭 난항','2026-10-15T01:00:00+00:00')
  b=dict(self.item('b','28차례 교섭에도 평행선…무기한 파업 예고'),description='한국노총 금속노련 포스코노동조합은 다음 달 파업을 예고했다.')
  c=self.item('c','포스코 임단협 타결…파업 철회','2026-10-28T02:00:00+00:00')
  result=group_articles([a,b,c]);self.assertEqual(len(result),2)
  self.assertEqual(sorted(len(x['timeline']) for x in result),[1,2])
  other=self.item('d','포스코 하청노조 원청교섭 요구')
  self.assertEqual(len(group_articles([a,other])),2)
 def test_accident_followup_and_conflicting_dates(self):
  a=dict(self.item('a','현대제철 당진공장 노동자 끼임 사망','2026-10-18T01:00:00+00:00'),description='오늘(18일) 사고가 발생했다.')
  follow=dict(self.item('b','현대제철 당진 끼임 사망에 노조 반발','2026-10-24T01:00:00+00:00'),description='지난 18일 하청 노동자가 숨졌다.')
  unknown=dict(self.item('c','현대제철 당진 끼임 사망 안전대책 요구'),description='안전관리 책임을 물었다.')
  self.assertEqual(len(group_articles([unknown,follow,a])),1)
  another=dict(a,id='d',description='오늘(20일) 사고가 발생했다.')
  groups=group_articles([a,unknown,another]);self.assertEqual(len(groups),1)
 def test_opinion_stays_separate_from_issue(self):
  a=self.item('a','포스코 노사 임금교섭 난항');b=self.item('b','[성명] 포스코 임금교섭 관련 입장')
  self.assertEqual(len(group_articles([a,b])),1);self.assertEqual(b['category'],'노사관계')

class UserNewsExamples(CategoryGroupingTests):
 def test_same_donation_different_headline_and_amount_expression(self):
  titles=['현대제철 순천공장, 안전한 보행길 위해 순천시에 H형 빛나는 도로 기금 전달','현대제철 순천공장, 교통안전 개선에 5천만 원 기부…임직원 뜻 모아','현대제철 순천공장, 임직원 기부로 교통안전 인프라 확충','현대제철 순천공장, H형 빛나는 도로 기금 5000만원 전달']
  items=[dict(self.item(str(i),t),description='임직원의 교통안전 기부금으로 보행환경을 개선했다.') for i,t in enumerate(titles)]
  self.assertEqual(len(group_articles(items)),1)
  different=self.item('different','현대제철 당진공장, 교통안전 개선에 5천만 원 기부')
  self.assertEqual(len(group_articles(items+[different])),2)
 def test_same_speaker_reprinted_not_different_views(self):
  a=self.item('a','이상휘 의원 포스코 멈추면 포항도 흔들려…노사 결단 촉구')
  b=self.item('b','이상휘 의원 포스코 멈추면 포항 흔들려…노사에 결단 촉구')
  c=self.item('c','김철수 의원 포스코 멈추면 포항도 흔들려…노사 결단 촉구')
  self.assertEqual(len(group_articles([a,b,c])),2)
 def test_unconscious_accident_and_historical_location(self):
  self.assertEqual(category('현대제철 당진공장서 기계에 낀 40대 근로자 심정지'),'안전')
  from news_grouping import current_place
  self.assertFalse(current_place(dict(self.item('a','현대제철 5년간 7명 숨져…하청노동자 안전 사각지대'),description='2024년에는 인천공장에서 사망했다.')))
  a=dict(self.item('a','현대제철 당진공장 기계 끼임 사망'),description='지난 18일 40대 노동자가 끼어 숨졌다.')
  b=dict(self.item('b','현대제철 당진제철소 사망사고 노조 반발'),description='안전 대책을 요구했다.')
  c=dict(self.item('c','현대제철 당진 하청노동자 끼임 사망'),description='사망 사고를 규탄했다.')
  self.assertEqual(len(group_articles([a,b,c])),1)
