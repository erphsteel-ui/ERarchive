import json,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import paddle_adapter as pa
class PaddleTests(unittest.TestCase):
 def sample(self):return {'rec_texts':['강철의','함성','전국금속노동조합 충남지부 현대제철지회','노사협의회'], 'rec_scores':[.99,.98,.95,.5],'rec_boxes':[[20,0,45,10],[46,0,70,10],[10,95,90,100],[20,50,80,60]]}
 def test_issuer_footer_and_split_title(self):
  from app import suggest
  lines=pa.parse_result(self.sample(),100,100);r=suggest('', ['금속노조 충남지부 현대제철지회'],pa.regions(lines))
  self.assertEqual(r['title'],'강철의 함성');self.assertEqual(r['publishers'],['금속노조 충남지부 현대제철지회'])
  self.assertEqual(lines[-1]['box'],[.2,.5,.6,.1])
 def test_local_subprocess_conversion(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'page.png';Image.new('RGB',(100,100)).save(path)
   def execute(image,out,home,exe,det,rec):
    (out/'page_res.json').write_text(json.dumps(self.sample()))
    return {'load_seconds':1,'predict_seconds':2}
   with patch.object(pa,'status',return_value={'ready':True}),patch.object(pa,'worker_request',side_effect=execute):
    r=pa.recognize(path)
   self.assertEqual(r['engine'],'paddle');self.assertIn('노사협의회',r['raw']);self.assertEqual(len(r['variants'][0]['warnings']),1)
 def test_failure_returns_no_replacement(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'page.png';Image.new('RGB',(100,100)).save(path)
   with patch.object(pa,'status',return_value={'ready':True}),patch.object(pa,'worker_request',side_effect=subprocess.TimeoutExpired('ocr',300)):
    r=pa.recognize(path)
   self.assertEqual(r['variants'],[]);self.assertIn('5분',r['status'])
 def test_wrong_output_rejected(self):
  with self.assertRaises(ValueError):pa.parse_result({'rec_texts':['x'],'rec_scores':[],'rec_boxes':[]},100,100)
if __name__=='__main__':unittest.main()

class PersistentWorkerTests(unittest.TestCase):
 def test_model_is_loaded_once_for_two_requests(self):
  import sys,os
  pa.stop_worker()
  with tempfile.TemporaryDirectory() as tmp:
   home=Path(tmp);count=home/'loads.txt';out=home/'result';out.mkdir()
   (home/'paddleocr.py').write_text('''from pathlib import Path
import os,json
class Result:
 def save_to_json(self,out):Path(out,'result.json').write_text(json.dumps({'rec_texts':['ok'],'rec_scores':[.9],'rec_boxes':[[0,0,10,10]]}))
class PaddleOCR:
 def __init__(self,**kw):
  assert kw['enable_mkldnn'] is False
  with open(os.environ['TEST_LOAD_COUNT'],'a') as f:f.write('loaded\\n')
  print('library stdout noise')
 def predict(self,image):return [Result()]
''')
   with patch.dict(os.environ,{'PYTHONPATH':tmp,'TEST_LOAD_COUNT':str(count)}):
    try:
     first=pa.worker_request(home/'page.png',out,home,Path(sys.executable),home/'det',home/'rec');pid=pa._PROCESS.pid
     second=pa.worker_request(home/'page.png',out,home,Path(sys.executable),home/'det',home/'rec')
     self.assertEqual(pa._PROCESS.pid,pid);self.assertEqual(count.read_text().splitlines(),['loaded']);self.assertEqual(second['load_seconds'],0);self.assertTrue(first['ok'])
    finally:pa.stop_worker()
