"""Separate occasion notices; old records remain readable and editable."""
import datetime as dt,secrets
from flask import abort,jsonify,request

def install(a):
 with a.db() as c:
  c.execute('CREATE TABLE IF NOT EXISTS occasion_notices(id TEXT PRIMARY KEY,title TEXT NOT NULL,kind TEXT NOT NULL,event_date TEXT NOT NULL,note TEXT NOT NULL,version INTEGER NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL)')
  existing={r[1] for r in c.execute('PRAGMA table_info(occasion_notices)')}
  for name in ('sub_type','target_name','relation','location'):
   if name not in existing:c.execute('ALTER TABLE occasion_notices ADD COLUMN '+name+" TEXT NOT NULL DEFAULT ''")
 def serialize(row):
  d=dict(row);d.update(category=d['kind'],subType=d['sub_type'],targetName=d['target_name'],date=d['event_date'],content=d['note']);return d
 @a.app.get('/api/occasions')
 @a.protected()
 def occasions_list():
  period=request.args.get('period','upcoming')
  if period not in ('upcoming','past'):abort(400)
  today=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
  sql='SELECT * FROM occasion_notices WHERE event_date '+('>=? ORDER BY event_date ASC,created ASC,id' if period=='upcoming' else '<? ORDER BY event_date DESC,created DESC,id')
  with a.db() as c:items=[serialize(r) for r in c.execute(sql,(today,))]
  return jsonify(items=items)
 @a.app.post('/api/occasions/save')
 @a.protected(True)
 def occasions_save():
  b=request.get_json(silent=True)
  if not isinstance(b,dict):abort(400)
  ident=b.get('id');version=b.get('version')
  if ident is not None and (not isinstance(ident,str) or type(version) is not int):abort(400)
  with a.db() as c:
   c.execute('BEGIN IMMEDIATE');now=a.stamp();old=None
   if ident:
    old=c.execute('SELECT * FROM occasion_notices WHERE id=?',(ident,)).fetchone()
    if not old:abort(404)
    if old['version']!=version:abort(409)
   def value(new,legacy,default=''):
    return b.get(new,b.get(legacy,old[legacy] if old is not None and legacy in old.keys() else default))
   title=value('title','title');kind=value('category','kind');date=value('date','event_date');content=value('content','note')
   subtype=value('subType','sub_type');target=value('targetName','target_name');relation=value('relation','relation');location=value('location','location')
   for v,limit in ((title,100),(content,10000),(subtype,100),(target,100),(relation,100),(location,300)):
    if not isinstance(v,str) or len(v)>limit:abort(400)
   if kind not in ('경사','조사','기타') or not isinstance(date,str):abort(400)
   title=title.strip() or ' '.join(x for x in (target.strip(),relation.strip()+subtype.strip()) if x)
   if not title or len(title)>100:return jsonify(error='대상자 또는 제목을 입력하세요.'),400
   try:
    parsed=dt.date.fromisoformat(date)
    if parsed.isoformat()!=date:raise ValueError()
   except ValueError:return jsonify(error='날짜를 확인하세요.'),400
   values=(title,kind,date,content,subtype.strip(),target.strip(),relation.strip(),location.strip())
   if ident:c.execute('UPDATE occasion_notices SET title=?,kind=?,event_date=?,note=?,sub_type=?,target_name=?,relation=?,location=?,version=version+1,updated=? WHERE id=?',values+(now,ident))
   else:
    ident=secrets.token_hex(12);c.execute('INSERT INTO occasion_notices(id,title,kind,event_date,note,sub_type,target_name,relation,location,version,created,updated) VALUES(?,?,?,?,?,?,?,?,?,1,?,?)',(ident,)+values+(now,now))
   a.log(c,'경조사 저장',ident)
  return jsonify(ok=True,id=ident)
 @a.app.post('/api/occasions/delete')
 @a.protected(True)
 def occasions_delete():
  b=request.get_json(silent=True)
  if not isinstance(b,dict) or not isinstance(b.get('id'),str) or type(b.get('version')) is not int:abort(400)
  with a.db() as c:
   c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT version FROM occasion_notices WHERE id=?',(b['id'],)).fetchone()
   if not row:abort(404)
   if row['version']!=b['version']:abort(409)
   c.execute('DELETE FROM occasion_notices WHERE id=?',(b['id'],));a.log(c,'경조사 삭제',b['id'])
  return jsonify(ok=True)
