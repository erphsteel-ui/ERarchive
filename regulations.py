"""Current regulation documents and transactional article search index."""
import json,secrets,io,zipfile
from xml.etree import ElementTree as ET
from flask import abort, jsonify, request
from regulations_index import parse_document,normalize,number_key,snippet

CATEGORIES={
 'labor_act':'근로기준법','union_act':'노동조합법','work_technical':'기술직 취업규칙',
 'agreement':'단체협약','work_general':'일반직 취업규칙','pohang_rules':'노동조합 규칙','pohang_bylaws':'노동조합 세칙',
}
LEGACY_SAFE={'labor_act':'labor_act','union_act':'union_act','agreement':'agreement'}
LIMIT=2000000

def store_document(c,category,body,parts,updated,token):
    c.execute('INSERT INTO regulation_documents(category,body,updated,token) VALUES(?,?,?,?) ON CONFLICT(category) DO UPDATE SET body=excluded.body,updated=excluded.updated,token=excluded.token',(category,body,updated,token))
    c.execute('DELETE FROM regulation_articles WHERE category=?',(category,))
    for part in parts:
        c.execute('INSERT INTO regulation_articles(category,position,kind,chapter,section,number,title,body,search_title,search_body,needs_review,structure) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(
            category,part['order'],part['kind'],part['chapter'],part['section'],part['number'],part['title'],part['text'],normalize(part['title']+' '+part['number']),normalize(part['text']+' '+part['chapter']+' '+part['section']),int(part['review']),json.dumps(part['components'],ensure_ascii=False)))

def install(a):
    with a.db() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS regulation_documents(category TEXT PRIMARY KEY,body TEXT NOT NULL,updated TEXT NOT NULL,token TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS regulation_articles(category TEXT NOT NULL REFERENCES regulation_documents(category) ON DELETE CASCADE,position INTEGER NOT NULL,kind TEXT NOT NULL,chapter TEXT NOT NULL,section TEXT NOT NULL,number TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,search_title TEXT NOT NULL,search_body TEXT NOT NULL,needs_review INTEGER NOT NULL,PRIMARY KEY(category,position));''')
        if 'structure' not in {row[1] for row in c.execute('PRAGMA table_info(regulation_articles)')}:
            c.execute("ALTER TABLE regulation_articles ADD COLUMN structure TEXT NOT NULL DEFAULT '[]'")
        legacy=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='regulation_versions'").fetchone()
        if legacy:
            for old,new in LEGACY_SAFE.items():
                if c.execute('SELECT 1 FROM regulation_documents WHERE category=?',(new,)).fetchone():continue
                row=c.execute('SELECT body,created FROM regulation_versions WHERE category=? ORDER BY version DESC LIMIT 1',(old,)).fetchone()
                if row and row['body'] and row['body'].strip():
                    try:parts=parse_document(row['body'])
                    except ValueError:continue
                    store_document(c,new,row['body'],parts,row['created'] or '',secrets.token_hex(16))
        # Legacy versions are intentionally preserved for backup and ambiguous migration.
    def checked(body):
        if not isinstance(body,str) or len(body)>LIMIT or not body.strip():raise ValueError('원문을 입력하세요. 최대 200만 글자까지 가능합니다.')
        return parse_document(body)
    @a.app.get('/api/regulations/document')
    @a.protected(True)
    def regulation_document():
        category=request.args.get('category','')
        if category not in CATEGORIES:abort(400)
        with a.db() as c:row=c.execute('SELECT body,updated,token FROM regulation_documents WHERE category=?',(category,)).fetchone()
        return jsonify(document=dict(row) if row else None)
    @a.app.get('/api/regulations/legacy')
    @a.protected(True)
    def legacy_documents():
        with a.db() as c:
            if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='regulation_versions'").fetchone():return jsonify(items=[])
            result=[dict(row) for row in c.execute('''SELECT category,title,body,created FROM regulation_versions r WHERE (category NOT IN ('labor_act','union_act','agreement') OR NOT EXISTS (SELECT 1 FROM regulation_documents d WHERE d.category=r.category)) AND version=(SELECT MAX(version) FROM regulation_versions WHERE category=r.category) ORDER BY category''')]
        return jsonify(items=result)
    @a.app.post('/api/regulations/extract')
    @a.protected(True)
    def regulation_extract():
        upload=request.files.get('file')
        if not upload:return jsonify(error='파일을 선택하세요.'),400
        ext=(upload.filename or '').lower().rsplit('.',1)[-1]
        if ext not in ('txt','docx'):return jsonify(error='.txt 또는 .docx 파일만 지원합니다. HWP/DOC는 텍스트를 복사해 붙여넣으세요.'),400
        data=upload.stream.read(10*1024*1024+1)
        if len(data)>10*1024*1024:return jsonify(error='파일은 최대 10MB입니다.'),413
        try:
            if ext=='txt':
                try:text=data.decode('utf-8-sig')
                except UnicodeDecodeError:text=data.decode('cp949')
            else:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    info=archive.getinfo('word/document.xml')
                    if info.file_size>12*1024*1024:raise ValueError('압축 해제된 문서가 너무 큽니다.')
                    xml=archive.read(info)
                    if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:raise ValueError('지원하지 않는 XML 문서입니다.')
                    root=ET.fromstring(xml);ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                    text='\n'.join(''.join(node.text or '' if node.tag.endswith('}t') else '\t' if node.tag.endswith('}tab') else '\n' for node in para.iter() if node.tag.rsplit('}',1)[-1] in ('t','tab','br','cr')) for para in root.findall('.//w:p',ns))
            checked(text)
        except (ValueError,UnicodeError,zipfile.BadZipFile,KeyError,ET.ParseError,RuntimeError,NotImplementedError):
            return jsonify(error='텍스트를 추출할 수 없습니다. 파일 형식 또는 인코딩을 확인하고 텍스트 붙여넣기를 사용하세요.'),400
        return jsonify(text=text)
    @a.app.post('/api/regulations/preview')
    @a.protected(True)
    def regulation_preview():
        b=request.get_json(silent=True)
        if not isinstance(b,dict) or b.get('category') not in CATEGORIES:abort(400)
        try:parts=checked(b.get('body'))
        except ValueError as exc:return jsonify(error=str(exc)),400
        return jsonify(items=parts,article_count=sum(p['kind']=='article' for p in parts),review_count=sum(p['review'] for p in parts))
    @a.app.post('/api/regulations/save')
    @a.protected(True)
    def regulation_save_current():
        b=request.get_json(silent=True)
        if not isinstance(b,dict) or b.get('category') not in CATEGORIES or not isinstance(b.get('token'),str):abort(400)
        manual=b.get('mode')=='manual'
        if manual:
            title=b.get('title')
            if not isinstance(title,str) or not title.strip() or len(title)>200:return jsonify(error='제목을 200자 이내로 입력하세요.'),400
        try:parts=checked(b.get('body'))
        except ValueError as exc:return jsonify(error=str(exc)),400
        with a.db() as c:
            c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT token FROM regulation_documents WHERE category=?',(b['category'],)).fetchone()
            if b['token']!=(old['token'] if old else ''):abort(409)
            updated=a.stamp();token=secrets.token_hex(16)
            if manual:
                # Append one manual item, preserving the existing category document and index.
                current=c.execute('SELECT body FROM regulation_documents WHERE category=?',(b['category'],)).fetchone()
                old_body=current['body'] if current else ''
                combined=old_body+('\n\n' if old_body else '')+title.strip()+'\n'+b['body']
                if len(combined)>LIMIT:return jsonify(error='카테고리 원문은 최대 200만 글자입니다.'),400
                c.execute('INSERT INTO regulation_documents VALUES(?,?,?,?) ON CONFLICT(category) DO UPDATE SET body=excluded.body,updated=excluded.updated,token=excluded.token',(b['category'],combined,updated,token))
                position=c.execute('SELECT COALESCE(MAX(position),-1)+1 FROM regulation_articles WHERE category=?',(b['category'],)).fetchone()[0]
                text=title.strip()+'\n'+b['body']
                c.execute('INSERT INTO regulation_articles VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(b['category'],position,'manual','','','',title.strip(),text,normalize(title),normalize(text),0,'[]'))
            else:
                store_document(c,b['category'],b['body'],parts,updated,token)
            a.log(c,'법령·규정 원문 저장',b['category'])
        return jsonify(ok=True,updated=updated)
    @a.app.get('/api/regulations/archive')
    @a.protected()
    def regulation_archive_current():
        q=request.args.get('q','').strip();category=request.args.get('category','')
        if len(q)>200 or (category and category not in CATEGORIES):abort(400)
        normalized=normalize(q);number=number_key(q);counts={key:0 for key in CATEGORIES};results=[]
        with a.db() as c:
            records=[dict(r) for r in c.execute('SELECT a.*,d.updated FROM regulation_articles a JOIN regulation_documents d ON d.category=a.category')]
        order={key:i for i,key in enumerate(CATEGORIES)}
        for item in records:
            if item['category'] not in CATEGORIES or item['kind'] not in ('article','manual'):continue
            if normalized:
                number_match=bool(number and item['number']==number)
                title_match=number_match or normalized in item['search_title']
                if not title_match and normalized not in item['search_body']:continue
                rank=0 if title_match else 1
            else:rank=0
            counts[item['category']]+=1
            if category and item['category']!=category:continue
            item['category_name']=CATEGORIES[item['category']];item['preview']=snippet(item['body'],q) if normalized and rank else snippet(item['body'],'');item['_rank']=rank
            del item['search_title'],item['search_body'];results.append(item)
        results.sort(key=lambda x:(x['_rank'],order[x['category']],x['position']))
        for item in results:del item['_rank']
        return jsonify(items=results,counts=counts,total=sum(counts.values()))
