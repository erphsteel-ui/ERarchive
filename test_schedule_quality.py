import unittest
from schedule_extract import extract_events

class QualityTests(unittest.TestCase):
 def get(self,text,ref='2026-10-21'):return extract_events(text,reference=ref)
 def test_screenshot_noise_excluded(self):
  rejected=[
   '10월 20일(화) 순천에서 임금 제도개선위원회 상견례가 진행되었다.',
   '10. 20.(화) 12:00부터', '11월 19일(목)', '5월19일',
   '편집:교육선전부 · 전화:055)280-9524~7 · 홈페이지:www.hwianojo.or.kr 발행일:2026년10월22일(목)',
   '10월 18일 노동조건 개선과 차별 철폐를 요구하며 크레인 고공농성에',
   '10월 8일 현대차의 파견법 위반을 인정하고 직접고용하라고 시정 지시',
   '5월18일 선거는 3년에 한 번 치러지는 선거로',
   '2026.10.21.수(26-29호, 585호)\n임금 제도개선위원회 KICK-OFF',
   '2026.10.21\n임금 제도개선위원회 KICK-OFF',
  ]
  for t in rejected:self.assertEqual(self.get(t),[],t)
 def test_screenshot_useful_schedules(self):
  cases=[('만족도 설문조사 기간은 10월 20일(화) ~ 27일(화)','2026-10-20','2026-10-27','만족도 설문조사'),
   ('* 차기 교섭 일정 : 10/29(목) 예정','2026-10-29','2026-10-29','차기 교섭'),
   ('10월 27일 [화] 2차 품평회! 이번에도 눈속임 개선이라면 업체 전면 교체 한다!','2026-10-27','2026-10-27','2차 품평회')]
  for text,start,end,title in cases:
   es=self.get(text);self.assertEqual(len(es),1,text);self.assertEqual((es[0]['start'],es[0]['end'],es[0]['title']),(start,end,title))
 def test_no_borrowed_meeting_from_venue(self):
  e=self.get('☞ 4. 열사영상 시사회 개최\n일시/장소 : 2026년 10월 23일 15시 / 서울 회의실')[0]
  self.assertEqual(e['title'],'열사영상 시사회')
 def test_deadline_stages(self):
  es=self.get('안전 숏폼 영상 공모 시행\n일정\n10/27 제출 마감 → 10/28 적합성 검토 → 10/30 안전마일리지 지급')
  self.assertEqual([e['title'] for e in es],['안전 숏폼 영상 공모 마감','안전 숏폼 영상 공모 검토','안전마일리지 지급'])
 def test_period_crosses_year(self):
  e=self.get('조합원 교육 기간 12/30 ~ 1/2',ref='2026-12-20')[0]
  self.assertEqual((e['start'],e['end']),('2026-12-30','2027-01-02'))
 def test_explicit_subject_separate_from_venue(self):
  e=self.get('현대제철 당진지회 : 10/29 단체교섭 예정')[0]
  self.assertEqual(e['subject'],'현대제철 당진지회')
  e=self.get('단체교섭\n일시 : 2026.10.29\n장소 : 포항 회의실')[0]
  self.assertEqual(e['subject'],'')
 def test_old_date_is_relative_to_document_not_today(self):
  self.assertEqual(self.get('9/30 간담회',ref='2026-10-21'),[])
  self.assertEqual(len(self.get('10/29 교섭 예정',ref='2026-10-21')),1)
 def test_multi_clause_date_gets_its_own_activity(self):
  e=self.get('현담산업 : 19일 확간회의, 20일 교육, 11/4일 조인식')[0]
  self.assertEqual(e['title'],'조인식')
 def test_day_without_month_does_not_invent_date(self):
  self.assertEqual(self.get('19일 확간회의'),[])

if __name__=='__main__':unittest.main()
