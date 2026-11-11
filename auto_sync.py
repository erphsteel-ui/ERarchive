"""Administrator review queue counts."""
from flask import jsonify

def install(a):
 @a.app.get('/api/admin/status')
 @a.protected(True)
 def status():
  with a.db() as c:
   counts={'schedule':c.execute("SELECT COUNT(*) FROM schedule_events e WHERE e.state='pending' AND (e.source IS NULL OR EXISTS (SELECT 1 FROM schedule_sources s WHERE s.id=e.source AND (s.kind='hwp' OR EXISTS (SELECT 1 FROM schedule_jobs j WHERE s.id=j.kind||':'||j.hash))))").fetchone()[0],
    'batches':c.execute("SELECT COUNT(*) FROM batches WHERE state IN ('queued','processing','review')").fetchone()[0],
    'drafts':c.execute("SELECT COUNT(*) FROM documents WHERE json_extract(meta,'$.state')='draft'").fetchone()[0]}
  return jsonify(counts=counts)
