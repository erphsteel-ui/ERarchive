"""Isolated local VL runtime; release v5 memory before CPU VL processing."""
import json,os,subprocess,tempfile,time
from pathlib import Path
from html.parser import HTMLParser
import paddle_adapter
from PIL import Image,ImageOps

def paths():
    home=Path(os.environ.get('PADDLE_VL_HOME',str(Path.home()/'PaddleOCR-VL')))
    exe=Path(os.environ.get('PADDLE_VL_PYTHON',str(home/'.venv'/'Scripts'/'python.exe')))
    cache=Path.home()/'.paddlex'/'official_models'
    layout=Path(os.environ.get('PADDLE_VL_LAYOUT',str(cache/'PP-DocLayoutV3')))
    default_vl=next((p for p in (cache/'PaddleOCR-VL-1.6',cache/'PaddleOCR-VL-1.6-0.9B') if (p/'config.json').is_file()),cache/'PaddleOCR-VL-1.6')
    vl=Path(os.environ.get('PADDLE_VL_MODEL',str(default_vl)))
    return home,exe,layout,vl

def status():
    home,exe,layout,vl=paths();missing=[]
    if not exe.is_file():missing.append(str(exe))
    if not (layout/'inference.yml').is_file() or not (layout/'inference.pdiparams').is_file():missing.append(str(layout))
    if not (vl/'config.json').is_file() or not any(vl.glob('*.safetensors')):missing.append(str(vl))
    return dict(ready=not missing,missing=missing,python=str(exe),layout=str(layout),model=str(vl))

class PlainHTML(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th'):self.parts.append(' | ')
        elif tag in ('tr','p','div'):self.parts.append('\n')
    def handle_starttag(self,tag,attrs):
        if tag=='br':self.parts.append('\n')

def parse_result(data):
    data=data.get('res',data);blocks=data.get('parsing_res_list')
    if not isinstance(blocks,list):raise ValueError('VL 결과에 본문 블록이 없습니다.')
    texts=[]
    for block in blocks:
        text=block.get('block_content','')
        if not isinstance(text,str):continue
        if '<table' in text.lower():
            p=PlainHTML();p.feed(text);text=''.join(p.parts)
        if text.strip():texts.append(text.strip())
    text='\n\n'.join(texts)
    if not text.strip():raise ValueError('VL이 인식한 본문이 없습니다.')
    return text[:100000]

def recognize(path):
    s=status()
    if not s['ready']:raise ValueError('VL 설치·모델 경로 확인 필요: '+' / '.join(s['missing']))
    home,exe,layout,vl=paths();start=time.monotonic()
    # Same lock as foreground v5 recognition: never run both models at once.
    with paddle_adapter._LOCK,tempfile.TemporaryDirectory(prefix='er-vl-') as tmp:
        paddle_adapter.stop_worker()
        out=Path(tmp)/'result';out.mkdir();log=Path(tmp)/'worker.log'
        image=Path(tmp)/'page.png'
        with Image.open(path) as source:ImageOps.exif_transpose(source).convert('RGB').save(image)
        with log.open('wb') as stream:
            try:
                proc=subprocess.run([str(exe),str(Path(__file__).with_name('vl_worker.py')),str(image),str(out),str(layout),str(vl)],
                    cwd=str(home),stdout=stream,stderr=subprocess.STDOUT,timeout=1800,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),
                    env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK':'True'})
            except subprocess.TimeoutExpired as e:raise ValueError('VL 처리 30분 초과. 기존 자료는 유지됩니다. 다시 시도할 수 있습니다.') from e
        if proc.returncode:
            tail=log.read_bytes()[-3000:].decode('utf-8',errors='replace')
            raise ValueError('VL 처리 실패 · '+tail[-900:])
        files=list(out.glob('*.json'))
        if len(files)!=1:raise ValueError('VL 결과 JSON을 찾지 못했습니다.')
        data=json.loads(files[0].read_text(encoding='utf-8-sig'))
        return dict(text=parse_result(data),raw=data,seconds=round(time.monotonic()-start,1))

if __name__=='__main__':
    print(json.dumps(status(),ensure_ascii=False,indent=2))
