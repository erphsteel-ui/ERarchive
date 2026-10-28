"""Offline HWP 5 text reader and conservative, review-only schedule extraction."""
import datetime as dt
import io
import re
import struct
import zlib
from vendor import olefile

LIMIT = 16 * 1024 * 1024

def hwp_text(raw):
    if not raw.startswith(bytes.fromhex('d0cf11e0a1b11ae1')):
        raise ValueError('일반 HWP 5 파일이 아닙니다. DRM·암호 문서는 읽을 수 없습니다.')
    paragraphs=[]; total=0
    with olefile.OleFileIO(io.BytesIO(raw)) as ole:
        header=ole.openstream('FileHeader').read(256)
        if not header.startswith(b'HWP Document File') or len(header)<40:raise ValueError('HWP 헤더를 확인할 수 없습니다.')
        flags=struct.unpack_from('<I',header,36)[0]
        if flags & (2|4):raise ValueError('암호 또는 배포용 HWP는 지원하지 않습니다.')
        sections=sorted((p for p in ole.listdir() if len(p)==2 and p[0]=='BodyText' and re.fullmatch(r'Section\d+',p[1])),key=lambda p:int(p[1][7:]))
        for path in sections:
            if ole.get_size(path)>LIMIT:raise ValueError('문서 본문이 너무 큽니다.')
            data=ole.openstream(path).read()
            if flags&1:
                decoder=zlib.decompressobj(-15);data=decoder.decompress(data,LIMIT+1)
                if len(data)>LIMIT or not decoder.eof:raise ValueError('HWP 압축 본문이 너무 크거나 손상되었습니다.')
            total+=len(data)
            if total>LIMIT:raise ValueError('문서 본문이 너무 큽니다.')
            pos=0; tables=[]; section=[]
            while pos+4<=len(data):
                head=struct.unpack_from('<I',data,pos)[0];pos+=4;tag=head&1023;level=(head>>10)&1023;size=head>>20
                if size==4095:
                    if pos+4>len(data):raise ValueError('손상된 HWP 레코드')
                    size=struct.unpack_from('<I',data,pos)[0];pos+=4
                if pos+size>len(data):raise ValueError('손상된 HWP 레코드')
                block=data[pos:pos+size];pos+=size
                while tables and level<=tables[-1]['level']:
                    tables.pop()
                if tag==71 and block[:4]==b' lbt':
                    table={'level':level,'cells':[],'items':[],'current':None}
                    target=tables[-1]['current']['items'] if tables and tables[-1]['current'] is not None else section
                    target.append(table);tables.append(table)
                elif tag==72 and tables and level==tables[-1]['level']+1 and len(block)>=34:
                    col,row,cs,rs=struct.unpack_from('<HHHH',block,8)
                    cell={'col':col,'row':row,'cs':cs,'rs':rs,'items':[]}
                    tables[-1]['cells'].append(cell);tables[-1]['current']=cell
                if tag!=67:continue
                # Embedded HWP control codes occupy eight UTF-16 code units.
                clean=bytearray();i=0
                while i+2<=len(block):
                    code=int.from_bytes(block[i:i+2],'little')
                    if code in (1,2,3,4,5,6,7,8,9,11,12,14,15,16,17,18,19,20,21,22,23):
                        clean.extend(b' \x00');i+=16
                    elif code<32:
                        clean.extend(b'\n\x00' if code in (10,13) else b' \x00');i+=2
                    else:clean.extend(block[i:i+2]);i+=2
                text=clean.decode('utf-16le',errors='replace').strip()
                if text:
                    target=tables[-1]['current']['items'] if tables and tables[-1]['current'] is not None else section
                    target.append(text)
            paragraphs.extend(render_hwp_items(section))
    if not paragraphs:raise ValueError('추출할 텍스트가 없습니다. 이미지로 된 HWP는 이미지 홍보물로 등록해 주세요.')
    return '\n'.join(paragraphs)

def render_hwp_items(items):
    """Retain calendar coordinates before flattening. Never borrow across weeks."""
    out=[]
    for item in items:
        if isinstance(item,str):out.append(item);continue
        cells=item['cells']
        dates={}
        for cell in cells:
            strings=[x for x in cell['items'] if isinstance(x,str)]
            matches=[(x,date_matches(x)) for x in strings]
            pure=[(x,ms[0]) for x,ms in matches if len(ms)==1 and not ACTIVITY.search(x) and not re.sub(r'[\s()월화수목금토일.]+','',DATE.sub('',x))]
            if len(pure)==1 and cell['cs']==cell['rs']==1:
                dates[(cell['row'],cell['col'])]=pure[0][0]
        # Calendar rows have at least three adjacent, explicit date cells.
        date_rows=set()
        for row in {r for r,c in dates}:
            cols=sorted(c for r,c in dates if r==row)
            if len(cols)>=3 and all(b==a+1 for a,b in zip(cols,cols[1:])):
                try:
                    ds=[date_matches(dates[(row,c)])[0] for c in cols]
                    vals=[dt.date(int(m[1] or 2000),int(m[2]),int(m[3])) for m in ds]
                    if all((b-a).days==1 or (a.month==12 and b.month==1 and a.day==31 and b.day==1) for a,b in zip(vals,vals[1:])):date_rows.add(row)
                except ValueError:pass
        if date_rows:
            out.append('[표 경계]')
            for cell in sorted(cells,key=lambda c:(c['row'],c['col'])):
                r,c=cell['row'],cell['col'];date=None
                if cell['cs']==cell['rs']==1:
                    if r in date_rows:date=dates.get((r,c))
                    elif r-1 in date_rows:date=dates.get((r-1,c))
                for line in render_hwp_items(cell['items']):
                    if not ACTIVITY.search(line):continue
                    if date:
                        # An explicit date inside the event wins over the calendar heading.
                        out.extend(['[표 경계]',line if date_matches(line) else date+' '+line])
                    else:out.append('[날짜 미연결] '+line)
            out.append('[표 경계]')
        else:
            for cell in cells:
                if len(cells)>1:out.append('[표 경계]')
                out.extend(render_hwp_items(cell['items']))
            if len(cells)>1:out.append('[표 경계]')
    return out

# Versioned to rebuild untouched old proposals from saved OCR/HWP text.
EXTRACTOR_VERSION = '0.18.0'
DATE = re.compile(r'(?<![\d/])(?:(20\d{2})\s*(?:년\s*|[./-]\s*))?(\d{1,2})\s*(?:월\s*|[./]\s*)(\d{1,2})\s*일?(?!\d)')
CLOCK = re.compile(r'(?:(?:오전|오후)\s*)?\d{1,2}\s*(?::\s*\d{2}|시(?:\s*\d{1,2}\s*분?)?)')
PAST = re.compile(r'진행\s*(?:되었|됐|하였|했)|개최\s*(?:되었|됐|하였|했)|실시\s*(?:되었|됐|하였|했)|참석\s*(?:하였|했)|회의\s*결과|마쳤|밝혔|요구하[며고]|지적하[며고]|시정\s*지시|보고\s*사항|사고\s*발생')
META = re.compile(r'발\s*행\s*일|발\s*행\s*인|펴낸[날곳이]|편집[·ㆍ:]|홈페이지|https?://|www\.|TEL\s*[:\d]|FAX\s*[:\d]|전화\s*[:\d]',re.I)
FUTURE = re.compile(r'차기|예정|소집|개최\s*안내|참가\s*요청|모집|접수|마감|까지|기간|일\s*시|일정|계획|실시한다|진행한다')
ACTIVITY = re.compile(r'전노대|산안보|토론회|기자회견|교섭|회의|위원회|운영위|산보위|노사협|상견례|간담회|집담회|설명회|총회|대회|집회|수련회|교육|시사회|선거|투표|공모|설문\s*조사|품평회|파업|출근\s*투쟁|조인식|후보\s*등록')
BOUNDARY = re.compile(r'^\s*[■☞]|^\s*(?:안건|보고)\s*\d+[. :]')
LABEL = re.compile(r'^[\s○●▶▷■□※▣⇨☞*\-=]+')

def clean(value):
    value=LABEL.sub('',value).strip()
    return re.sub(r'^(?:안건\s*)?\d+(?:-\d+)?\.\s*','',value).strip()

def activity_title(value):
    """Small evidence-based labels; no free-form generation or invented subjects."""
    text=clean(value)
    text=re.sub(r'전노대','전국노동자대회',text)
    text=DATE.sub(' ',text)
    text=re.sub(r'[~～∼–]\s*\d{1,2}\s*일',' ',text)
    text=re.sub(r'\(?[월화수목금토일]\)|\[[월화수목금토일]\]',' ',text)
    text=CLOCK.sub(' ',text)
    text=re.sub(r'\s+',' ',text)
    patterns=[
      (r'집단교섭.*?불참사업장.*?대표자\s*회의','집단교섭 불참사업장 대표자 회의'),
      (r'사무장단회의.*?단체협약위원회.*?회의','사무장단·단체협약위원회 회의'),
      (r'마음\s*돌봄\s*수련회','마음돌봄 수련회'),
      (r'확대\s*간부\s*수련회','확대간부 수련회'),
      (r'특별\s*산안보(?:위|위원회)?','특별 산업안전보건위원회'),
      (r'연대\s*지원','연대 지원'),
      (r'(?:만족도|단체교섭|산별교섭|조합원\s*의견)?\s*설문\s*조사',None),
      (r'(?:\d+\s*차\s*)?품평회',None),
      (r'(?:대의원|임원|지회장|위원장|집행부)\s*(?:선거|선출\s*투표)',None),
      (r'(?:잠정\s*합의(?:안)?|쟁의행위|찬반)\s*(?:찬반\s*)?투표',None),
      (r'(?:차기\s*|\d+차\s*|보충\s*|단체\s*|임금\s*|실무\s*|집단\s*|중앙\s*|본\s*)+교섭(?:\s*(?:조인식|상견례))?',None),
      (r'안전\s*[숏숫솟]\s*[폼품]\s*영상\s*공모','안전 숏폼 영상 공모'),
      (r'활동가\s*양성\s*<?중급\s*과정>?','활동가양성 중급과정'),
      (r'교육\s*활동가\s*대회','교육활동가대회'),
      (r'전국\s*노동자\s*대회','전국노동자대회'),
      (r'금속\s*노동자\s*대회','금속노동자대회'),
      (r'기후\s*정의.*?(?:회의|간담회)','기후정의 담당자 회의'),
      (r'문화패원.*?수련회','문화패원·문체담당자 수련회'),
      (r'여성\s*사업\s*담당자.*?(?:회의|수련회)','여성사업담당자 회의'),
      (r'지역지회\s*합동간부\s*수련회','지역지회 합동간부 수련회'),
      (r'정의로운\s*노동전환\s*집담회\s*\d*',None),
      (r'(?:열사영상|열사\s*영상)\s*시사회','열사영상 시사회'),
      (r'(?:제도개선위원회|투자발전위원회|노동안전보건위원회|조직혁신소위원회|단체협약위원회|집행위원회|운영위원회|조직소위원회)(?:\s*(?:회의|상견례))?',None),
      (r'(?:차기|상집|확간|쟁대위|사무장단|조직담당자|집행부|대의원|대표자|운영위)\s*회의',None),
      (r'(?:조합원|노조간부|안전|기본과정|노동법)\s*교육',None),
      (r'(?:[가-힣]+\s*){0,2}(?:간담회|집담회|설명회|조인식|수련회|결의대회|노사협의회|산보위)',None),
      (r'(?:후보(?:자)?\s*등록|출근\s*투쟁|총회|교섭회의|교섭|회의(?!실)|집회|파업|공모|선거|투표|교육)',None),
    ]
    for pattern,replacement in patterns:
        m=re.search(pattern,text)
        if not m:continue
        title=replacement or m[0].strip()
        title=re.sub(r'^(?:참가|일정|안내|우리|이번|차기에는)\s+','',title)
        return re.sub(r'\s+',' ',title)[:60]
    return ''

def date_matches(line):
    return [m for m in DATE.finditer(line) if not re.match(r'\s*(?:분기|차|기|일차)',line[m.end():])]

def reference_date(text,name,reference):
    try:return dt.date.fromisoformat(reference[:10])
    except (ValueError,TypeError):pass
    m=re.match(r'(20\d{2}|\d{2})(\d{2})(\d{2})(?:_|\D)',name)
    if m:
        try:return dt.date(int(m[1])+(2000 if len(m[1])==2 else 0),int(m[2]),int(m[3]))
        except ValueError:pass
    for line in text.splitlines()[:20]:
        ms=date_matches(line)
        if ms and ms[0][1]:
            m=ms[0]
            try:return dt.date(int(m[1]),int(m[2]),int(m[3]))
            except ValueError:pass
    return None

def subject_from(value):
    # Only explicit actors; a meeting venue and the publisher alone are not actors.
    m=re.match(r'\s*[▶▷●○]?\s*([가-힣A-Za-z0-9 ·]{2,35})\s*[:：]',value)
    if m and not re.search(r'일시|장소|기간|일정|차기\s*회의|차기|안건|보고|참가|방법|대상|회차|제목|문서번호|시행일|수신|참조|문의',m[1]):return m[1].strip()
    m=re.search(r'(?:현대제철\s*(?:포항|당진|인천|순천|당냉)(?:공장|지회)?|현대자동차(?:지부)?|기아(?:자동차)?지부|포스코노동조합|금속노조\s*충남지부|(?:금속노조\s*)?철강업종분과위원회)',value)
    return m[0] if m else ''

def extract_events(text,name='',reference=''):
    ref=reference_date(text,name,reference)
    lines=[]
    for original in text.splitlines():
        original=re.sub(r'\s+',' ',original).strip()
        if not original:continue
        actor=subject_from(original)
        # A full month/day in a later clause cannot label an earlier event.
        clauses=re.split(r'[,;；]|(?:그리고|이후에는)\s*',original)
        if len(clauses)>1 and sum(bool(date_matches(c) or re.search(r'(?<![\d/])\d{1,2}(?:[~～∼–]\d{1,2})?일',c)) for c in clauses)>1:
            for clause in clauses:
                clause=clause.strip()
                if not clause:continue
                if actor and not subject_from(clause):clause=actor+' : '+clause
                lines.append(clause)
        else:lines.append(original)
    inferred_month=set()
    if ref:
        # Month inference only with an explicit actor and publication reference.
        for i,line in enumerate(lines):
            if subject_from(line) and not date_matches(line):
                lines[i]=re.sub(r'(?<![\d/])(\d{1,2})(?=(?:[~～∼–]\d{1,2})?일)',str(ref.month)+'월 '+r'\1',line,count=1)
                if lines[i]!=line:inferred_month.add(i)
    year=ref.year if ref else dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).year
    results=[];seen={};heading='';heading_index=-100;heading_table=False
    for i,line in enumerate(lines):
        if line.startswith('[표 경계]'):
            heading='';heading_index=-100;heading_table=False;continue
        if line.startswith('[날짜 미연결]'):continue
        if BOUNDARY.search(line) or (len(line)<=85 and not date_matches(line) and not PAST.search(line) and not META.search(line) and ACTIVITY.search(line) and re.search(r'(?:안내|소집|시행|요청|건|KICK-OFF|회의|대회|공모|교육|수련회)$',line)):
            heading=clean(line);heading_index=i;heading_table=False
        # A table's row labels can separate the heading and dates by several lines.
        if line in ('회차','일시','일정') and i-heading_index<8:heading_table=True
        ms=date_matches(line)
        if not ms or META.search(line) or re.search(r'\d+\s*호[),）\s]',line):continue
        if PAST.search(line) or re.search(r'(?:선거|투표|회의)(?:는|란).*?(?:한\s*번|경우|원칙|규정)',line):continue
        # Keep a single-date lead-in with its wrapped continuation, but stop at another event.
        local=line
        if not ACTIVITY.search(local) and not BOUNDARY.search(line) and re.search(r'일시|일정|기간|마감|접수|모집',line):
            for nxt in lines[i+1:i+3]:
                if BOUNDARY.search(nxt) or date_matches(nxt) or META.search(nxt) or re.match(r'.*장\s*소\s*[:：]',nxt):break
                local+=' '+nxt
                if ACTIVITY.search(nxt):break
        if PAST.search(local):continue
        own_title='' if re.match(r'일\s*시|날짜|기간',clean(line)) else activity_title(local)
        explicit_date_label=bool(re.search(r'일\s*시|일정|기간|기한|마감|접수|모집',line))
        # Headings are only inherited within their block, never arbitrary nearby prose.
        parent=''
        if not own_title:
            prev=lines[i-1] if i else ''
            if heading_table or (heading and explicit_date_label and i-heading_index<=40):
                if heading and not PAST.search(heading) and not META.search(heading):parent=heading
            if explicit_date_label and not parent and prev and len(prev)<=80 and not date_matches(prev) and not META.search(prev) and not PAST.search(prev) and ACTIVITY.search(prev):parent=clean(prev)
            if parent and not (explicit_date_label or heading_table or re.fullmatch(r'[\d\s년월일./:()~～∼–\-수목금토화월시분오전후박]+',clean(line))):parent=''
        if not parent and heading and i-heading_index<=4 and re.search(r'취합|참가인원|보고한다',line):parent=heading
        title=own_title or activity_title(parent)
        if not title:continue
        if PAST.search(parent):continue
        # Reject retrospective material relative to publication date, not today's date.
        for n,m in enumerate(ms):
            if n and re.search(r'[~～∼–]|부터',line[ms[n-1].end():m.start()]):continue
            warnings=['발행일 기준 월 추정 · 확인 필요'] if i in inferred_month else []
            try:start=dt.date(int(m[1] or year),int(m[2]),int(m[3]))
            except ValueError:continue
            if not m[1] and ref and ref.month==12 and start.month==1 and FUTURE.search(local):start=start.replace(year=year+1)
            end=start;next_m=ms[n+1] if n+1<len(ms) else None
            range_end=next_m if next_m and re.search(r'[~～∼–]|부터',line[m.end():next_m.start()]) else None
            short_end=None
            try:
                if range_end:
                    end=dt.date(int(range_end[1] or start.year),int(range_end[2]),int(range_end[3]))
                    if not range_end[1] and start.month==12 and end.month==1:end=end.replace(year=start.year+1)
                else:
                    short_end=re.search(r'[~～∼–]\s*(\d{1,2})\s*일',line[m.end():next_m.start() if next_m else len(line)])
                    if short_end:end=start.replace(day=int(short_end[1]))
            except ValueError:continue
            if end<start:continue
            if ref and end<ref:continue
            if not m[1]:warnings.append('연도 추정 · 확인 필요')
            for match,date,label in [(m,start,'날짜'),(range_end,end,'종료 날짜')]:
                if match:
                    wd=re.match(r'\s*[.(（\[]?\s*([월화수목금토일])\s*[)）\]]',line[match.end():])
                    if wd and '월화수목금토일'[date.weekday()]!=wd[1]:warnings.append(label+'와 요일 불일치')
            if short_end:
                wd=re.match(r'\s*[.(（\[]?\s*([월화수목금토일])\s*[)）\]]',line[m.end()+short_end.end():])
                if wd and '월화수목금토일'[end.weekday()]!=wd[1]:warnings.append('종료 날짜와 요일 불일치')
            part=line[m.end():next_m.start() if next_m and not range_end else len(line)]
            stage=''
            if re.search(r'참가인원.*(?:보고|취합)',line):stage='참가인원 보고 마감'
            elif re.search(r'마감|까지.*(?:취합|보고)|취합한다',part):stage='마감'
            elif re.search(r'접수|모집',part) and not re.search(r'마감',local):stage='접수'
            elif re.search(r'검토',part):stage='검토'
            elif re.search(r'지급',part):stage='지급'
            # Submission deadlines should inherit their named activity, not become "마감" alone.
            if stage=='마감' and parent and activity_title(parent):title=activity_title(parent)
            clause=line[line.rfind(',',0,m.start())+1:next_m.start() if next_m and not range_end else len(line)]
            clause=clause.split(',',1)[0]
            nearby=activity_title(clause) if not re.match(r'일\s*시|날짜|기간',clean(line)) else ''
            if len(ms)>1 and not range_end:
                own_part=activity_title(part)
                if own_part:nearby=own_part
                else:
                    shared=activity_title(parent) or activity_title(line[:ms[0].start()])
                    if not shared:continue
                    nearby=shared
            base_title=nearby or title
            final_title=base_title+(' '+stage if stage and stage not in base_title else '')
            final_title=re.sub(r'^(?:(?:및|그리고|또는)\s*)+', '', final_title).strip()
            paid=re.search(r'([가-힣]{2,15})\s*지급',part)
            if paid:final_title=paid[1]+' 지급'
            subject=subject_from(line) or subject_from(parent)
            if not subject and re.fullmatch(r'(?:차기\s*)?회의',final_title):continue
            quote='\n'.join(([parent] if parent else [])+[local])[:1600]
            if not subject:warnings.append('주체 확인 필요')
            if not ref and not m[1]:warnings.append('발행일 근거 없음')
            state='취소' if '취소' in local else '보류' if re.search('보류|연기',local) else '예정'
            key=(start.isoformat(),end.isoformat(),final_title,subject)
            if key in seen:continue
            seen[key]=True
            results.append(dict(start=key[0],end=key[1],time='',end_time='',title=final_title,place='',row='',subject=subject,kind='마감' if stage.endswith('마감') else '일정',status=state,quote=quote,warnings=warnings,extractor=EXTRACTOR_VERSION))
            if len(results)>=300:return results
    # Only suppress a single-day summary when a compatible range contains it.
    norm=lambda v:re.sub(r'\s+','',v or '').casefold()
    ranges=[x for x in results if x['start']!=x['end']]
    merged=[]
    for e in results:
        if e['start']==e['end'] and any(
            norm(e['title'])==norm(p['title']) and
            (norm(e['subject'])==norm(p['subject']) or not norm(e['subject']) or not norm(p['subject'])) and
            p['start']<=e['start']<=p['end'] for p in ranges
        ):continue
        merged.append(e)
    return merged
