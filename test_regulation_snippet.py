import random, unittest
from regulations_index import snippet,normalize

def reference(text,query,limit=480):
 target=normalize(query);chars=[];positions=[]
 for i,char in enumerate(text):
  for c in normalize(char):chars.append(c);positions.append(i)
 index=''.join(chars).find(target)
 start=max(0,positions[index]-100) if index>=0 else 0
 return ('…' if start else '')+text[start:start+limit]+('…' if start+limit<len(text) else '')
class SnippetTests(unittest.TestCase):
 def test_matching_and_unicode(self):
  rng=random.Random(9);alphabet='가나다ABC  \n㎏①'
  for _ in range(100):
   text=''.join(rng.choice(alphabet) for _ in range(600));q=text[rng.randrange(500):][:rng.randrange(1,12)]
   if normalize(q):self.assertEqual(snippet(text,q),reference(text,q))
  self.assertIn('근 로 시간',snippet('앞'*200+'근 로 시간'+'뒤'*600,'근로시간'))
 def test_large_input_peak_memory(self):
  import tracemalloc
  text='가'*200000+'근로시간';tracemalloc.start()
  try:
   result=snippet(text,'근로시간');_,peak=tracemalloc.get_traced_memory()
  finally:tracemalloc.stop()
  self.assertIn('근로시간',result);self.assertLess(peak,2*1024*1024)
if __name__=='__main__':unittest.main()
