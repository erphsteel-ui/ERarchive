from app import ROOT,DATA,db,stamp
import json,secrets,hashlib,shutil
count=0
for d in json.loads((ROOT/'examples.json').read_text(encoding='utf-8')):
 paths=[ROOT/'examples'/f for f in d['files']]
 if not all(p.exists() for p in paths):continue
 hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
 with db() as c:
  if any(c.execute('SELECT 1 FROM pages WHERE hash=?',(h,)).fetchone() for h in hashes):continue
  did=secrets.token_hex(12);c.execute('INSERT INTO documents VALUES(?,?,?,?,1)',(did,json.dumps(d['meta'],ensure_ascii=False),stamp(),stamp()))
  for i,(p,h) in enumerate(zip(paths,hashes)):
   pid=secrets.token_hex(12);name=pid+p.suffix;shutil.copyfile(p,DATA/'images'/name)
   c.execute('INSERT INTO pages VALUES(?,?,?,?,?,?,?)',(pid,did,name,h,'','手動 예시 · 본문 OCR 미실행'.replace('手動','수동'),i))
  c.execute('INSERT INTO audit(time,actor,action,doc) VALUES(?,?,?,?)',(stamp(),'CLI','수동 예시 가져오기',did));count+=1
print(f'Imported {count} example documents as drafts.')
