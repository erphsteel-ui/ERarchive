"""Offline, versioned archive of administrator-supplied legal and workplace texts."""
import datetime as dt
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from flask import abort, jsonify, request
from schedule_extract import hwp_text

CATEGORIES = {
    'labor_act': '근로기준법',
    'labor_decree': '근로기준법 시행령',
    'union_act': '노동조합 및 노동관계조정법',
    'union_decree': '노동조합 및 노동관계조정법 시행령',
    'work_rules': '취업규칙',
    'agreement': '단체협약',
}
CHAPTER = re.compile(r'^\s*(제\s*[0-9０-９일이삼사오육칠팔구십백천]+\s*장(?:\s*의\s*\d+)?)(.*)$')
ARTICLE = re.compile(r'^\s*(제\s*([0-9０-９]+)\s*조(?:\s*의\s*([0-9０-９]+))?)(.*)$')
FILE_LIMIT=15*1024*1024

# Illustrative search fixtures only. They are not law text or company agreements.
SAMPLES={
 'labor_act': [('60','제60조 연차유급휴가','연차와 유급휴가 관련 검색 예시입니다. 실제 적용 기준은 등록된 공식 법령 원문을 확인하세요.'),('23','제23조 해고 등의 제한','해고와 징계 관련 검색 예시입니다. 실제 요건은 공식 법령 원문을 확인하세요.'),('50','제50조 근로시간','근로시간과 휴게 관련 검색 예시입니다. 실제 조문과 예외는 공식 원문을 확인하세요.')],
 'labor_decree': [('','근로기준법 시행령 예시','휴가 및 근로시간 관련 검색 예시입니다. 실제 시행령 원문을 등록해 확인하세요.')],
 'union_act': [('81','제81조 부당노동행위','노동조합 활동과 부당노동행위 관련 검색 예시입니다. 실제 내용은 공식 원문을 확인하세요.')],
 'union_decree': [('','노동조합법 시행령 예시','노동조합 및 쟁의행위 관련 검색 예시입니다. 실제 시행령 원문을 등록해 확인하세요.')],
 'work_rules': [('','사내 취업규칙 예시','연차, 휴가, 징계, 근로시간을 검색하기 위한 가상 예시입니다. 실제 회사 규정이 아닙니다.')],
 'agreement': [('','사내 단체협약 예시','교섭, 근로시간, 휴가, 타임오프를 검색하기 위한 가상 예시입니다. 실제 단체협약이 아닙니다.')],
}

def docx_text(raw):
    """Extract paragraphs in document order with a bounded, local-only XML parser."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            info=archive.getinfo('word/document.xml')
            if info.file_size>16*1024*1024:raise ValueError('문서 본문이 너무 큽니다.')
            xml=archive.read(info)
        if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():raise ValueError('지원하지 않는 문서 구조입니다.')
        root=ET.fromstring(xml)
    except (zipfile.BadZipFile,KeyError,ET.ParseError,RuntimeError,OSError) as exc:
        raise ValueError('DOCX 파일을 읽지 못했습니다. 암호 또는 손상 여부를 확인하세요.') from exc
    ns='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    lines=[]
    for paragraph in root.iter(ns+'p'):
        parts=[]
        for node in paragraph.iter():
            if node.tag==ns+'t' and node.text:parts.append(node.text)
            elif node.tag==ns+'tab':parts.append('\t')
            elif node.tag in (ns+'br',ns+'cr'):parts.append('\n')
        value=''.join(parts).strip()
        if value:lines.append(value)
    if not lines:raise ValueError('본문 텍스트가 없습니다. 이미지 문서는 텍스트로 변환해 주세요.')
    return '\n'.join(lines)

def parse_articles(text):
    """Keep every input line, and split only explicit Korean chapter/article headings."""
    chapter='기타';articles=[];current=None
    def flush():
        nonlocal current
        if current is not None:
            current['text']='\n'.join(current.pop('_lines')).strip()
            if current['text']:articles.append(current)
            current=None
    for line in text.replace('\r\n','\n').replace('\r','\n').split('\n'):
        ch=CHAPTER.match(line);article=ARTICLE.match(line)
        if ch:
            flush();chapter=line.strip();continue
        if article:
            flush();key=str(int(article.group(2)))+('의'+str(int(article.group(3))) if article.group(3) else '')
            current={'key':key,'chapter':chapter,'title':line.strip(),'_lines':[line]}
        else:
            if current is None:current={'key':'','chapter':chapter,'title':'본문','_lines':[]}
            current['_lines'].append(line)
    flush()
    return articles

def install(a):
    with a.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS regulation_versions (
          category TEXT NOT NULL, version INTEGER NOT NULL, title TEXT NOT NULL,
          effective_date TEXT NOT NULL, source TEXT NOT NULL, body TEXT NOT NULL,
          created TEXT NOT NULL, actor TEXT NOT NULL, PRIMARY KEY(category,version))''')
    @a.app.get('/api/regulations')
    @a.protected()
    def regulation_list():
        category=request.args.get('category','labor_act')
        if category not in CATEGORIES:abort(400)
        with a.db() as c:
            meta=[dict(row) for row in c.execute('SELECT category,version,title,effective_date,source,created FROM regulation_versions WHERE category=? ORDER BY version DESC',(category,))]
            requested=request.args.get('version','')
            if requested:
                try:version=int(requested)
                except ValueError:abort(400)
                if version<1:abort(400)
                row=c.execute('SELECT * FROM regulation_versions WHERE category=? AND version=?',(category,version)).fetchone()
                if not row:abort(404)
            else:row=c.execute('SELECT * FROM regulation_versions WHERE category=? ORDER BY version DESC LIMIT 1',(category,)).fetchone()
        entry=dict(row) if row else None
        if entry:entry['articles']=parse_articles(entry['body'])
        return jsonify(categories=CATEGORIES,entry=entry,versions=meta)
    @a.app.get('/api/regulations/search')
    @a.protected()
    def regulation_search():
        query=request.args.get('q','').strip()
        if not query or len(query)>200:abort(400)
        with a.db() as c:
            entries=[dict(row) for row in c.execute('''SELECT r.category,r.version,r.title,r.effective_date,r.source,r.created,r.body
                FROM regulation_versions r WHERE r.version=(SELECT MAX(v.version) FROM regulation_versions v WHERE v.category=r.category)''')]
        matches=[];registered=set()
        for entry in entries:
            registered.add(entry['category'])
            articles=[article for article in parse_articles(entry.pop('body')) if query.casefold() in (article['chapter']+'\n'+article['text']).casefold()]
            if articles:
                entry['category_name']=CATEGORIES[entry['category']];entry['articles']=articles;matches.append(entry)
        order={key:i for i,key in enumerate(CATEGORIES)}
        matches.sort(key=lambda x:order[x['category']])
        return jsonify(items=matches,missing=[{'category':key,'name':value} for key,value in CATEGORIES.items() if key not in registered])
    @a.app.get('/api/regulations/archive')
    @a.protected()
    def regulation_archive():
        query=request.args.get('q','').strip()
        if len(query)>200:abort(400)
        with a.db() as c:
            saved={row['category']:dict(row) for row in c.execute('''SELECT r.category,r.version,r.title,r.effective_date,r.source,r.created,r.body
                FROM regulation_versions r WHERE r.version=(SELECT MAX(v.version) FROM regulation_versions v WHERE v.category=r.category)''')}
        items=[];missing=[]
        for category,name in CATEGORIES.items():
            entry=saved.get(category)
            if entry:
                articles=parse_articles(entry.pop('body'));entry['sample']=False
            else:
                missing.append({'category':category,'name':name})
                entry={'category':category,'title':name,'version':0,'effective_date':'','source':'검색 기능 예시 · 실제 원문 아님','created':'','sample':True}
                articles=[{'key':key,'title':title,'text':text,'chapter':'샘플'} for key,title,text in SAMPLES.get(category,[])]
            for article in articles:
                if query and query.casefold() not in (article['chapter']+'\n'+article['title']+'\n'+article['text']).casefold():continue
                items.append({**entry,'category_name':name,'article':article})
        return jsonify(items=items,missing=missing)
    @a.app.get('/api/regulations/history')
    @a.protected()
    def regulation_history():
        category=request.args.get('category','');key=request.args.get('article','')
        if category not in CATEGORIES or not re.fullmatch(r'\d+(?:의\d+)?',key):abort(400)
        with a.db() as c:
            versions=[dict(row) for row in c.execute('SELECT version,title,effective_date,source,created,body FROM regulation_versions WHERE category=? ORDER BY version DESC',(category,))]
        result=[]
        for version in versions:
            matches=[item for item in parse_articles(version.pop('body')) if item['key']==key]
            for item in matches:result.append({**version,**item})
        return jsonify(items=result)
    @a.app.post('/api/regulations')
    @a.protected(True)
    def regulation_save():
        b=request.get_json(silent=True)
        if not isinstance(b,dict) or b.get('category') not in CATEGORIES or type(b.get('base_version')) is not int:abort(400)
        limits={'title':180,'effective_date':10,'source':500,'body':2000000}
        for key,limit in limits.items():
            if not isinstance(b.get(key),str) or len(b[key])>limit:abort(400)
        if not b['title'].strip() or not b['body'].strip():return jsonify(error='문서명과 원문을 입력하세요.'),400
        if b['effective_date']:
            try:dt.date.fromisoformat(b['effective_date'])
            except ValueError:abort(400)
        with a.db() as c:
            c.execute('BEGIN IMMEDIATE')
            version=c.execute('SELECT COALESCE(MAX(version),0) FROM regulation_versions WHERE category=?',(b['category'],)).fetchone()[0]
            if b['base_version']!=version:abort(409)
            c.execute('INSERT INTO regulation_versions VALUES(?,?,?,?,?,?,?,?)',(b['category'],version+1,b['title'].strip(),b['effective_date'],b['source'].strip(),b['body'],a.stamp(),a.session.get('user','')))
            a.log(c,'법령·규정 원문 등록',b['category'])
        return jsonify(ok=True,version=version+1)
    @a.app.post('/api/regulations/extract')
    @a.protected(True)
    def regulation_extract():
        uploaded=request.files.get('file')
        if not uploaded or not uploaded.filename:abort(400)
        filename=uploaded.filename.lower()
        if not filename.endswith(('.hwp','.docx')):return jsonify(error='HWP 또는 DOCX 파일을 선택하세요.'),400
        raw=uploaded.stream.read(FILE_LIMIT+1)
        if len(raw)>FILE_LIMIT:return jsonify(error='파일은 15MB 이하여야 합니다.'),413
        try:
            text=hwp_text(raw) if filename.endswith('.hwp') else docx_text(raw)
            if len(text)>2000000:raise ValueError('추출한 본문이 너무 깁니다.')
        except (ValueError, OSError, KeyError, EOFError) as exc:
            return jsonify(error=str(exc)[:200] or '파일을 읽지 못했습니다.'),400
        except Exception:
            return jsonify(error='파일을 읽지 못했습니다. 형식과 암호 설정을 확인하세요.'),400
        return jsonify(text=text)
