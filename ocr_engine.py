"""Offline OCR candidates and review evidence. Never guesses or rewrites numbers."""
import csv, io, os, re, shutil, subprocess, tempfile, time
from pathlib import Path
from PIL import Image, ImageOps

TERMS=('임단협','주휴수당','노사협의회','임금피크제','성과금','성과급','단체협약','노동조합','교대근무','산업안전','통상임금','특별휴가','복리후생','고용안정','정년연장')
def near(a,b):
    if abs(len(a)-len(b))>1:return False
    if len(a)==len(b):return sum(x!=y for x,y in zip(a,b))==1
    if len(a)>len(b):a,b=b,a
    return any(a==b[:i]+b[i+1:] for i in range(len(b)))
def suggestions(word):
    # Suggest only isolated Hangul words. Never change OCR output automatically.
    if not re.fullmatch('[가-힣]{4,12}',word) or word in TERMS:return []
    return [term for term in TERMS if len(term)>=4 and near(word,term)]
def parse_tsv(data,w,h,offset=(0,0),scale=(1,1)):
    groups={}
    for row in csv.DictReader(io.StringIO(data),delimiter='\t',quoting=csv.QUOTE_NONE):
        if row.get('level')!='5' or not row.get('text','').strip():continue
        try:
            conf=float(row['conf']);x=int(row['left']);y=int(row['top']);bw=int(row['width']);bh=int(row['height'])
            key=(row['page_num'],row['block_num'],row['par_num'],row['line_num'])
        except (KeyError,ValueError):continue
        word={'text':row['text'].strip(),'confidence':round(conf,1),'box':[offset[0]+x/w*scale[0],offset[1]+y/h*scale[1],bw/w*scale[0],bh/h*scale[1]]}
        groups.setdefault(key,[]).append(word)
    lines=[]
    for key,words in groups.items():
        joined=[]
        for word in words:
            previous=joined[-1] if joined else None
            if previous:
                a=previous['box'];b=word['box'];gap=(b[0]-a[0]-a[2])*w/scale[0]
                height=min(a[3],b[3])*h/scale[1]
                if re.search('[가-힣]$',previous['text']) and re.match('[가-힣]',word['text']) and gap<height*.25:
                    previous['text']+=word['text'];previous['confidence']=min(previous['confidence'],word['confidence'])
                    previous['box']=[a[0],min(a[1],b[1]),b[0]+b[2]-a[0],max(a[1]+a[3],b[1]+b[3])-min(a[1],b[1])]
                    continue
            joined.append(word)
        lines.append({'block':key[:2],'text':' '.join(word['text'] for word in joined),'words':joined})
    return lines

def as_candidate(name,lines):
    words=[w for line in lines for w in line['words']]
    weight=sum(len(w['text']) for w in words)
    confidence=sum(max(0,w['confidence'])*len(w['text']) for w in words)/max(1,weight)
    text='\n'.join(line['text'] for line in lines)
    warnings=[]
    for word in words:
        proposed=suggestions(word['text'])
        if word['confidence']<65 or proposed:
            warnings.append({**word,'suggestions':proposed})
    return {'name':name,'text':text,'confidence':round(confidence,1),'warnings':warnings[:150], 'warning_count':len(warnings),'lines':lines,'reliable_chars':sum(len(w['text']) for w in words if w['confidence']>=65)}

def run_tsv(exe,path,psm,deadline,horizontal=True):
    remain=deadline-time.monotonic()
    if remain<=0:raise TimeoutError('OCR 시간 한도')
    env={**os.environ,'OMP_THREAD_LIMIT':'1'}
    command=[exe,str(path),'stdout','-l','kor+eng','--psm',str(psm),'-c','tessedit_create_tsv=1','-c','tessedit_create_txt=0']
    if horizontal:
        command+=['-c','textord_tabfind_vertical_text=0']
        models=Path(__file__).resolve().parent/'ocr-models'
        if all((models/(lang+'.traineddata')).exists() for lang in ('kor','eng')):command+=['--tessdata-dir',str(models),'--oem','1']
    r=subprocess.run(command,capture_output=True,timeout=min(60,remain),env=env)
    if r.returncode:raise OSError('OCR 실행 실패')
    return r.stdout.decode('utf-8',errors='replace')

def recognize_tesseract(path,layout='auto'):
    result={'raw':'','variants':[],'selected':0,'status':'OCR 미설치 · 직접 입력 가능'}
    exe=os.environ.get('TESSERACT_CMD') or shutil.which('tesseract')
    if not exe:return result
    try:
        langs=subprocess.run([exe,'--list-langs'],capture_output=True,text=True,timeout=10)
        if not {'kor','eng'}<=set(langs.stdout.split()):
            result['status']='한국어/영어 OCR 데이터 미설치 · 직접 입력 가능';return result
        deadline=time.monotonic()+180
        with Image.open(path) as source, tempfile.TemporaryDirectory(prefix='er-body-') as tmp:
            original=ImageOps.exif_transpose(source).convert('RGB');w,h=original.size
            base_path=Path(tmp)/'original.png';original.save(base_path)
            lines=parse_tsv(run_tsv(exe,base_path,3,deadline,False),w,h)
            base=as_candidate('원본 인식',lines);result['raw']=base['text'];result['variants'].append(base)
            enhanced=ImageOps.autocontrast(ImageOps.grayscale(original),cutoff=.5)
            factor=min(2.5,3600/max(w,h));factor=max(1,factor) if max(w,h)<3600 else factor
            enhanced=enhanced.resize((round(w*factor),round(h*factor)),Image.Resampling.LANCZOS)
            ew,eh=enhanced.size
            enhanced_path=Path(tmp)/'enhanced.png';enhanced.save(enhanced_path)
            if layout=='columns':
                # Explicit two-column mode, chosen by administrator; no guessed column cut.
                lines=[]
                for index,(left,right) in enumerate(((0,ew//2),(ew//2,ew))):
                    part=enhanced.crop((left,0,right,eh));part_path=Path(tmp)/f'col{index}.png';part.save(part_path)
                    found=parse_tsv(run_tsv(exe,part_path,3,deadline),part.width,part.height,(left/ew,0),(part.width/ew,1))
                    for line in found:line['block']=(str(index),line['block'][1])
                    lines.extend(found)
                label='2단 분리 인식'
            else:
                lines=parse_tsv(run_tsv(exe,enhanced_path,3,deadline),ew,eh);label='확대·명암 보정'
            improved=as_candidate(label,lines);result['variants'].append(improved)
            if layout=='auto':
                dense=parse_tsv(run_tsv(exe,enhanced_path,6,deadline),ew,eh)
                result['variants'].append(as_candidate('한 단 집중 인식 (다단 지면은 순서 확인)',dense))
            # Re-read uncertain text blocks as single blocks; keep original block order.
            blocks={}
            for line in lines:blocks.setdefault(tuple(line['block']),[]).append(line)
            replacements={}
            eligible=[]
            for key,block in blocks.items():
                c=as_candidate('',block)
                if len(re.findall('[가-힣]',c['text']))>=20 and c['confidence']<88:eligible.append((c['confidence'],key,block))
            for _,key,block in sorted(eligible,key=lambda x:x[0])[:4]:
                words=[word for line in block for word in line['words']]
                x=max(0,min(t['box'][0] for t in words)-.004);y=max(0,min(t['box'][1] for t in words)-.004)
                right=min(1,max(t['box'][0]+t['box'][2] for t in words)+.004);bottom=min(1,max(t['box'][1]+t['box'][3] for t in words)+.004)
                part=enhanced.crop((round(x*ew),round(y*eh),round(right*ew),round(bottom*eh)))
                crop_path=Path(tmp)/'block.png';part.save(crop_path)
                try:retry=parse_tsv(run_tsv(exe,crop_path,6,deadline),part.width,part.height,(x,y),(right-x,bottom-y))
                except (OSError,subprocess.TimeoutExpired,TimeoutError):break
                before=as_candidate('',block);after=as_candidate('',retry)
                if after['confidence']>=before['confidence']+4 and .85<=len(after['text'])/max(1,len(before['text']))<=1.3:
                    replacements[key]=retry
            if replacements:
                rebuilt=[]
                for key,block in blocks.items():rebuilt.extend(replacements.get(key,block))
                result['variants'].append(as_candidate('보정·문단별 재인식',rebuilt))
            # Confidence is a selection heuristic, NOT a measured accuracy percentage.
            baseline_count=base['reliable_chars']
            candidates=[(i,v) for i,v in enumerate(result['variants']) if v['reliable_chars']>=baseline_count*.85 and not v['name'].startswith('한 단')]
            if candidates:result['selected']=max(candidates,key=lambda pair:pair[1]['confidence'])[0]
            if layout=='columns':result['selected']=len(result['variants'])-1
            result['status']='본문 OCR 완료 · 의심 단어 확인 필요'
    except (OSError,ValueError,subprocess.TimeoutExpired,TimeoutError):
        result['status']='OCR 일부 처리 실패 · 남은 결과 확인' if result['variants'] else 'OCR 실패 · 직접 입력 가능'
    for variant in result['variants']:variant.pop('lines',None)
    return result


def recognize_body(path,layout='auto'):
    from paddle_adapter import recognize
    return recognize(path,layout)
