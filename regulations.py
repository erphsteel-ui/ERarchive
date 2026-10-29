"""Offline, versioned archive of administrator-supplied legal and workplace texts."""
import datetime as dt
import re
from flask import abort, jsonify, request

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
