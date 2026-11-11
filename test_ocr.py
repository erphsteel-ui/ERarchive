import unittest,io
from unittest.mock import patch
import test_app,app
from ocr_engine import parse_tsv,suggestions,recognize_body
class OCRTests(unittest.TestCase):
 setUp=test_app.Tests.setUp
 img=test_app.Tests.img
 upload=test_app.Tests.upload
 doc=test_app.Tests.doc
 save=test_app.Tests.save
 def test_preview_history_original_and_permissions(self):
  result={'raw':'최초 본문','variants':[{'name':'시험','text':'교정 후보','confidence':80,'warning_count':1,'warnings':[{'text':'노사협의희','confidence':40,'box':[.1,.1,.5,.4],'suggestions':['노사협의회']}]}],'selected':0,'status':'완료'}
  with patch.object(app,'recognize_body',return_value=result):did=self.upload(['pink'])
  d=self.doc(did);pid=d['pages'][0]['id'];endpoint='/api/pages/'+pid+'/ocr'
  self.assertEqual(app.app.test_client().get(endpoint).status_code,401)
  self.assertEqual(self.v.get(endpoint).status_code,403)
  result={**result,'raw':'다시 인식','variants':[{**result['variants'][0],'text':'새로운 후보'}]}
  with patch.object(app,'recognize_body',return_value=result):
   r=self.c.post(endpoint,json={'version':d['version'],'layout':'auto'},headers=self.h)
  self.assertEqual(r.status_code,200);self.assertEqual(self.doc(did),d)
  rid=r.json['run_id'];crop='/api/ocr-runs/'+rid+'/crop/0/0'
  self.assertEqual(self.c.get(crop).mimetype,'image/png');self.assertEqual(self.v.get(crop).status_code,403)
  self.assertEqual(self.c.get(crop[:-1]+'99').status_code,404)
  d['texts']={pid:'최종 교정 본문'};d['ocr_runs']={pid:rid};self.assertEqual(self.save(d).status_code,200)
  stored=self.c.get(endpoint).json
  self.assertEqual(stored['original']['text'],'최초 본문');self.assertEqual(stored['history'][0]['text'],'교정 후보')
  current=self.doc(did);self.assertEqual(current['pages'][0]['text'],'최종 교정 본문')
  current['texts']={pid:'잘못 덮어쓰기'};current['ocr_runs']={pid:rid}
  self.assertEqual(self.save(current).status_code,409)
  self.assertEqual(self.doc(did)['pages'][0]['text'],'최종 교정 본문')
  self.assertEqual(self.c.post(endpoint,json={'version':1},headers=self.h).status_code,409)
 def test_migration_snapshot(self):
  did=self.upload(['cyan']);d=self.doc(did);pid=d['pages'][0]['id']
  with app.db() as c:
   c.execute('DELETE FROM page_original WHERE page=?',(pid,));c.execute('UPDATE pages SET text=? WHERE id=?',('기존 수동 수정',pid))
  app.init();app.init()
  data=self.c.get('/api/pages/'+pid+'/ocr').json
  self.assertEqual(data['original'],{'text':'기존 수동 수정','source':'업데이트 시 보존한 본문'})
 def test_failed_ocr_preview_preserves_text(self):
  did=self.upload(['brown']);d=self.doc(did);pid=d['pages'][0]['id']
  with patch.object(app,'recognize_body',return_value={'raw':'','variants':[],'selected':0,'status':'실패'}):
   self.assertEqual(self.c.post('/api/pages/'+pid+'/ocr',json={'version':d['version']},headers=self.h).status_code,200)
  self.assertEqual(d,self.doc(did))
 def test_invalid_text_payload(self):
  d=self.doc(self.upload(['lime']));d['texts']=[];self.assertEqual(self.save(d).status_code,400)
class ParserTests(unittest.TestCase):
 def test_coordinates_and_hangul_spacing(self):
  t='level\tpage_num\tblock_num\tpar_num\tline_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t10\t20\t10\t10\t90\t노\n5\t1\t1\t1\t1\t21\t20\t10\t10\t80\t조\n'
  lines=parse_tsv(t,100,100)
  self.assertEqual(lines[0]['text'],'노조');self.assertEqual(lines[0]['words'][0]['confidence'],80)
  self.assertAlmostEqual(lines[0]['words'][0]['box'][2],.21)
 def test_suggestions_are_limited(self):
  self.assertEqual(suggestions('노사협의희'),['노사협의회']);self.assertEqual(suggestions('1,400,000'),[]);self.assertEqual(suggestions('2026.10.21'),[])
 def test_unavailable_engine(self):
  with patch('ocr_engine.shutil.which',return_value=None),patch.dict('os.environ',{},clear=True):
   self.assertEqual(recognize_body('no-file')['variants'],[])
if __name__=='__main__':unittest.main()
