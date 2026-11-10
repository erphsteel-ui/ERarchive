import unittest,json,io,zipfile,threading
from unittest.mock import patch
import test_app,app,financials as f

class FinancialMathTests(unittest.TestCase):
 def account(self,id,name,amount,cum=None,currency='KRW',sj='IS'):
  return dict(account_id=id,account_nm=name,thstrm_amount=amount,thstrm_add_amount=cum,currency=currency,sj_div=sj,rcept_no='20260301000001')
 def test_standard_accounts_currencies_and_absence(self):
  data=f.extract([self.account('ifrs-full_Revenue','수익','1,000','1800'),self.account('dart_OperatingIncomeLoss','영업이익(손실)','(100)','-150'),self.account('ifrs-full_ProfitLoss','당기순손익','0','0'),self.account('ifrs-full_ProfitLossAttributableToOwnersOfParent','지배기업 소유주 순이익','800')],2)
  self.assertEqual(data['metrics']['revenue']['direct'],1000);self.assertEqual(data['metrics']['operating']['cumulative'],-150)
  self.assertEqual(data['metrics']['net']['direct'],0);self.assertIsNone(data['metrics']['pretax']['direct'])
  self.assertIsNone(f.extract([self.account('ifrs-full_Revenue','매출액','100',currency='USD')],1)['metrics']['revenue']['direct'])
  self.assertIsNone(f.extract([self.account('ifrs-full_Revenue','매출액','100',currency='')],1)['metrics']['revenue']['direct'])
  self.assertIsNone(f.extract([self.account('ifrs-full_Revenue','매출액','100'),self.account('ifrs-full_Revenue','매출액','200')],1)['metrics']['revenue']['direct'])
 def report(self,y,q,direct,cumulative):
  return dict(year=y,quarter=q,status='available',updated='now',data=dict(metrics={m:dict(direct=direct,cumulative=cumulative) for m in f.METRICS},warnings=[],receipts=['20260301000001']))
 def test_quarter_vs_cumulative_q4_and_comparisons(self):
  records=[self.report(2024,3,100,300),self.report(2024,4,450,450),self.report(2025,1,180,180),self.report(2025,2,220,400),self.report(2025,3,250,650),self.report(2025,4,1000,1000)]
  quarter=f.build_rows(records,2025,2025);self.assertEqual(quarter[0]['values']['revenue'],350);self.assertEqual(quarter[0]['net_qoq'],40);self.assertAlmostEqual(quarter[0]['net_yoy'],(350-150)/150*100);self.assertEqual(quarter[2]['values']['revenue'],220)
  self.assertAlmostEqual(quarter[3]['revenue_qoq'],20)
  self.assertEqual(f.build_rows(records,2025,2025,'cumulative')[2]['values']['revenue'],400)
  self.assertEqual(f.build_rows(records,2025,2025,'annual')[0]['values']['revenue'],1000)
  self.assertIsNone(f.build_rows([records[-1]],2025,2025)[0]['values']['revenue'])
  self.assertIsNone(f.growth(1,0));self.assertEqual(f.growth(10,-10),200)
 def test_corporation_master_exact_operating_entities(self):
  xml=('<result><list><corp_code>00000001</corp_code><corp_name>포스코</corp_name></list>'
       '<list><corp_code>00000002</corp_code><corp_name>포스코홀딩스</corp_name></list>'
       '<list><corp_code>00000003</corp_code><corp_name>동국제강</corp_name><stock_code>460860</stock_code></list>'
       '<list><corp_code>00000004</corp_code><corp_name>동국홀딩스</corp_name><stock_code>001230</stock_code></list></result>').encode()
  data=io.BytesIO()
  with zipfile.ZipFile(data,'w') as z:z.writestr('CORPCODE.xml',xml)
  resolved=f.resolve_companies(data.getvalue());self.assertEqual(resolved['posco']['corp_code'],'00000001')
  self.assertEqual(resolved['dongkuk']['corp_code'],'00000003');self.assertEqual(len(resolved),2)
 def test_dart_status_is_sanitized(self):
  with patch('financials.dart_bytes',return_value=json.dumps({'status':'020','message':'privatekey'}).encode()):
   with self.assertRaises(f.DartError) as cm:f.dart_report('x'*40,'00000001',2025,1,'CFS')
  self.assertNotIn('privatekey',str(cm.exception))

class FinancialAPITests(unittest.TestCase):
 def setUp(self):
  test_app.Tests.setUp(self)
  with app.db() as c:c.execute('DELETE FROM financial_reports');c.execute('DELETE FROM dart_companies')
  (app.DATA/'dart_config.json').unlink(missing_ok=True)
 def test_permissions_key_and_validation(self):
  self.assertEqual(self.v.get('/api/financials').status_code,200)
  self.assertEqual(self.v.get('/api/financials/config').status_code,403)
  self.assertEqual(self.v.post('/api/financials/fetch',headers=self.vh,json={}).status_code,403)
  self.assertEqual(self.c.post('/api/financials/config',json={'key':'a'*40}).status_code,403)
  self.assertEqual(self.c.post('/api/financials/config',headers=self.h,json={'key':'a'*40}).status_code,200)
  self.assertEqual(self.c.get('/api/financials/config').json,{'configured':True})
  self.assertNotIn('a'*40,self.v.get('/api/financials').get_data(as_text=True))
  self.assertEqual(self.v.get('/api/financials?start=2015&end=2026').status_code,400)
  self.assertEqual(self.v.get('/api/financials?company=unlisted').status_code,400)
 def test_background_fetch_source_and_missing_data(self):
  self.c.post('/api/financials/config',headers=self.h,json={'key':'b'*40})
  with app.db() as c:c.execute('INSERT INTO dart_companies VALUES(?,?,?,?,?)',('hyundai-steel','00000001','현대제철','004020','now'))
  def response(key,corp,year,q,fs):
   self.assertEqual(fs,'OFS')
   if q==2:return []
   return [FinancialMathTests().account('ifrs-full_Revenue','매출액',str(q*100000000),str(q*100000000))]
  with patch('financials.dart_report',side_effect=response):
   res=self.c.post('/api/financials/fetch',headers=self.h,json=dict(company='hyundai-steel',fs='OFS',start=2025,end=2025));self.assertEqual(res.status_code,200)
   for thread in threading.enumerate():
    if thread.name=='dart-financials':thread.join(3)
  data=self.v.get('/api/financials?company=hyundai-steel&fs=OFS&start=2025&end=2025').json
  self.assertFalse(data['job']['running']);self.assertEqual(data['job']['error'],'')
  self.assertEqual(data['rows'][0]['values']['revenue'],100000000)
  self.assertEqual(data['rows'][2]['status'],'no_data');self.assertIsNone(data['rows'][2]['values']['revenue'])
  self.assertIsNone(self.v.get('/api/financials?start=2025&end=2025').json['rows'][0]['values']['revenue'])
 def test_failure_preserves_cache_and_blocks_overlap(self):
  self.c.post('/api/financials/config',headers=self.h,json={'key':'c'*40})
  with app.db() as c:
   c.execute('INSERT INTO dart_companies VALUES(?,?,?,?,?)',('hyundai-steel','00000001','현대제철','004020','now'))
   c.execute('INSERT INTO financial_reports VALUES(?,?,?,?,?,?,?,?)',('hyundai-steel','00000001',2025,1,'CFS','available',json.dumps(dict(metrics=dict(revenue=dict(direct=123,cumulative=123)),warnings=[],receipts=[])),'before'))
  entered=threading.Event();release=threading.Event()
  def failure(*args):
   entered.set();release.wait(3);raise f.DartError('DART: API 이용 한도 초과 (코드 020)')
  with patch('financials.dart_report',side_effect=failure):
   self.assertEqual(self.c.post('/api/financials/fetch',headers=self.h,json=dict(start=2025,end=2025)).status_code,200)
   self.assertTrue(entered.wait(2))
   try:
    self.assertEqual(self.c.post('/api/financials/fetch',headers=self.h,json=dict(start=2025,end=2025)).status_code,409)
    self.assertEqual(self.c.post('/api/financials/config',headers=self.h,json={'key':'d'*40}).status_code,409)
   finally:release.set()
   for thread in threading.enumerate():
    if thread.name=='dart-financials':thread.join(3)
  data=self.c.get('/api/financials?start=2025&end=2025').json
  self.assertIn('020',data['job']['error']);self.assertEqual(data['rows'][-1]['values']['revenue'],123)
 def test_collect_both_bases_in_one_job(self):
  self.c.post('/api/financials/config',headers=self.h,json={'key':'e'*40})
  with app.db() as c:c.execute('INSERT INTO dart_companies VALUES(?,?,?,?,?)',('hyundai-steel','00000001','현대제철','004020','now'))
  calls=[]
  def response(key,corp,year,q,fs):
   calls.append((year,q,fs))
   return [] if fs=='OFS' else [FinancialMathTests().account('ifrs-full_Revenue','매출액','100000000','100000000')]
  self.assertEqual(self.c.post('/api/financials/fetch',headers=self.h,json=dict(start=2025,end=2025,both_fs='true')).status_code,400)
  with patch('financials.dart_report',side_effect=response):
   self.assertEqual(self.c.post('/api/financials/fetch',headers=self.h,json=dict(start=2025,end=2025,both_fs=True)).status_code,200)
   for thread in threading.enumerate():
    if thread.name=='dart-financials':thread.join(3)
  self.assertEqual(len(calls),16);self.assertEqual({x[2] for x in calls},{'CFS','OFS'})
  self.assertEqual(self.v.get('/api/financials?start=2025&end=2025&fs=OFS').json['rows'][0]['status'],'no_data')
  data=self.v.get('/api/financials?start=2025&end=2025&fs=CFS').json;self.assertEqual(data['job']['done'],16);self.assertEqual(data['job']['error'],'');self.assertEqual(data['rows'][0]['status'],'available')
