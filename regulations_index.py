"""Deterministic text segmentation for the offline regulation archive."""
import re, unicodedata

STRUCTURE=re.compile(r'^\s*(제\s*[0-9０-９일이삼사오육칠팔구십백천]+\s*(장|절)(?:\s*의\s*\d+)?)(?:\s|$|[\[(])')
ARTICLE=re.compile(r'^\s*제\s*([0-9０-９]+)\s*조(?:\s*의\s*([0-9０-９]+))?(?=$|\s|[\[(])')
CITATION=re.compile(r'^\s*(?:에|에서|에게|의|을|를|가|이|은|는|로|으로|와|과|부터|까지)(?:\s|따른|의해|의한|$)')
APPENDIX=re.compile(r'^\s*(부\s*칙|\[\s*별\s*표[^\]]*\]|별\s*표\s*\d*)(?=\s|$|[\[(])')
COMPONENT=re.compile(r'^\s*(?:(?P<paragraph>[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]|제\s*\d+\s*항)|(?P<item>\d+\.)|(?P<subitem>[가-힣]\.))')

def component_markers(text):
    """Record line-level paragraph/item labels while retaining the original text."""
    markers=[]
    for line_number,line in enumerate(text.splitlines()):
        match=COMPONENT.match(line)
        if match:
            kind='항' if match.group('paragraph') else '호' if match.group('item') else '목'
            markers.append({'kind':kind,'marker':match.group({'항':'paragraph','호':'item','목':'subitem'}[kind]),'line':line_number})
    return markers

def normalize(text):return re.sub(r'\s+','',unicodedata.normalize('NFKC',text or '')).casefold()
def number_key(text):
    match=re.fullmatch(r'(?:제)?(\d+)조(?:의(\d+))?',normalize(text))
    return (str(int(match[1]))+('의'+str(int(match[2])) if match[2] else '')) if match else ''

def parse_document(raw):
    """Preserve every character; segment article starts only at unambiguous line starts."""
    if not isinstance(raw,str) or not raw.strip():raise ValueError('원문을 입력하세요.')
    pieces=[];current=None;pending='';chapter='';section='';area='';
    def push(kind,text,number='',title='',review=False,chapter_value=None,section_value=None):
        if not text:return
        pieces.append(dict(kind=kind,number=number,title=title,text=text,chapter=chapter if chapter_value is None else chapter_value,section=section if section_value is None else section_value,review=review,order=len(pieces),components=component_markers(text)))
    def flush_current():
        nonlocal current
        if current:
            push(current['kind'],current['text'],current['number'],current['title'],current['review'],current['chapter'],current['section']);current=None
    def flush_pending():
        nonlocal pending
        if pending:
            # A nonempty preamble or irregular paragraph is retained for review.
            push('unstructured',pending,title='확인 필요 · 조문 외 원문',review=True);pending=''
    for line in raw.splitlines(keepends=True):
        stripped=line.strip();structure=STRUCTURE.match(line);appendix=APPENDIX.match(line);article=ARTICLE.match(line)
        if article and CITATION.match(line[article.end():]):article=None
        if structure:
            flush_current()
            # Keep headings with the next text block while recording their context.
            if pending and pending.strip() and not all(STRUCTURE.match(x) or not x.strip() for x in pending.splitlines()):flush_pending()
            if structure.group(2)=='장':chapter=stripped;section=''
            else:section=stripped
            pending+=line;continue
        if appendix:
            flush_current();flush_pending();area=stripped;chapter=area;section='';current=dict(kind='appendix',text=line,number='',title=stripped,review=False,chapter=chapter,section=section);continue
        if article:
            flush_current()
            if pending and pending.strip() and not all(STRUCTURE.match(x) or not x.strip() for x in pending.splitlines()):flush_pending()
            number=str(int(article[1]))+('의'+str(int(article[2])) if article[2] else '')
            header=re.match(r'^\s*제\s*[0-9０-９]+\s*조(?:\s*의\s*[0-9０-９]+)?\s*(?:\([^)]*\)|\[[^]]*\])',line)
            title=header.group(0).strip() if header else stripped
            current=dict(kind='article',text=pending+line,number=number,title=title,review=False,chapter=chapter,section=section);pending='';continue
        if current:current['text']+=line
        else:
            pending+=line
            if not stripped and pending.strip() and not all(STRUCTURE.match(x) or not x.strip() for x in pending.splitlines()):flush_pending()
    flush_current();flush_pending()
    if ''.join(piece['text'] for piece in pieces)!=raw:raise ValueError('원문 분리 검증에 실패했습니다.')
    return pieces

def snippet(text,query,limit=480):
    if not query:return text[:limit]
    target=normalize(query)
    if not target:return text[:limit]
    # KMP tracks only the matching prefix and the recent source offsets.
    # Avoid allocating a Python string and integer for every source character.
    from collections import deque
    prefix=[0]*len(target)
    j=0
    for i in range(1,len(target)):
        while j and target[i]!=target[j]:j=prefix[j-1]
        if target[i]==target[j]:j+=1
        prefix[i]=j
    positions=deque(maxlen=len(target));j=0;found=None
    for i,char in enumerate(text):
        for c in normalize(char):
            positions.append(i)
            while j and c!=target[j]:j=prefix[j-1]
            if c==target[j]:j+=1
            if j==len(target):
                found=positions[0];break
        if found is not None:break
    start=max(0,found-100) if found is not None else 0
    return ('…' if start else '')+text[start:start+limit]+('…' if start+limit<len(text) else '')

# Search indexing operates on normalized copies; regulation_documents retains the original.
def preprocess(raw):
    text=raw.replace('\u00a0',' ').replace('&nbsp;',' ').replace('\r\n','\n').replace('\r','\n')
    text=re.sub(r'[ \t]+',' ',text)
    text=re.sub(r'([^\n])(?=제\s*\d+\s*조(?:\s*의\s*\d+)?\s*(?:[([【]|삭\s*제))',r'\1\n',text)
    text=re.sub(r'(?m)^(\s*(?:\d+[.)]|-))\s*\n\s*',r'\1 ',text)
    text=re.sub(r'(?m)^(\s*(?:\d+[.)]|-)\s*\d+[A-Za-z]*)\s*\n\s*(?=[가-힣])',r'\1',text)
    return '\n'.join(line for line in text.split('\n') if not re.match(r'^\s*(?:제정일|개정일)\s*:',line))

def parse_hybrid(raw):
    """Index meaningful body text line by line; retain original separately in the DB."""
    if not isinstance(raw,str) or not raw.strip():raise ValueError('원문을 입력하세요.')
    text=preprocess(raw);lines=text.splitlines();pieces=[];current=None
    sub=chapter=section='';signed=False;buffer=[];toc=False
    article=re.compile(r'^(제\s*(\d+)\s*조(?:\s*의\s*(\d+))?)\s*(?:([\(\[【])([^\)\]】]*?)[\)\]】]|(삭\s*제))(.*)$')
    def flush():
        nonlocal current
        if current:
            content='\n'.join(current.pop('lines')).strip()
            if not content and current.pop('deleted',False):content='삭제된 조항입니다.'
            if content:
                current.update(text=content,order=len(pieces),components=component_markers(content));pieces.append(current)
            current=None
    def start(title,number='',kind='article',first='',deleted=False):
        nonlocal current
        flush();current=dict(kind=kind,number=number,title=title,chapter=' > '.join(x for x in (sub,chapter) if x),section=section,review=False,lines=[first] if first else [],deleted=deleted)
    standard=bool(re.search(r'(?m)^\s*1\.\s*적용범위',text) and re.search(r'(?m)^\s*\d+\.\d+\.\d+\s*[가-힣]',text))
    active=not standard;major=middle=''
    for index,line in enumerate(lines):
        s=line.strip()
        if standard:
            if not active:
                if not re.match(r'^1\.\s*적용범위',s):continue
                active=True
            m=re.match(r'^(\d+(?:\.\d+){0,2})(\.)?\s+([가-힣].*)$',s)
            if m:
                level=m[1].count('.');label=m[1]+(m[2] or '')+' '+m[3]
                flush()
                if level==0:major=label;middle='';chapter=section=''
                elif level==1:middle=label;chapter=major;section=''
                else:chapter=major;section=middle
                start(label,m[1]);continue
            if current:current['lines'].append(line)
            continue
        if re.fullmatch(r'목\s*차',s):flush();toc=True;continue
        match=article.match(s)
        if toc and re.fullmatch(r'전\s*문',s):
            following=next((x.strip() for x in lines[index+1:] if x.strip()),'')
            if following and not article.match(following) and not re.match(r'^제\s*\d+\s*[장절]',following) and not re.fullmatch(r'전\s*문',following):toc=False
        if toc:
            # Non-heading content marks the start of an actual candidate body.
            # TOC entries will be discarded by flush when they have no content.
            if s and not match and not re.fullmatch(r'전\s*문',s) and not re.match(r'^제\s*\d+\s*[장절]',s) and not re.match(r'^\d+\s*$',s):
                toc=False
            elif re.match(r'^제\s*1\s*장',s):
                toc=False
            else:continue
        sm=re.match(r'^\d+\)\s*(.+세칙.*)$',s)
        if sm:flush();sub=s;chapter=section='';signed=False;continue
        cm=re.match(r'^제\s*\d+\s*(장|절)\.?\s*(.*)$',s)
        if cm:
            flush()
            if cm[1]=='장':chapter=s;section=''
            else:section=s
            continue
        if re.match(r'^부\s*칙(?:\s|$|[<\[({])',s):flush();break
        if re.fullmatch(r'전\s*문',s):start('[전문] 전문',kind='preamble');continue
        if match:
            number=match[2]+('의'+match[3] if match[3] else '')
            title=match[1]+(' '+match[6] if match[6] else match[4]+match[5]+{'(':')','[':']','【':'】'}[match[4]])
            start(title,number,first=match[7].strip(),deleted=bool(match[6]));continue
        if re.match(r'^(?:[·ㆍ]?\s*별첨|▣)',s):start('[별첨] '+re.sub(r'^(?:[·ㆍ]?\s*별첨|▣)\s*','',s),kind='appendix');continue
        if re.match(r'^\d{4}\.\s*\d+\.\s*\d+',s):flush();signed=True;buffer=[];continue
        if signed and re.match(r'^(대표이사|위원장)',s):continue
        if s.startswith('■'):
            start('[별표] '+s[1:].strip(),kind='appendix');current['lines'].extend(buffer);buffer=[];signed=True;continue
        if signed:buffer.append(line)
        elif current:current['lines'].append(line)
    flush();return pieces
