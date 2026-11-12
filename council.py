"""Labor-management council search and administrator clipboard import."""
import csv, io, hashlib, json, re
from flask import request, jsonify, abort

FIELDS=('year','quarter','category','title','request','unit','result','details')
LABELS=('연도','분기','안건분류','안건명','요구사항','협의단위','결과구분','협의결과 상세')

TEXT_FIELDS=('title','request','details')
CORRECTIONS={
 '분양요':'분양 요구','본읜의사':'본인 의사','고렿여':'고려하여','하기휴야':'하기휴양소',
 '발상시':'발생 시','자동호파':'자동호퍼','주치하고':'조치하고','손에 뭍은':'손에 묻은',
 '센스개선':'센서 개선','센스 보강':'센서 보강','센스 개선':'센서 개선','식당이부':'식당 일부',
 '목욕탕 샴푸 비치 거':'목욕탕 샴푸 비치 건','사내 세차장 설치의 선':'사내 세차장 설치의 건',
 '차랑출입증':'차량출입증','소취하사자':'소취하자','세차 비용 지금':'세차 비용 지급',
 '실태 패악':'실태 파악','시전 조율':'사전 조율','혹서비 대비':'혹서기 대비',
 '해수용장':'해수욕장','형상간':'형산강'
}
def sanitizeAgendaText(value):
 text=str(value or '').replace('\r\n','\n').replace('\r','\n').replace('\u00a0',' ').replace('\v',' ')
 text=re.sub(r'[\x00-\x08\x0e-\x1f\x7f]', '', text)
 for old,new in (('간\n소화','간소화'),('사\n내','사내'),('본\n발급','본 발급')):text=text.replace(old,new)
 text=re.sub(r'->|=>|⇒','→',text)
 text=re.sub(r'(\d)名',r'\1명',text);text=re.sub(r'(\d)月',r'\1월',text);text=re.sub(r'(\d)年',r'\1년',text)
 text=re.sub(r'(?<=\S)內',' 내',text).replace('旣','기')
 for old,new in sorted(CORRECTIONS.items(),key=lambda x:-len(x[0])):
  if old=='분양요':text=re.sub(r'분양요(?![가-힣])',new,text)
  else:text=text.replace(old,new)
 lines=[]
 for line in text.split('\n'):
  line=re.sub(r'[ \t]+',' ',line).strip()
  if re.match(r'^[○ㅇㅁ□■]',line):line='• '+re.sub(r'^[○ㅇㅁ□■]\s*','',line)
  elif re.match(r'^-(?=\s|[가-힣]|$)',line) or re.match(r'^[ㆍ·]',line):line='  - '+re.sub(r'^[-ㆍ·]\s*','',line)
  lines.append(line.rstrip())
 return '\n'.join(lines).strip('\n')

def normalize_item(item):
 return {key:sanitizeAgendaText(item[key]) if key in TEXT_FIELDS else (item[key] or '') for key in FIELDS}

def item_key(item):
 return hashlib.sha256(json.dumps(normalize_item(item),ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def parse_paste(text):
 if not isinstance(text,str) or len(text)>5_000_000:raise ValueError('붙여넣기 내용은 500만 자 이하여야 합니다.')
 try: rows=list(csv.reader(io.StringIO(text, newline=''),delimiter='\t',strict=True))
 except csv.Error:raise ValueError('복사한 셀의 따옴표 형식을 확인해 주세요.')
 rows=[r for r in rows if any(v.strip() for v in r)]
 if not rows:raise ValueError('엑셀 데이터를 붙여넣어 주세요.')
 first=[v.strip().replace(' ','') for v in rows[0]]
 aliases={'year':['연도','개최연도'],'quarter':['분기'],'category':['안건분류','분류'],'title':['안건명'],'request':['요구사항'],'unit':['협의단위'],'result':['결과구분','협의결과'],'details':['협의결과상세','상세내용']}
 if '안건명' in first:
  indices={k:next((i for i,x in enumerate(first) if x in aliases[k]),None) for k in FIELDS}
  if any(v is None for v in indices.values()):raise ValueError('머리글에서 연도, 분기, 안건분류, 안건명, 요구사항, 협의단위, 결과구분, 협의결과 상세를 확인해 주세요.')
  rows=rows[1:]
 else:
  # 02_Data B:I, or A:I including the leading automatic number.
  offset=1 if len(rows[0])>=9 and rows[0][0].strip().isdigit() and len(rows[0][1].strip())==4 else 0
  indices={key:i+offset for i,key in enumerate(FIELDS)}
 if not rows:raise ValueError('머리글 아래 데이터가 없습니다.')
 if len(rows)>5000:raise ValueError('한 번에 5,000행까지 등록할 수 있습니다.')
 result=[]
 for i,row in enumerate(rows,1):
  if len(row)<=max(indices.values()):raise ValueError(f'{i}번째 데이터 행에 필요한 열이 부족합니다. B:I 또는 A:I를 다시 복사해 주세요.')
  item=normalize_item({key:row[idx].strip() for key,idx in indices.items()})
  if not item['title'] or not item['year'].isdigit() or not 1900<=int(item['year'])<=2100:raise ValueError(f'{i}번째 데이터 행의 연도와 안건명을 확인해 주세요.')
  if any(len(v)>20000 for v in item.values()):raise ValueError(f'{i}번째 데이터 행의 값이 너무 깁니다.')
  result.append(item)
 return result

def install(a):
 with a.db() as c:
  c.execute('CREATE TABLE IF NOT EXISTS council_items (id TEXT PRIMARY KEY,year TEXT,quarter TEXT,category TEXT,title TEXT,request TEXT,unit TEXT,result TEXT,details TEXT,created TEXT)')
 @a.app.post('/api/council/import')
 @a.protected(True)
 def council_import_items():
  payload=request.get_json(silent=True) or {}
  try: items=parse_paste(payload.get('text'))
  except ValueError as e:return jsonify(error=str(e)),400
  unique={item_key(item):item for item in items}
  with a.db() as c:
   existing={item_key(dict(r)) for r in c.execute('SELECT year,quarter,category,title,request,unit,result,details FROM council_items')}; new=[(key,item) for key,item in unique.items() if key not in existing]
   if payload.get('save') is True:
    for key,item in new:c.execute('INSERT OR IGNORE INTO council_items (id,year,quarter,category,title,request,unit,result,details,created) VALUES(?,?,?,?,?,?,?,?,?,?)',(key,*(item[k] for k in FIELDS),a.stamp()))
    if new:a.log(c,'노사협의회 자료 등록')
  return jsonify(total=len(items),new=len(new),duplicates=len(items)-len(new),preview=items[:10],saved=payload.get('save') is True)
 @a.app.get('/api/council')
 @a.protected()
 def council_listing():
  filters={key:request.args.get(key,'').strip() for key in ('year','quarter','category','unit','result')};terms=[request.args.get(k,'').strip().casefold() for k in ('q','q2')]
  try:offset=int(request.args.get('offset','0'))
  except ValueError:abort(400)
  if offset<0 or any(len(x)>200 for x in terms) or any(len(v)>100 for v in filters.values()):abort(400)
  with a.db() as c:rows=[dict(r) for r in c.execute('SELECT id,year,quarter,category,title,request,unit,result,details,created FROM council_items ORDER BY year DESC,quarter DESC,created DESC,id')]
  rows=[{**r,**normalize_item(r)} for r in rows]
  options={k:sorted({r[k] for r in rows if r[k]},reverse=k=='year') for k in filters}
  found=[r for r in rows if all(not v or r[k]==v for k,v in filters.items()) and all(not term or term in ' '.join(r[k] for k in FIELDS).casefold() for term in terms)]
  return jsonify(items=found[offset:offset+100],total=len(found),offset=offset,options=options)
