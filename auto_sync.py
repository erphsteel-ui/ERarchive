"""Background news synchronization and administrator queue status."""
import datetime as dt,json,threading,time
from flask import jsonify
KST=dt.timezone(dt.timedelta(hours=9))
SCHEDULE={(8,30),(11,30),(14,30),(16,30)}

def install(a):
 lock=threading.Lock();state={'running':False,'last_attempt':'','last_result':'','error':''}
 def last_success():
  with a.db() as c:row=c.execute("SELECT value FROM settings WHERE key='last_news_sync_at'").fetchone()
  return row[0] if row else ''
 def start(manual=False):
  if not lock.acquire(blocking=False):return False,'이미 통합 수집이 진행 중입니다.'
  try:
   last=last_success();now=dt.datetime.now(dt.timezone.utc)
   if not manual and last:
    try:recent=0<=(now-dt.datetime.fromisoformat(last)).total_seconds()<3600
    except (ValueError,TypeError):recent=False
    if recent:lock.release();return False,'최근 60분 이내에 수집했습니다.'
   state.update(running=True,last_attempt=now.isoformat(),last_result='진행 중',error='')
   def worker():
    try:
     errors=[]
     try:
      result,status=a.collect_news()
      if status!=200:errors.append(result.get('error','뉴스 수집 실패'))
     except Exception:
      a.app.logger.exception('Automatic news collection failed');errors.append('뉴스 수집 오류 · 서버 실행 창을 확인하세요.')
     try:
      result=a.collect_steel_press()
      if not result.get('ok'):errors.append(result.get('error','전문지 수집 실패'))
     except Exception:
      a.app.logger.exception('Automatic steel press collection failed');errors.append('전문지 수집 오류 · 서버 실행 창을 확인하세요.')
     if errors:state.update(last_result='일부 실패',error=' · '.join(errors))
     else:
      done=dt.datetime.now(dt.timezone.utc).isoformat()
      with a.db() as c:
       c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('last_news_sync_at',?)",(done,))
       if not manual:c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('last_auto_news_sync_at',?)",(done,))
      state.update(last_result='완료',error='')
    except Exception:
     a.app.logger.exception('News synchronization failed');state.update(last_result='실패',error='통합 수집 상태 저장 오류 · 서버 실행 창을 확인하세요.')
    finally:state['running']=False;lock.release()
   threading.Thread(target=worker,daemon=True,name='news-sync').start();return True,'통합 수집을 시작했습니다.'
  except Exception:
   state['running']=False;lock.release();raise
 def scheduler():
  start()
  last_slot=None
  while True:
   now=dt.datetime.now(KST);slot=(now.date(),now.hour,now.minute)
   if now.weekday()<5 and (now.hour,now.minute) in SCHEDULE and slot!=last_slot:
    last_slot=slot;start()
   time.sleep(20)
 a.start_news_sync=start
 def start_scheduler():threading.Thread(target=scheduler,daemon=True,name='news-sync-scheduler').start()
 @a.app.post('/api/admin/sync')
 @a.protected(True)
 def sync():
  started,message=start(manual=True);return jsonify(started=started,message=message)
 @a.app.get('/api/admin/status')
 @a.protected(True)
 def status():
  with a.db() as c:
   counts={'schedule':c.execute("SELECT COUNT(*) FROM schedule_events WHERE state='pending'").fetchone()[0],
    'batches':c.execute("SELECT COUNT(*) FROM batches WHERE state IN ('queued','processing','review')").fetchone()[0],
    'drafts':c.execute("SELECT COUNT(*) FROM documents WHERE json_extract(meta,'$.state')='draft'").fetchone()[0],
    'precision':c.execute("SELECT COUNT(*) FROM precision_jobs WHERE state IN ('queued','running','done','failed')").fetchone()[0]}
   auto=c.execute("SELECT value FROM settings WHERE key='last_auto_news_sync_at'").fetchone()
  return jsonify(counts=counts,sync={**state,'last_success':last_success(),'last_auto_success':auto[0] if auto else ''})
 return start_scheduler
