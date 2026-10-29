import unittest,datetime as dt
from unittest.mock import patch
from email.utils import format_datetime
import news,app,test_news
from news_filter import classify
KEEP=["포항 떠받치는 양대산업 '철강·이차전지' 불황에 잇단 인력감축","조선·철강업계 임단협 잇단 타결… 포스코는 협상 난항","[경상칼럼]포스코 노조, 철강 위기 앞에 무엇을 지킬 것인가"]
EXCLUDE=['[오늘의 주요일정]사회(10월28일 수요일)','페로타임즈 손바닥뉴스 10월27일(화)','9월 3주 주요 제조업 전망','[위클립] 9월 2주','케이엔피이노텍, 광주 평동산업단지 제4공장 준공',"태신중공업, 국토부 '건축 2급' 철강구조물 공장 인증","[산업소식] 현대차 '썸머 페스타'…최대 300만원 혜택",'경남교육청, 장유 초등학교 통합 추진…옛 부지에 고교 캠퍼스 검토','바다에 빠진 시민 구조한 대학교수, 해경 감사장 받아',"당진교육지원청, 중1 대상 '공감' 교육 마무리","AI 우려 딛고, 코스피 '상승'...삼성생명·DL이앤씨 '활짝'",'세계 양궁의 도전 거세졌다…장영술 부회장 “LA 올림픽 더 철저히 준비','[금주의 제물포구의회] 제4회 임시회 개회…조례안 등 15건 심의 外','인천 제물포구, 어르신은 선생님·아이들은 제자로… 세대 잇는 특별한']
class RuleTests(unittest.TestCase):
 def test_user_labels(self):
  for title in KEEP:
   with self.subTest(title=title):self.assertEqual(classify(title)[0],'keep')
  for title in EXCLUDE:
   with self.subTest(title=title):self.assertEqual(classify(title,'현대제철 공장도 기사에 언급됐다')[0],'exclude')
 def test_structural_changes_not_rescue_noise(self):
  self.assertEqual(classify('현대제철 구조조정과 고용 협의')[0],'keep')
  self.assertEqual(classify('현대제철·폴리텍 채용 인력 양성 협약')[0],'review')
class FilterAPITests(unittest.TestCase):
 setUp=test_news.NewsTests.setUp
 config=test_news.NewsTests.config
 sample=test_news.NewsTests.sample
 def test_two_week_cutoff_and_review_override(self):
  self.config();now=news.utc_now();items=[]
  for i,days in enumerate([13,15]):
   n=self.sample();n.update(originallink='https://example.com/'+str(i),pubDate=format_datetime(now-dt.timedelta(days=days)));items.append(n)
  n=self.sample();n.update(title='[오늘의 주요일정] 현대제철',originallink='https://example.com/noise');items.append(n)
  with patch('news.fetch_news',return_value=items):r=self.c.post('/api/news/fetch',headers=self.h,json={})
  self.assertEqual(r.status_code,200);self.assertEqual(r.json['outdated'],1)
  self.assertEqual(self.v.get('/api/news').json['total'],1)
  excluded=self.c.get('/api/news?view=exclude').json['items'];self.assertEqual(len(excluded),1);self.assertTrue(excluded[0]['filter_reason'])
  self.assertEqual(self.v.get('/api/news?view=all').json['total'],1)
  n=excluded[0];self.assertEqual(self.c.post('/api/news/article',headers=self.h,json={'id':n['id'],'version':n['version'],'field':'important','value':True}).status_code,200)
  self.assertEqual(self.v.get('/api/news').json['total'],2)
  with app.db() as c:c.execute("UPDATE news_articles SET published=? WHERE id=?",((now-dt.timedelta(days=15)).isoformat(),n['id']))
  self.assertEqual(self.c.get('/api/news?view=all&excluded=1').json['total'],1)
