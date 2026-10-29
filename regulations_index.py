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
            current=dict(kind='article',text=pending+line,number=number,title=stripped,review=False,chapter=chapter,section=section);pending='';continue
        if current:current['text']+=line
        else:
            pending+=line
            if not stripped and pending.strip() and not all(STRUCTURE.match(x) or not x.strip() for x in pending.splitlines()):flush_pending()
    flush_current();flush_pending()
    if ''.join(piece['text'] for piece in pieces)!=raw:raise ValueError('원문 분리 검증에 실패했습니다.')
    return pieces

def snippet(text,query,limit=480):
    if not query:return text[:limit]
    target=normalize(query);chars=[];positions=[]
    for i,char in enumerate(text):
        normalized=normalize(char)
        for c in normalized:chars.append(c);positions.append(i)
    index=''.join(chars).find(target)
    start=max(0,positions[index]-100) if index>=0 else 0
    return ('…' if start else '')+text[start:start+limit]+('…' if start+limit<len(text) else '')
