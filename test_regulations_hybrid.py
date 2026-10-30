import unittest
from regulations_index import parse_hybrid,preprocess
class HybridTests(unittest.TestCase):
 def test_articles_and_citations(self):
  items=parse_hybrid('제2장 포상제3조 (적용범위)\n제55조에도 불구하고\n부 칙 제19조 (시행일)\n시행한다')
  self.assertEqual(len(items),2);self.assertIn('제55조에도',items[0]['text']);self.assertTrue(items[1]['title'].startswith('[부칙]'))
 def test_bylaws_and_appendix(self):
  p=parse_hybrid('1) 임원 선거관리 세칙\n제2장 선거관리\n제1조【목적】\n대의원\n부칙\n1. 시행한다')
  self.assertIn('임원 선거관리 세칙',p[0]['chapter']);self.assertEqual(p[1]['title'],'[부칙]')
 def test_standard(self):
  p=parse_hybrid('회사표준\n1. 적용범위\n5. 복무\n5.2 근무시간\n5.2.1 근무시간\n1) 본문')
  self.assertEqual(p[0]['title'],'5.2.1 근무시간');self.assertEqual(p[0]['section'],'5.2 근무시간')
 def test_table_and_cleaning(self):
  p=parse_hybrid('제130조(마지막)\n본문\n2025. 1. 1\n대표이사 홍길동\n근속수당 100\n■ 제수당 지급 기준표')
  self.assertEqual(p[-1]['title'],'[별표] 제수당 지급 기준표');self.assertIn('근속수당',p[-1]['text'])
  self.assertIn('1. 회사는',preprocess('1. \n 회사는'));self.assertIn('4조 2교대',preprocess('- 4\n조 2교대'))
if __name__=='__main__':unittest.main()
