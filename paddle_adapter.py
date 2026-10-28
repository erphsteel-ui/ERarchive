"""Run the user's isolated, locally installed PaddleOCR CLI without shell or downloads."""
import json,os,subprocess,tempfile,threading,queue,atexit
from pathlib import Path
from PIL import Image,ImageOps
_LOCK=threading.RLock()
_PROCESS=None
_REPLIES=None
_PROCESS_KEY=None
def stop_worker():
    with _LOCK:
        global _PROCESS
        if _PROCESS is not None:
            if _PROCESS.poll() is None:
                _PROCESS.kill()
            _PROCESS.wait()
            for stream in (_PROCESS.stdin,_PROCESS.stdout):
                if stream:stream.close()
            _PROCESS=None
atexit.register(stop_worker)
def worker_request(image,out,home,exe,det,rec):
    with _LOCK:
        global _PROCESS,_REPLIES,_PROCESS_KEY
        key=tuple(map(str,(home,exe,det,rec)))
        if _PROCESS is None or _PROCESS.poll() is not None or key!=_PROCESS_KEY:
            stop_worker(); replies=queue.Queue();_REPLIES=replies;_PROCESS_KEY=key
            _PROCESS=subprocess.Popen([str(exe),str(Path(__file__).with_name('paddle_worker.py')),str(det),str(rec)],
                cwd=str(home),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                text=True,encoding='utf-8',errors='replace',bufsize=1,
                env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8','PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK':'True'},
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            proc=_PROCESS
            def read():
                try:
                    for line in proc.stdout:
                        if line.startswith('ER_RESULT '):replies.put(line[10:])
                finally:replies.put(None)
            threading.Thread(target=read,daemon=True).start()
        try:
            _PROCESS.stdin.write(json.dumps({'image':str(image),'output':str(out)})+'\n');_PROCESS.stdin.flush()
            response=_REPLIES.get(timeout=300)
            if response is None:raise OSError('OCR 프로세스가 종료되었습니다. 다시 시도해 주세요.')
            response=json.loads(response)
            if not response.get('ok'):raise OSError(response.get('error','OCR 오류'))
            return response
        except queue.Empty:
            stop_worker();raise subprocess.TimeoutExpired('PaddleOCR',300)
        except (OSError,ValueError):
            stop_worker();raise
def paths():
    home=Path(os.environ.get('PADDLE_OCR_HOME',str(Path.home()/'PaddleOCR')))
    exe=Path(os.environ.get('PADDLE_OCR_PYTHON',str(home/'.venv'/'Scripts'/'python.exe')))
    return home,exe,home/'models'/'det',home/'models'/'rec'
def status():
    home,exe,det,rec=paths()
    missing=[str(p) for p in (exe,det/'inference.yml',rec/'inference.yml',det/'inference.json',rec/'inference.json',det/'inference.pdiparams',rec/'inference.pdiparams') if not p.is_file()]
    return {'ready':not missing,'home':str(home),'missing':missing}
def parse_result(data,width,height):
    data=data.get('res',data);texts=data.get('rec_texts',[]);scores=data.get('rec_scores',[]);boxes=data.get('rec_boxes',[])
    if not (len(texts)==len(scores)==len(boxes)):raise ValueError('PaddleOCR 결과 구조 확인 필요')
    lines=[]
    for text,score,box in zip(texts,scores,boxes):
        if not isinstance(text,str) or not text.strip():continue
        x1,y1,x2,y2=map(float,box)
        x1=max(0,min(width,x1));x2=max(x1,min(width,x2));y1=max(0,min(height,y1));y2=max(y1,min(height,y2))
        lines.append({'text':text.strip(),'confidence':round(float(score)*100,1),'box':[x1/width,y1/height,(x2-x1)/width,(y2-y1)/height]})
    return lines

def regions(lines):
    # Restrict metadata evidence to the masthead and footer, not body mentions.
    top=[l for l in lines if l['box'][1]<.25]
    title=[l for l in top if l['box'][1]<.14 and l['box'][0]+l['box'][2]/2>.17 and l['box'][0]+l['box'][2]/2<.83]
    issuer=[l for l in top if l['box'][1]<.15 and l['box'][0]+l['box'][2]/2<.25]
    footer=[l for l in lines if l['box'][1]>.88 and any(t in l['text'] for t in ('노조','노동조합','지부','지회'))]
    return {'header':'\n'.join(l['text'] for l in top+footer),'title':' '.join(l['text'] for l in title),'issuer':'\n'.join(l['text'] for l in issuer+footer)}

def recognize(path,layout='auto'):
    from ocr_engine import as_candidate
    result={'engine':'paddle','raw':'','variants':[],'selected':0,'regions':{},'status':'PaddleOCR 준비 중'}
    if not status()['ready']:
        result['status']='PaddleOCR 설치 또는 모델 경로 확인 필요 · 06_check_paddle.bat 실행';return result
    home,exe,det,rec=paths()
    try:
        with _LOCK, tempfile.TemporaryDirectory(prefix='er-paddle-') as tmp:
            tmp=Path(tmp)
            with Image.open(path) as source:im=ImageOps.exif_transpose(source).convert('RGB')
            image=tmp/'page.png';im.save(image);out=tmp/'result';out.mkdir()
            result['timing']=worker_request(image,out,home,exe,det,rec)
            files=list(out.glob('*.json'))
            if len(files)!=1:raise ValueError('인식 결과 JSON이 없습니다')
            data=json.loads(files[0].read_text(encoding='utf-8-sig'))
            lines=parse_result(data,im.width,im.height);result['regions']=regions(lines)
            raw='\n'.join(l['text'] for l in lines);result['raw']=raw
            def candidate(name,items):
                c=as_candidate(name,[{'text':l['text'],'words':[l]} for l in items]);c.pop('lines',None);return c
            result['variants']=[candidate('PaddleOCR · 원본 인식',lines)] if lines else []
            if layout=='columns' and lines:
                # Reorder only: preserve full-width heading and footer, never cut words/images.
                head=[l for l in lines if l['box'][1]<.25];foot=[l for l in lines if l['box'][1]>.9]
                body=[l for l in lines if .25<=l['box'][1]<=.9]
                if any(l['box'][0]<.45 and l['box'][0]+l['box'][2]>.55 for l in body):
                    result['status']='PaddleOCR 완료 · 중앙을 가로지르는 본문이 있어 원래 읽기 순서 유지'
                else:
                    left=[l for l in body if l['box'][0]+l['box'][2]/2<.5];right=[l for l in body if l not in left]
                    result['variants'].append(candidate('PaddleOCR · 왼쪽 단 다음 오른쪽 단',head+left+right+foot));result['selected']=1
            if result['status']=='PaddleOCR 준비 중':result['status']='PaddleOCR 완료 · 원본과 비교해 확인' if lines else 'PaddleOCR 완료 · 인식된 글자 없음'
    except subprocess.TimeoutExpired:result['status']='PaddleOCR 5분 초과 · 원본은 유지하며 직접 입력 가능'
    except (OSError,ValueError,KeyError,TypeError) as e:result['status']='PaddleOCR 처리 실패 · '+str(e)[:250]
    return result

if __name__=='__main__':
    s=status();print('PaddleOCR folder:',s['home']);print('Ready' if s['ready'] else 'Missing files:')
    for p in s['missing']:print(p)
    raise SystemExit(0 if s['ready'] else 1)
