import unittest,json,sys,importlib.util
from pathlib import Path
from schedule_extract import extract_events,hwp_text,render_hwp_items

class StructureTests(unittest.TestCase):
 def test_multiple_body_dates_and_ranges(self):
  es=extract_events('세정:27일 확간회의, 11/7일 전노대 32명 참가\n현대제철:27~28일 확대간부수련회, 11/4일 현대제철 특별산안보 진행',reference='2026-10-26')
  self.assertEqual([(e['start'],e['end'],e['title']) for e in es],[('2026-10-27','2026-10-27','확간회의'),('2026-11-07','2026-11-07','전국노동자대회'),('2026-10-27','2026-10-28','확대간부 수련회'),('2026-11-04','2026-11-04','특별 산업안전보건위원회')])
  self.assertEqual(es[0]['subject'],'세정');self.assertEqual(es[2]['subject'],'현대제철')
 def test_multiple_dates_without_comma_do_not_borrow_activity(self):
  es=extract_events('현대제철: 10/27 확간회의 10/30 조합원 교육 11/4 장소 미정',reference='2026-10-26')
  self.assertEqual([(e['start'],e['title']) for e in es],[('2026-10-27','확간회의'),('2026-10-30','조합원 교육')])
 def test_unconnected_dates_never_inherit(self):
  self.assertEqual(extract_events('*전국노동자대회\n11/8\n11/9\n11/10\n11/11',reference='2026-10-26'),[])
 def test_calendar_coordinates_and_ambiguous_merged_cell(self):
  def cell(r,c,text,cs=1):return dict(row=r,col=c,rs=1,cs=cs,items=[text])
  table=dict(cells=[cell(0,i,'11/'+str(7+i)) for i in range(3)]+[cell(1,0,'전국노동자대회'),cell(1,1,'조직담당자회의'),cell(1,2,'주체 불명 수련회',2)]+[cell(2,i,'11/'+str(14+i)) for i in range(3)])
  text='\n'.join(render_hwp_items([table]));es=extract_events(text,reference='2026-10-26')
  self.assertEqual([(e['start'],e['title']) for e in es],[('2026-11-07','전국노동자대회'),('2026-11-08','조직담당자회의')])
 def test_real_hwp_calendar_no_next_week_carry(self):
  files=list((Path(__file__).parent.parent/'upload').glob('*회의자료.hwp'))
  if not files:self.skipTest('local real HWP fixture unavailable')
  es=extract_events(hwp_text(files[0].read_bytes()),files[0].name)
  self.assertTrue(any(e['start']=='2026-11-07' and e['title']=='전국노동자대회' for e in es))
  self.assertTrue(any(e['start']=='2026-11-12' and e['end']=='2026-11-13' and e['title']=='마음돌봄 수련회' for e in es))
  self.assertFalse(any(e['start'] in ('2026-11-08','2026-11-09','2026-11-10','2026-11-11') and '전국노동자' in e['title'] for e in es))
  self.assertFalse(any(e['start'] in ('2026-11-15','2026-11-16','2026-11-17','2026-11-18') and '마음돌봄' in e['title'] for e in es))
  self.assertFalse(any(e['start'] in ('2026-10-26','2026-10-27','2026-10-28') and '조직담당자' in e['title'] for e in es))

if __name__=='__main__':unittest.main()
