"""Separate notices for occasions; they never occupy calendar rows."""
import datetime as dt,secrets
from flask import abort,jsonify,request

def install(a):
 with a.db() as c:
  c.execute('CREATE TABLE IF NOT EXISTS occasion_notices(id TEXT PRIMARY KEY,title TEXT NOT NULL,kind TEXT NOT NULL,event_date TEXT NOT NULL,note TEXT NOT NULL,version INTEGER NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL)')
 @a.app.get('/api/occasions')
 @a.protected()
 def occasions_list():
  today=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
  with a.db() as c:items=[dict(r) for r in c.execute('SELECT * FROM occasion_notices WHERE event_date>=? ORDER BY event_date,created,id',(today,))]
  return jsonify(items=items)
 @a.app.post('/api/occasions/save')
 @a.protected(True)
 def occasions_save():
  b=request.get_json(silent=True)
  if not isinstance(b,dict) or not isinstance(b.get('title'),str) or not 1<=len(b['title'].strip())<=100 or b.get('kind') not in ('경사','조사','기타') or not isinstance(b.get('note',''),str) or len(b.get('note',''))>2000 or not isinstance(b.get('date'),str):abort(400)
  try:
   date=dt.date.fromisoformat(b['date'])
   if date.isoformat()!=b['date']:raise ValueError()
  except ValueError:return jsonify(error='날짜를 확인하세요.'),400
  ident=b.get('id');version=b.get('version')
  if ident is not None and (not isinstance(ident,str) or type(version) is not int):abort(400)
  with a.db() as c:
   c.execute('BEGIN IMMEDIATE');now=a.stamp()
   if ident:
    row=c.execute('SELECT version FROM occasion_notices WHERE id=?',(ident,)).fetchone()
    if not row:abort(404)
    if row['version']!=version:abort(409)
    c.execute('UPDATE occasion_notices SET title=?,kind=?,event_date=?,note=?,version=version+1,updated=? WHERE id=?',(b['title'].strip(),b['kind'],b['date'],b.get('note',''),now,ident))
   else:
    ident=secrets.token_hex(12);c.execute('INSERT INTO occasion_notices VALUES(?,?,?,?,?,1,?,?)',(ident,b['title'].strip(),b['kind'],b['date'],b.get('note',''),now,now))
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
