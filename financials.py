"""DART financial statements: explicit company resolution, raw cache and quarter arithmetic."""
import datetime as dt,io,json,os,re,threading,urllib.request,urllib.parse,zipfile
import xml.etree.ElementTree as ET
from flask import request,jsonify,abort,session

COMPANIES=[
 ('hyundai-steel','현대제철',['현대제철'],'004020'),
 ('hyundai-motor','현대차',['현대자동차'],'005380'),
 ('kia','기아차',['기아','기아자동차'],'000270'),
 ('mobis','현대모비스',['현대모비스'],'012330'),
 ('wia','현대위아',['현대위아'],'011210'),
 ('rotem','현대로템',['현대로템'],'064350'),
 ('transys','현대트랜시스',['현대트랜시스'],''),
 ('kefico','현대케피코',['현대케피코'],''),
 ('posco','포스코',['포스코'],''),
 ('dongkuk','동국제강',['동국제강'],'460860')]
REPORTS={1:'11013',2:'11012',3:'11014',4:'11011'}
METRICS={
 'revenue':(['ifrs-full_Revenue','ifrs_Revenue'],['매출액','수익(매출액)','영업수익','매출']),
 'operating':(['dart_OperatingIncomeLoss'],['영업이익','영업이익(손실)','영업손익','영업손실']),
 'pretax':(['ifrs-full_ProfitLossBeforeTax','ifrs_ProfitLossBeforeTax'],['법인세비용차감전순이익','법인세비용차감전순이익(손실)','법인세비용차감전순손익','법인세비용차감전순손실','법인세차감전순이익','법인세차감전이익(손실)','법인세비용차감전이익(손실)']),
 'net':(['ifrs-full_ProfitLoss','ifrs_ProfitLoss'],['당기순이익','당기순이익(손실)','당기순손익','당기순손실','분기순이익','분기순이익(손실)','반기순이익','반기순이익(손실)'])}
METRIC_LABELS={'revenue':'매출액','operating':'영업이익','pretax':'법인세차감전이익','net':'당기순이익'}
class DartError(Exception):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def dart_bytes(endpoint,key,params=None):
 if endpoint not in ('corpCode.xml','fnlttSinglAcntAll.json'):raise DartError('지원하지 않는 DART 요청입니다.')
 query=urllib.parse.urlencode(dict(params or {},crtfc_key=key))
 req=urllib.request.Request('https://opendart.fss.or.kr/api/'+endpoint+'?'+query,headers={'User-Agent':'ERArchive/0.36'})
 try:
  with urllib.request.build_opener(NoRedirect()).open(req,timeout=20) as response:data=response.read(24*1024*1024+1)
 except (OSError,ValueError):raise DartError('DART 연결에 실패했습니다. 외부 접속·인증키·등록 IP를 확인하세요.') from None
 if len(data)>24*1024*1024:raise DartError('DART 응답 크기가 허용 범위를 초과했습니다.')
 return data

def dart_report(key,corp,year,quarter,fs):
 try:data=json.loads(dart_bytes('fnlttSinglAcntAll.json',key,dict(corp_code=corp,bsns_year=str(year),reprt_code=REPORTS[quarter],fs_div=fs)))
 except (ValueError,UnicodeError):raise DartError('DART 응답 형식이 올바르지 않습니다.') from None
 if not isinstance(data,dict):raise DartError('DART 응답 형식이 올바르지 않습니다.')
 status=data.get('status')
 if status=='013':return []
 if status!='000':
  messages={'010':'등록되지 않은 인증키','011':'사용 중지된 인증키','012':'허용되지 않은 IP','020':'API 이용 한도 초과','800':'DART 점검 중','901':'인증키 계정 만료'}
  raise DartError('DART: '+messages.get(status,'요청 오류')+' (코드 '+str(status)[:3]+')')
 rows=data.get('list')
 if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):raise DartError('DART 재무정보 형식이 올바르지 않습니다.')
 return rows

def norm(value):return re.sub(r'\s+|주식회사|\(주\)|㈜','',value or '').casefold()
def resolve_companies(data):
 try:
  with zipfile.ZipFile(io.BytesIO(data)) as archive:
   files=[f for f in archive.infolist() if f.filename.lower().endswith('.xml')]
   if len(files)!=1 or files[0].file_size>100*1024*1024:raise DartError('DART 기업목록 크기/형식 오류')
   xml=archive.read(files[0])
  if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():raise DartError('DART 기업목록 XML 오류')
  root=ET.fromstring(xml)
 except (zipfile.BadZipFile,ET.ParseError,RuntimeError):raise DartError('DART 기업목록을 읽지 못했습니다. 인증키를 확인하세요.') from None
 rows=[{k:r.findtext(k,'').strip() for k in ('corp_code','corp_name','stock_code')} for r in root.findall('list')]
 result={}
 for cid,label,aliases,stock in COMPANIES:
  matches=[r for r in rows if norm(r['corp_name']) in {norm(n) for n in aliases} and re.fullmatch(r'\d{8}',r['corp_code'])]
  listed=[r for r in matches if stock and r['stock_code']==stock]
  if listed:matches=listed
  if len(matches)==1:result[cid]=matches[0]
 return result

def amount(value):
 if value is None:return None
 text=str(value).strip().replace(',','').replace('−','-')
 if text.startswith('(') and text.endswith(')'):text='-'+text[1:-1]
 return int(text) if re.fullmatch(r'-?\d+',text) else None

def extract(rows,quarter):
 metrics={};warnings=[]
 for metric,(ids,names) in METRICS.items():
  candidates=[r for r in rows if r.get('sj_div') in ('IS','CIS') and (r.get('account_id') in ids or norm(r.get('account_nm')) in {norm(x) for x in names})]
  standard=[r for r in candidates if r.get('account_id') in ids]
  if standard:candidates=standard
  if any(r.get('sj_div')=='IS' for r in candidates):candidates=[r for r in candidates if r.get('sj_div')=='IS']
  distinct={(r.get('thstrm_amount'),r.get('thstrm_add_amount'),r.get('currency')) for r in candidates}
  if not candidates or len(distinct)>1:
   metrics[metric]=dict(direct=None,cumulative=None);warnings.append(METRIC_LABELS[metric]+(': 계정 중복·값 불일치' if candidates else ': 계정 없음'));continue
  row=candidates[0]
  if row.get('currency')!='KRW':
   metrics[metric]=dict(direct=None,cumulative=None);warnings.append(METRIC_LABELS[metric]+': 원화(KRW) 아님 또는 통화 미확인');continue
  direct=amount(row.get('thstrm_amount'))
  cumulative=direct if quarter in (1,4) else amount(row.get('thstrm_add_amount'))
  metrics[metric]=dict(direct=direct,cumulative=cumulative,account_id=row.get('account_id',''),account_name=row.get('account_nm',''),statement=row.get('sj_div'),currency='KRW')
 return dict(metrics=metrics,warnings=warnings,receipts=sorted({r.get('rcept_no','') for r in rows if re.fullmatch(r'\d{14}',r.get('rcept_no',''))}))

def difference(a,b):return a-b if a is not None and b is not None else None
def ratio(a,b):return a/b*100 if a is not None and b not in (None,0) else None
def growth(a,b):return difference(a,b)/abs(b)*100 if a is not None and b not in (None,0) else None

def build_rows(records,start,end,mode='quarterly',quarter=0):
 lookup={(r['year'],r['quarter']):r for r in records}
 def value(year,q,metric):
  row=lookup.get((year,q),{});m=row.get('data',{}).get('metrics',{}).get(metric,{})
  if mode=='annual':return m.get('cumulative') if q==4 else None
  if mode=='cumulative':return m.get('cumulative')
  if q==4:
   prev=lookup.get((year,3),{}).get('data',{}).get('metrics',{}).get(metric,{})
   return difference(m.get('cumulative'),prev.get('cumulative'))
  if m.get('direct') is not None:return m['direct']
  if q>1:
   prev=lookup.get((year,q-1),{}).get('data',{}).get('metrics',{}).get(metric,{})
   return difference(m.get('cumulative'),prev.get('cumulative'))
  return m.get('cumulative')
 result=[]
 for year in range(start,end+1):
  for q in ([4] if mode=='annual' else range(1,5)):
   if quarter and q!=quarter and mode!='annual':continue
   row=lookup.get((year,q));values={m:value(year,q,m) for m in METRICS};py,pq=(year,q-1) if q>1 else (year-1,4)
   receipts=list(row['data'].get('receipts',[])) if row else []
   if mode=='quarterly' and q==4:
    prev=lookup.get((year,3));receipts+=prev['data'].get('receipts',[]) if prev else []
   result.append(dict(year=year,quarter=q,values=values,operating_margin=ratio(values['operating'],values['revenue']),net_margin=ratio(values['net'],values['revenue']),
     revenue_qoq=growth(values['revenue'],value(py,pq,'revenue')) if mode=='quarterly' else None,operating_qoq=growth(values['operating'],value(py,pq,'operating')) if mode=='quarterly' else None,net_qoq=growth(values['net'],value(py,pq,'net')) if mode=='quarterly' else None,
     revenue_yoy=growth(values['revenue'],value(year-1,q,'revenue')),operating_yoy=growth(values['operating'],value(year-1,q,'operating')),net_yoy=growth(values['net'],value(year-1,q,'net')),pretax_yoy=growth(values['pretax'],value(year-1,q,'pretax')),status=row['status'] if row else 'not_collected',updated=row['updated'] if row else '',warnings=row['data'].get('warnings',[]) if row else [],
     derived=mode=='quarterly' and q==4,receipts=list(dict.fromkeys(receipts))))
 return list(reversed(result))

def install(a):
 config_path=a.DATA/'dart_config.json';guard=threading.Lock();job_guard=threading.Lock();job={'running':False,'done':0,'total':0,'error':'','company':''}
 with a.db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS financial_reports(company TEXT,corp_code TEXT,year INTEGER,quarter INTEGER,fs TEXT,status TEXT,data TEXT,updated TEXT,PRIMARY KEY(company,year,quarter,fs));
  CREATE TABLE IF NOT EXISTS dart_companies(company TEXT PRIMARY KEY,corp_code TEXT,corp_name TEXT,stock_code TEXT,updated TEXT);''')
 def config():return json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
 def snapshot():
  with job_guard:return dict(job)
 def selection(b):
  try:
   company=b.get('company','hyundai-steel');fs=b.get('fs','CFS');start=int(b.get('start',dt.datetime.now().year-2));end=int(b.get('end',dt.datetime.now().year));mode=b.get('mode','quarterly');quarter=int(b.get('quarter',0))
  except (TypeError,ValueError):abort(400)
  if not all(isinstance(v,str) for v in (company,fs,mode)):abort(400)
  if company not in {x[0] for x in COMPANIES} or fs not in ('CFS','OFS') or not 2015<=start<=end<=dt.datetime.now().year or end-start>5 or mode not in ('quarterly','cumulative','annual') or quarter not in (0,1,2,3,4):abort(400)
  return company,fs,start,end,mode,quarter
 @a.app.get('/api/financials/config')
 @a.protected(True)
 def financial_config_get():return jsonify(configured=bool(config().get('key')))
 @a.app.post('/api/financials/config')
 @a.protected(True)
 def financial_config_save():
  b=request.get_json(silent=True)
  if not isinstance(b,dict) or not isinstance(b.get('key'),str):abort(400)
  key=b['key'].strip()
  if key and not re.fullmatch(r'[A-Za-z0-9]{40}',key):return jsonify(error='DART 인증키 40자리를 입력하세요.'),400
  if not guard.acquire(blocking=False):return jsonify(error='실적 수집 중에는 인증키를 변경할 수 없습니다.'),409
  try:
   saved=config()
   if key:saved['key']=key
   temp=config_path.with_suffix('.tmp')
   try:
    with open(temp,'w',encoding='utf-8',opener=lambda path,flags:os.open(path,flags,0o600)) as f:json.dump(saved,f)
    os.replace(temp,config_path)
   finally:temp.unlink(missing_ok=True)
  finally:guard.release()
  return jsonify(ok=True)
 @a.app.get('/api/financials')
 @a.protected()
 def financial_list():
  company,fs,start,end,mode,quarter=selection(request.args)
  with a.db() as c:
   records=[dict(r) for r in c.execute('SELECT * FROM financial_reports WHERE company=? AND fs=? AND year BETWEEN ? AND ?',(company,fs,max(2015,start-1),end))]
   resolved=c.execute('SELECT corp_code,corp_name FROM dart_companies WHERE company=?',(company,)).fetchone()
  for r in records:r['data']=json.loads(r['data'])
  return jsonify(companies=[dict(id=x[0],name=x[1]) for x in COMPANIES],rows=build_rows(records,start,end,mode,quarter),job=snapshot(),company=company,fs=fs,start=start,end=end,mode=mode,quarter=quarter,resolved=dict(resolved) if resolved else None)
 def worker(company,fs,start,end,key,actor,both_fs=False):
  try:
   with a.db() as c:resolved=c.execute('SELECT corp_code FROM dart_companies WHERE company=?',(company,)).fetchone()
   if not resolved:
    master=resolve_companies(dart_bytes('corpCode.xml',key))
    with a.db() as c:
     for cid,row in master.items():c.execute('INSERT OR REPLACE INTO dart_companies VALUES(?,?,?,?,?)',(cid,row['corp_code'],row['corp_name'],row['stock_code'],a.stamp()))
    if company not in master:raise DartError('DART 기업목록에서 회사를 유일하게 찾지 못했습니다. 회사명/분할 여부를 확인하세요.')
    corp=master[company]['corp_code']
   else:corp=resolved['corp_code']
   periods=[(y,q) for y in range(start,end+1) for q in range(1,5)]
   if start>2015:periods=[(start-1,q) for q in range(1,5)]+periods
   today=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
   periods=[(y,q) for y,q in periods if dt.date(y,q*3,1)<=today]
   requests=[(year,q,basis) for basis in (('CFS','OFS') if both_fs else (fs,)) for year,q in periods]
   with job_guard:job['total']=len(requests)
   for year,q,basis in requests:
    rows=dart_report(key,corp,year,q,basis);data=extract(rows,q) if rows else dict(metrics={},warnings=[],receipts=[])
    with a.db() as c:c.execute('INSERT OR REPLACE INTO financial_reports VALUES(?,?,?,?,?,?,?,?)',(company,corp,year,q,basis,'available' if rows else 'no_data',json.dumps(data,ensure_ascii=False),a.stamp()))
    with job_guard:job['done']+=1
   with a.db() as c:c.execute('INSERT INTO audit(time,actor,action,doc) VALUES(?,?,?,?)',(a.stamp(),actor,'기업실적 DART 수집 '+company+' '+str(start)+'~'+str(end)+' '+('CFS+OFS' if both_fs else fs),''))
  except DartError as exc:
   with job_guard:job['error']=str(exc)
  except Exception:
   with job_guard:job['error']='기업실적을 처리하지 못했습니다. 기존 저장 자료는 유지됩니다.'
  finally:
   with job_guard:job['running']=False
   guard.release()
 @a.app.post('/api/financials/fetch')
 @a.protected(True)
 def financial_fetch():
  b=request.get_json(silent=True)
  if not isinstance(b,dict):abort(400)
  company,fs,start,end,_,_=selection(b)
  if type(b.get('both_fs',False)) is not bool:abort(400)
  if not guard.acquire(blocking=False):return jsonify(error='이미 기업실적을 수집 중입니다.'),409
  try:
   key=config().get('key')
   if not key:guard.release();return jsonify(error='DART 설정에서 인증키를 먼저 저장하세요.'),400
   with job_guard:job.update(running=True,done=0,total=0,error='',company=company)
   thread=threading.Thread(target=worker,args=(company,fs,start,end,key,session.get('user','admin'),b.get('both_fs',False)),daemon=True,name='dart-financials');thread.start()
  except Exception:
   guard.release();raise
  return jsonify(ok=True)
 a.financial_job=snapshot
