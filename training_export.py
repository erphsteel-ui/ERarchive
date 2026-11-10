"""Administrator-reviewed classification examples, exported on demand."""
import io,json,datetime
from flask import abort,jsonify,request,send_file

def install(a):
    with a.db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS classification_review (doc TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE, version INTEGER NOT NULL, note TEXT NOT NULL, reviewed_at TEXT NOT NULL)')

    @a.app.get('/api/classification-review/<did>')
    @a.protected(True)
    def review_get(did):
        with a.db() as c:
            doc=c.execute('SELECT version FROM documents WHERE id=?',(did,)).fetchone()
            if not doc:abort(404)
            row=c.execute('SELECT version,note,reviewed_at FROM classification_review WHERE doc=?',(did,)).fetchone()
            return jsonify(review=dict(row) if row else None,current_version=doc['version'])

    @a.app.post('/api/classification-review/<did>')
    @a.protected(True)
    def review_set(did):
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or type(data.get('version')) is not int or not isinstance(data.get('note'),str) or len(data['note'])>5000 or type(data.get('reviewed')) is not bool:abort(400)
        with a.db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT version FROM documents WHERE id=?',(did,)).fetchone()
            if not row:abort(404)
            if row['version']!=data['version']:abort(409)
            if data['reviewed']:
                c.execute('INSERT INTO classification_review VALUES(?,?,?,?) ON CONFLICT(doc) DO UPDATE SET version=excluded.version,note=excluded.note,reviewed_at=excluded.reviewed_at',(did,row['version'],data['note'],a.stamp()))
            else:c.execute('DELETE FROM classification_review WHERE doc=?',(did,))
            a.log(c,'분류 정답 확인' if data['reviewed'] else '분류 정답 확인 취소',did)
        return jsonify(ok=True)

    @a.app.get('/api/classification-export')
    @a.protected(True)
    def classification_export():
        with a.db() as c:
            c.execute('BEGIN')
            docs=c.execute('SELECT id,meta,created,updated,version FROM documents ORDER BY created,id').fetchall()
            pages={}
            for p in c.execute('''SELECT p.doc,p.id,p.position,p.text,p.status,p.hash,o.text AS original_text,o.source AS original_source
                FROM pages p LEFT JOIN page_original o ON o.page=p.id ORDER BY p.doc,p.position,p.id'''):
                entry=dict(p);doc=entry.pop('doc');pages.setdefault(doc,[]).append(entry)
            reviews={row['doc']:dict(row) for row in c.execute('SELECT * FROM classification_review')}
            records=[]
            for doc in docs:
                meta=json.loads(doc['meta']);rev=reviews.get(doc['id']);version=doc['version']
                state='reviewed' if rev and rev['version']==version else 'changed_after_review' if rev else 'unreviewed'
                records.append({'id':doc['id'],'created':doc['created'],'updated':doc['updated'],'version':version,
                    'review':{'status':state,'reviewed_version':rev['version'] if rev else None,'reviewed_at':rev['reviewed_at'] if rev else None,'note':rev['note'] if rev else ''},
                    'labels':{'category_explicit':meta.get('category',''),'categories_current':a.categories_for(meta),'publishers':meta.get('publishers',[]),'title':meta.get('title',''),'kind':meta.get('kind',''),'date':meta.get('date',''),'issue':meta.get('issue',''),'tags':meta.get('tags',[]),'state':meta.get('state','')},
                    'classification_reason':meta.get('classification_reason',''),'document_note':meta.get('note',''),'pages':pages.get(doc['id'],[])})
        payload={'schema':'erarchive.classification.v1','exported_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'description':'관리자 확인 상태는 review.status를 참고하세요. 확인 후 수정된 자료는 재확인이 필요합니다. 자동 계산된 categories_current와 직접 지정한 category_explicit을 구분합니다. 원본 이미지와 계정 정보는 포함하지 않습니다.',
            'records':records}
        data=json.dumps(payload,ensure_ascii=False,indent=2).encode('utf-8')
        return send_file(io.BytesIO(data),mimetype='application/json',as_attachment=True,download_name='erarchive_classification_examples.json')
