import unittest
from regulations_index import parse_hybrid,preprocess
class HybridTests(unittest.TestCase):
 def test_articles_and_citations(self):
  items=parse_hybrid('제2장 포상제3조 (적용범위)\n제55조에도 불구하고\n부 칙 제19조 (시행일)\n시행한다')
  self.assertEqual(len(items),1);self.assertIn('제55조에도',items[0]['text'])
 def test_bylaws_and_appendix(self):
  p=parse_hybrid('1) 임원 선거관리 세칙\n제2장 선거관리\n제1조【목적】\n대의원\n부칙\n1. 시행한다')
  self.assertIn('임원 선거관리 세칙',p[0]['chapter']);self.assertEqual(len(p),1)
 def test_standard(self):
  p=parse_hybrid('회사표준\n1. 적용범위\n5. 복무\n5.2 근무시간\n5.2.1 근무시간\n1) 본문')
  self.assertEqual(p[0]['title'],'5.2.1 근무시간');self.assertEqual(p[0]['section'],'5.2 근무시간')
 def test_table_and_cleaning(self):
  p=parse_hybrid('제130조(마지막)\n본문\n2025. 1. 1\n대표이사 홍길동\n근속수당 100\n■ 제수당 지급 기준표')
  self.assertEqual(p[-1]['title'],'[별표] 제수당 지급 기준표');self.assertIn('근속수당',p[-1]['text'])
  self.assertIn('1. 회사는',preprocess('1. \n 회사는'));self.assertIn('4조 2교대',preprocess('- 4\n조 2교대'))
 def test_multiline_toc_addendum_deleted(self):
  raw='목 차\n전 문\n제4조(정당행위)\n제8장 벌칙\n제1장 총칙\n전 문\n전문 본문\n제1조【교섭권 보장】\n첫째 줄\n□ 포항\n둘째 줄\n제4조(정당행위)\n실제 본문\n제40조 삭제\n부칙 <제5310호>\n제4조(경과조치)\n부칙 본문'
  p=parse_hybrid(raw)
  self.assertEqual([x['title'] for x in p],['[전문] 전문','제1조【교섭권 보장】','제4조(정당행위)','제40조 삭제'])
  self.assertEqual(p[1]['text'],'첫째 줄\n□ 포항\n둘째 줄');self.assertEqual(p[-1]['text'],'삭제된 조항입니다.')
 def test_continuing_chapter_and_signatures(self):
  p=parse_hybrid('제14장 부칙\n제126조(시행)\n적용한다\n제130조(마지막)\n마지막 본문\n2026. 8. 6\n대표이사 홍길동\n표 내용\n■ 제수당 지급 기준표')
  self.assertEqual([x['number'] for x in p],['126','130','']);self.assertEqual(p[-1]['text'],'표 내용')
 def test_inline_and_empty(self):
  p=parse_hybrid('제1조(목적) 본문 즉시 시작\n이어지는 줄\n제2조(빈 목차)\n제3조(다음)\n본문')
  self.assertEqual(len(p),2);self.assertEqual(p[0]['text'],'본문 즉시 시작\n이어지는 줄')
if __name__=='__main__':unittest.main()
