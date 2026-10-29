"""Title-first categories and conservative, bounded news grouping."""
import datetime as dt,re,unicodedata
from difflib import SequenceMatcher
from news_filter import demoted
CATEGORIES=['노사관계','경영(투자·실적)','안전','정책','기타']
CATEGORY_VERSION='2026-10-29.2'
CATEGORY_PATTERNS=[
 ('안전',r'사망|숨져|숨진|끼임|끼[어여]|기계에\s*낀|추락|질식|화재|폭발|중대재해|산재|심정지|작업\s*중지|고용노동부\s*감독'),
 ('노사관계',r'노조|노동조합|파업|교섭|임단협|임금\s*협상|투쟁|결의대회|지회|비정규직|하청\s*노동자|불법파견|쟁의|노사|해고|구조조정|인력\s*감축'),
 ('정책',r'노란봉투법|노동특례|국정감사|국감|관세|반덤핑|탄소중립|수출규제|전기요금|산업용\s*전기|법안|정부|기후에너지'),
 ('경영(투자·실적)',r'실적|영업이익|매출|신용등급|투자|전기로|제철소\s*건설|가동\s*중단|공장\s*폐쇄|감산|인수|매각|판가|열연|후판|철근')]
def is_opinion(title):
    return bool(re.search(r'칼럼|사설|기고|논평|성명|담화문|입장문',title))
def category(title,description=''):
    title=unicodedata.normalize('NFKC',title or '');description=unicodedata.normalize('NFKC',description or '')
    if demoted(title,description):return '기타'
    # Title matches are decisive, in the specified safety-to-business order.
    for label,pattern in CATEGORY_PATTERNS:
        if re.search(pattern,title,re.I):return label
    scores={label:3*len(re.findall(pattern,title,re.I))+len(re.findall(pattern,description,re.I)) for label,pattern in CATEGORY_PATTERNS}
    best=max(scores.values(),default=0)
    return next((label for label,_ in CATEGORY_PATTERNS if scores[label]==best),'기타') if best else '기타'

ALIASES=[(r'국힘','국민의힘'),(r'노조','노동조합'),(r'임단협','임금협상'),(r'포항제철소','포항'),(r'하청노동자','하청 노동자')]
COMMON=re.compile(r'현대\s*제철|포스코|노동조합|포항|당진|인천|순천|파업|공장|제철소|투자|프로젝트|계획|기자|뉴스|관련|발표|보도|대한|위한|에서|으로|했다|한다')
def normalized_words(title):
    text=unicodedata.normalize('NFKC',title or '').casefold()
    text=re.sub(r'\[[^\]]*\]',' ',text)
    for pattern,replacement in ALIASES:text=re.sub(pattern,replacement,text)
    return text
def normalized(title):return re.sub(r'[^가-힣a-z0-9]','',normalized_words(title))
def title_features(title):
    text=COMMON.sub(' ',normalized_words(title))
    words=re.findall(r'[가-힣]{2,}|[a-z]{2,}|\d+(?:\.\d+)?(?:명|년|조|억|월|일|%)?',text)
    features=set()
    for word in words:
        features.add('w:'+word)
        if len(word)>2 and not re.search(r'\d',word):features.update('b:'+word[i:i+2] for i in range(len(word)-1))
    return features
def title_similarity(left,right):
    a,b=title_features(left),title_features(right)
    def weight(feature):return 4 if feature.startswith('w:') and re.search(r'\d',feature) else 2 if feature.startswith('w:') else 1
    return sum(map(weight,a&b))/sum(map(weight,a|b)) if a and b else 0.0
def title_overlap(left,right):
    a,b=title_features(left),title_features(right)
    return len(a&b)/len(a|b) if a and b else 0.0
def named_person(title):
    text=normalized_words(title)
    match=re.search(r'([가-힣]{2,4})\s*(?:국회의원|의원|지회장|위원장|국민의힘)',text)
    if match:return match.group(1)
    for name in ('최병욱','이상휘'):
        if name in text:return name
    return ''
def headline_subject(title):
    person=named_person(title)
    if person:return person
    text=COMMON.sub(' ',normalized_words(title))
    generic={'노사관계','안전사고','실적발표','산업계','현대자동차','기업소식'}
    return next((word for word in re.findall(r'[가-힣]{3,}|[a-z]{3,}',text) if word not in generic),'')
def number_units(title):
    return {(unit,value) for value,unit in re.findall(r'(\d+(?:\.\d+)?)\s*(년간|명|조|억|월|일|%)',title)}
def companies(title):
    title=title.replace('현대자동차','현대차').replace('기아자동차','기아').replace('현대케피코','케피코')
    return frozenset(re.findall(r'현대제철|포스코|현대차|기아|현대모비스|현대위아|현대로템|현대트랜시스|동국제강|세아제강|케피코',title))
def places(title):return frozenset(re.findall(r'포항|당진|인천|순천|광양|루이지애나',title))
def topic(title):
    for key,pattern in [('cleanup',r'환경\s*정화|환경\s*정비|쓰레기\s*줍|플로깅'),('earnings',r'실적\s*발표|분기\s*실적'),('tentative',r'잠정\s*합의'),('settlement',r'교섭.*타결|임단협.*타결'),('strike_notice',r'파업.*예고'),('strike_start',r'파업.*돌입')]:
        if re.search(pattern,title):return key
    return ''
def event_date(item,kind):
    """Resolve a reported incident/announced strike date, not arbitrary headline numbers."""
    text=item['title']+' '+item.get('description','')
    published=dt.datetime.fromisoformat(item['published']).astimezone(dt.timezone(dt.timedelta(hours=9))).date()
    patterns=([r'(?:오는\s*|다음\s*달\s*|내달\s*)?(\d{1,2})월\s*(\d{1,2})일'] if kind=='strike_notice' else [])
    if kind=='strike_notice':
        match=re.search(r'(?:다음\s*달|내달)\s*(\d{1,2})일',text)
        if match:
            month=published.month%12+1;year=published.year+(published.month==12)
            try:return dt.date(year,month,int(match[1]))
            except ValueError:return None
    for pattern in patterns:
        match=re.search(pattern,text)
        if match:
            try:return dt.date(published.year,int(match[1]),int(match[2]))
            except ValueError:return None
    if kind=='fatal_entrapment':
        # Only an incident clause supplies the incident date. A press conference date is not it.
        clauses=re.split(r'[.!?。](?:\s|$)',item.get('description',''))
        for clause in clauses:
            if not re.search(r'끼|사망|숨|심정지|사고가?\s*발생',clause):continue
            # Historical cases mentioned in a followup are not the current incident.
            years=[int(y) for y in re.findall(r'(20\d{2})년',clause)]
            if years and any(y!=published.year for y in years):continue
            match=re.search(r'(?:(\d{1,2})월\s*)?(\d{1,2})일',clause)
            if match:
                try:
                    value=dt.date(published.year,int(match[1]) if match[1] else published.month,int(match[2]))
                    if value>published and not match[1]:
                        prev=published.replace(day=1)-dt.timedelta(days=1);value=prev.replace(day=int(match[2]))
                    if 0<=(published-value).days<=31:return value
                except ValueError:pass
            if '어제' in clause:return published-dt.timedelta(days=1)
            if '오늘' in clause or '이날' in clause:return published
    return None

def event_kind(item):
    title=item['title'];text=title+' '+item.get('description','')
    if re.search(r'잠정\s*합의|타결|파업\s*(?:철회|중단)|원인\s*발표|수사\s*결과',title):return ''
    if re.search(r'파업.*(?:돌입|시작)',title) and not re.search(r'예고|선언|내달|다음\s*달|오는',title):return 'strike_start'
    if re.search(r'파업',title) and re.search(r'예고|선언|내달|다음\s*달|오는\s*\d',text):return 'strike_notice'
    if re.search(r'끼[어여]|끼임|협착',text) and re.search(r'숨져|숨진|사망',text):return 'fatal_entrapment'
    return ''

def similar(a,b):
    try:
        elapsed=abs((dt.datetime.fromisoformat(a['published'])-dt.datetime.fromisoformat(b['published'])).total_seconds())
        if elapsed>10*24*3600:return False
    except (ValueError,TypeError):return False
    topic_a,topic_b=macro_topic(a),macro_topic(b)
    if topic_a and topic_a==topic_b:return True
    if elapsed>72*3600:return False
    at,bt=a['title'],b['title'];ca,cb=companies(at),companies(bt);pa,pb=places(at),places(bt)
    if ca and cb and ca.isdisjoint(cb):return False
    if pa and pb and pa.isdisjoint(pb):return False
    if is_opinion(at)!=is_opinion(bt):return False
    if is_opinion(at) and is_opinion(bt):
        ma=re.search(r'\[([^\]]+)\]',at);mb=re.search(r'\[([^\]]+)\]',bt)
        if ma and mb and ma.group(1)!=mb.group(1):return False
    person_a,person_b=named_person(at),named_person(bt)
    if person_a and person_b and person_a!=person_b:return False
    na,nb=number_units(at),number_units(bt)
    for unit in {u for u,_ in na}&{u for u,_ in nb}:
        if {v for u,v in na if u==unit}.isdisjoint({v for u,v in nb if u==unit}):return False
    ka,kb=event_kind(a),event_kind(b)
    if ka and kb and ka==kb:
        da,db=event_date(a,ka),event_date(b,kb)
        if da and db and da!=db:return False
        if da and db and da==db and ca and cb and not ca.isdisjoint(cb) and (not pa or not pb or not pa.isdisjoint(pb)):return True
    # A specific local event can bridge different wording, but never a generic labor topic.
    if ca and cb and not ca.isdisjoint(cb) and pa and pb and pa==pb:
        common_a,common_b=common_event(a),common_event(b)
        if common_a and common_b and common_a['key']==common_b['key'] and common_a['key'][0]=='community':return True
        if topic(at)==topic(bt)=='cleanup':return True
    score=title_similarity(at,bt)
    if a.get('category')!=b.get('category') and score<.65:return False
    if score>=.45:return True
    af,bf=title_features(at),title_features(bt)
    shared={x for x in af&bf if x.startswith('w:') and person_a not in x}
    return bool(person_a and person_a==person_b and len(shared)>=2)
def issue_actor(item):
    title=companies(item['title'])
    if len(title)==1:return next(iter(title))
    if len(title)>1:return ''
    lead=companies(item.get('description','')[:250])
    return next(iter(lead)) if len(lead)==1 else ''

def current_place(item):
    explicit=places(item['title'])
    if explicit:return explicit
    lead=item.get('description','')[:350]
    year=dt.datetime.fromisoformat(item['published']).year
    # Do not turn a historic example (e.g. 2024 Incheon) into the current event's location.
    before=re.split(r'(?:20\d{2}년|지난해|재작년)',lead)[0]
    return places(before)

def opinion_speaker(title):
    match=re.search(r'([가-힣]{2,4})\s*(?:국회)?의원',title)
    return match[1] if match else ''

def common_event(item):
    title=item['title'];text=title+' '+item.get('description','');actor=issue_actor(item)
    if not actor:return None
    site=current_place(item)
    if re.search(r'교통\s*안전|[Hh]형.*도로|빛나는\s*도로',text) and re.search(r'기부|기금|전달|기탁|성금',text) and len(site)==1:
        return dict(key=('community',actor,tuple(sorted(site)),'교통안전 기부'),date=None,label=actor+' '+next(iter(site))+' 교통안전 기부')
    if re.search(r'실적|매출|영업이익',title):
        q=re.search(r'([1-4])\s*분기',title);y=re.search(r'(20\d{2})년',title)
        if q:
            year=y[1] if y else str(dt.datetime.fromisoformat(item['published']).year)
            return dict(key=('earnings',actor,year,q[1]),date=None,label=actor+' '+year+'년 '+q[1]+'분기 실적')
    return None

def issue_info(item):
    if is_opinion(item['title']):return None
    title=item['title'];body=item.get('description','');text=title+' '+body
    actor=issue_actor(item)
    if not actor:return None
    common=common_event(item)
    if common:return common
    if item['category']=='노사관계' and re.search(r'임금|임단협|교섭|파업|잠정합의|성과급',title):
        # Different unions and subcontract disputes must not be conflated.
        union='하청' if re.search(r'하청|비정규직|원청교섭',title) else ('금속노조' if re.search(r'금속노조',text) and not re.search(r'금속노련',text) else '일반')
        site=places(title) if actor=='현대제철' else frozenset()
        return dict(key=('labor',actor,union,tuple(sorted(site))),date=None,label=actor+' 임금교섭·파업 동향')
    if item['category']=='안전' and re.search(r'사망|숨져|숨진|죽음|끼임|끼[어여]|기계에\s*낀|심정지',text):
        site=current_place(item)
        if len(site)!=1:return None
        kind='끼임' if re.search(r'끼임|끼[어여]|협착|기계에\s*낀',text) else ('추락' if re.search(r'추락|떨어져',text) else ('화재' if '화재' in text else '사망사고'))
        date=event_date(item,'fatal_entrapment')
        return dict(key=('safety',actor,tuple(sorted(site))),kind=kind,date=date,label=actor+' '+next(iter(site))+' '+kind+' 사고')
    return None

def news_stage(item):
    title=item['title']
    for label,pattern in [('파업 철회',r'파업.*철회'),('파업 중단',r'파업.*중단'),('잠정 합의',r'잠정\s*합의'),('타결',r'타결'),('수사 결과',r'수사.*결과'),('원인 발표',r'원인.*발표'),('후속 대응',r'촉구|반발|대책|사과|책임|감독')]:
        if re.search(pattern,title):return label
    kind=event_kind(item)
    return {'strike_notice':'파업 예고','strike_start':'파업 돌입','fatal_entrapment':'사고 보도'}.get(kind,'관련 보도')

def macro_topic(item):
    text=item['title']+' '+item.get('description','')
    actor=issue_actor(item)
    if actor=='포스코' and item.get('category')=='노사관계' and re.search(r'파업|임단협|교섭|노조|노동조합',text):return ('posco_labor','포스코 임금교섭·무기한 파업 동향')
    if actor=='현대제철' and item.get('category')=='안전' and re.search(r'사망|숨져|숨진|끼임|산재|중대재해',text):return ('hyundai_safety','현대제철 안전·중대재해 사고')
    return None

def group_articles(records):
    # The representative is fixed first: every member must directly match it.
    ordered=sorted(records,key=lambda n:(bool(n.get('important')),n['published'],n['id']),reverse=True)
    groups=[]
    for item in ordered:
        target=next((g for g in groups if similar(item,g[0])),None)
        if target is None:groups.append([item])
        else:target.append(item)
    result=[]
    for group in groups:
        representative=group[0];ordered_group=sorted(group,key=lambda n:(n['published'],n['id']),reverse=True)
        row=dict(representative)
        row['related_articles']=[dict(n,stage=news_stage(n)) for n in ordered_group if n['id']!=row['id']]
        row['timeline']=[dict({k:n[k] for k in ('id','title','published','url','publisher') if k in n},stage=news_stage(n)) for n in ordered_group]
        macro=macro_topic(representative)
        row['issue_label']=macro[1] if macro and len(group)>1 else '';row['article_count']=len(group);row['group_latest']=ordered_group[0]['published']
        if not row.get('has_image'):
            image=next((n for n in ordered_group if n.get('has_image')),None)
            if image:row['image_id']=image['id']
        result.append(row)
    return sorted(result,key=lambda r:(r['group_latest'],r['id']),reverse=True)
