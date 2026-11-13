"""End-to-end checks for non-destructive schedule import."""
import os, subprocess, sys, tempfile, textwrap, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
class ScheduleImportTests(unittest.TestCase):
 def test_preview_and_import(self):
  with tempfile.TemporaryDirectory() as folder:
   env=os.environ.copy();env.pop('ERARCHIVE_REQUIRE_VOLUME',None);env['ERARCHIVE_DATA_DIR']=folder
   code=textwrap.dedent('''
    import io,json,sqlite3,tempfile
    from pathlib import Path
    from werkzeug.security import generate_password_hash
    import app
    from schedule_import import build_plan
    with app.db() as c:
     c.execute('INSERT INTO users VALUES(?,?,?)',('admin',generate_password_hash('admin-password-123'),'admin'))
     c.execute('INSERT INTO users VALUES(?,?,?)',('reader',generate_password_hash('reader-password-123'),'viewer'))
     rows=json.loads(c.execute("SELECT value FROM settings WHERE key='schedule_rows'").fetchone()[0])
     c.execute('INSERT INTO schedule_events VALUES(?,NULL,NULL,?,?,1,?,?)',('existing',json.dumps({'title':'보존','start':'2026-11-01','end':'2026-11-01','row':rows[0]['id']}),'published','now','now'))
    with tempfile.TemporaryDirectory() as tmp:
     path=Path(tmp)/'archive.db'
     con=sqlite3.connect(path)
     con.executescript('CREATE TABLE settings(key TEXT,value TEXT);CREATE TABLE schedule_events(id TEXT,data TEXT,state TEXT);')
     source_rows=[{'id':'old-a','group':rows[0]['group'],'name':rows[0]['name']},{'id':'old-b','group':'새 조직','name':'신규'}]
     con.execute('INSERT INTO settings VALUES(?,?)',('schedule_rows',json.dumps(source_rows,ensure_ascii=False)))
     def add(i,title,row,state='published',start='2026-11-11'):
      con.execute('INSERT INTO schedule_events VALUES(?,?,?)',(i,json.dumps({'title':title,'start':start,'end':start,'row':row,'time':'13:00'},ensure_ascii=False),state))
     add('existing','변경하면 안됨','old-a');add('one','회의','old-a');add('two','행사','old-b');add('unknown','알 수 없음','missing');add('bad','잘못된 날짜','old-a',start='bad');add('draft','비공개','old-a','pending');con.commit();con.close();blob=path.read_bytes()
     admin=app.app.test_client();reader=app.app.test_client();guest=app.app.test_client()
     ah={'X-CSRF':admin.post('/api/login',json={'name':'admin','password':'admin-password-123'}).json['csrf']}
     rh={'X-CSRF':reader.post('/api/login',json={'name':'reader','password':'reader-password-123'}).json['csrf']}
     def upload(client,action,headers,content=blob,extra=None):
      data={'files':(io.BytesIO(content),'archive.db')};data.update(extra or {})
      return client.post('/api/schedule/import/'+action,data=data,headers=headers,content_type='multipart/form-data')
     assert upload(guest,'preview',{}).status_code==401
     assert upload(reader,'preview',rh).status_code==403
     assert upload(admin,'preview',{}).status_code==403
     assert upload(admin,'preview',ah,b'invalid').status_code==400
     r=upload(admin,'preview',ah);assert r.status_code==200,r.data
     v=r.json;assert (v['total'],v['count'],v['duplicates'],v['skipped'])==(5,2,1,2),v
     assert [i['title'] for i in v['items']]==['회의','행사'];assert len(v['new_rows'])==1
     with app.db() as c:
      assert c.execute('SELECT COUNT(*) FROM schedule_events').fetchone()[0]==1
      assert len(json.loads(c.execute("SELECT value FROM settings WHERE key='schedule_rows'").fetchone()[0]))==len(rows)
     assert upload(admin,'commit',ah,extra={'digest':'bad','plan':v['plan']}).status_code==400
     assert upload(admin,'commit',ah,extra={'digest':v['digest'],'plan':'bad'}).status_code==409
     done=upload(admin,'commit',ah,extra={'digest':v['digest'],'plan':v['plan']});assert done.status_code==200,done.data
     assert done.json['count']==2
     with app.db() as c:
      assert c.execute('SELECT COUNT(*) FROM users').fetchone()[0]==2
      events=c.execute('SELECT id,data FROM schedule_events').fetchall();assert len(events)==3
      saved={r['id']:json.loads(r['data']) for r in events}
      assert saved['existing']['title']=='보존' and saved['one']['time']=='13:00'
      mapped=json.loads(c.execute("SELECT value FROM settings WHERE key='schedule_rows'").fetchone()[0]);assert any(x['name']=='신규' and x['id']==saved['two']['row'] for x in mapped)
     r=upload(admin,'preview',ah);assert r.json['count']==0 and r.json['duplicates']==3,r.json
     # A live WAL backup remains readable when all three files are supplied.
     walpath=Path(tmp)/'wal'/'archive.db';walpath.parent.mkdir()
     con=sqlite3.connect(walpath);con.execute('PRAGMA journal_mode=WAL');con.executescript('CREATE TABLE settings(key TEXT,value TEXT);CREATE TABLE schedule_events(id TEXT,data TEXT,state TEXT);')
     con.execute('INSERT INTO settings VALUES(?,?)',('schedule_rows',json.dumps(source_rows,ensure_ascii=False)))
     con.execute('INSERT INTO schedule_events VALUES(?,?,?)',('wal-event',json.dumps({'title':'WAL 일정','start':'2026-11-11','end':'2026-11-11','row':'old-a'},ensure_ascii=False),'published'));con.commit()
     data={'files':[(io.BytesIO(Path(str(walpath)+suffix).read_bytes()),'archive.db'+suffix) for suffix in ('','-wal','-shm')]}
     r=admin.post('/api/schedule/import/preview',data=data,headers=ah,content_type='multipart/form-data');assert r.status_code==200,r.data
     assert r.json['count']==1 and r.json['items'][0]['title']=='WAL 일정',r.json;con.close()
   ''')
   result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=env,text=True,capture_output=True)
   self.assertEqual(result.returncode,0,result.stderr)
if __name__=='__main__':unittest.main()
