"""Title-first categories and conservative, bounded news grouping."""
import datetime as dt,re,unicodedata
from difflib import SequenceMatcher
CATEGORIES=['노사관계','경영(투자·실적)','안전','정책','기타']
CATEGORY_VERSION='2026-10-28.4'

def is_opinion(title):
    return bool(re.search(r'칼럼|사설|기고|논평|성명|담화문|입장문|국회의원|의원.*(?:촉구|호소|입장|주장|의견)|지역사회.*(?:대응|호소)|지역.*(?:상공회의소|경제계).*(?:촉구|호소)',title))

def category(title,description=''):
    if is_opinion(title):return '기타' 
    if re.search(r'기부|성금|기금.*전달|사회공헌',title):return '기타'
    if re.search(r'교통\s*안전|[Hh]형.*도로|빛나는\s*도로',title) and re.search(r'기부|기금|기탁|성금',title+' '+description):return '기타'
    def choose(text):
        for label,pattern in [
          ('안전',r'중대재해|산업재해|산재|안전사고|심정지|기계에낀|끼인|사망|숨져|숨진|끼[어여]|죽음|화재|폭발|추락|끼임|안전보건|안전점검'),
          ('노사관계',r'노사|임단협|단체교섭|교섭|파업|임금|단체협약|고용|감원|인력감축|구조조정|해고|희망퇴직|불법파견|원청교섭|정규직'),
          ('정책',r'관세|반덤핑|무역규제|전기요금|전력요금|탄소|배출권|산업정책|정부정책|법안|특구법|보조금'),
          ('경영(투자·실적)',r'실적|매출|영업이익|순이익|적자|흑자|실적발표|투자|증설|착공|인수|매각|경영|주가|배당|PBR|NDR|IR|공장|생산|설비|가동'),
          ('노사관계',r'노조|노동조합|조합원')]:
            if re.search(pattern,re.sub(r'\s+','',text),re.I):return label
        return None
    return choose(title) or choose(description) or '기타'

def normalized(title):
    t=unicodedata.normalize('NFKC',title).casefold()
    t=re.sub(r'^\s*\[[^\]]{1,25}\]\s*','',t)
    return re.sub(r'[^가-힣a-z0-9]','',t)
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
    if a['category']!=b['category']:return False
    try:
        elapsed=abs((dt.datetime.fromisoformat(a['published'])-dt.datetime.fromisoformat(b['published'])).total_seconds())
        if elapsed>72*3600:return False
    except (ValueError,TypeError):return False
    at,bt=a['title'],b['title'];ca,cb=companies(at),companies(bt);pa,pb=places(at),places(bt)
    if ca!=cb or (pa and pb and pa!=pb):return False
    # Commentary and responses keep their individual viewpoints.
    if is_opinion(at) or is_opinion(bt):
        sa,sb=opinion_speaker(at),opinion_speaker(bt)
        if sa and sb:
            if sa!=sb:return False
            return SequenceMatcher(None,normalized(at),normalized(bt)).ratio()>=.65
        return re.sub(r'\s+','',at)==re.sub(r'\s+','',bt)
    ka,kb=event_kind(a),event_kind(b)
    if ka and ka==kb and ca:
        da,db=event_date(a,ka),event_date(b,kb)
        if da and db and da!=db:return False
        if ka=='strike_notice' and da and da==db:return True
        if ka=='fatal_entrapment' and pa and pa==pb:
            if da and db:return da==db
            # Without a confirmed incident date, require matching headline text.
    # Numbers remain a guard for events that could not be resolved confidently.
    if set(re.findall(r'\d+(?:\.\d+)?',at))!=set(re.findall(r'\d+(?:\.\d+)?',bt)):return False
    ta,tb=topic(at),topic(bt)
    if ta and tb and ta!=tb:return False
    if ka!=kb and (ka or kb):return False
    na,nb=normalized(at),normalized(bt)
    if SequenceMatcher(None,na,nb).ratio()>=.80:return True
    da,db=normalized(a.get('description','')),normalized(b.get('description',''))
    if ca and len(da)>=60 and len(db)>=60 and SequenceMatcher(None,da,db).ratio()>=.82:return True
    return bool(ta and ta==tb and ca and pa and pa==pb and ta=='cleanup')
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

def group_articles(records):
    # Known incident dates form anchors first. Undated followups join only one possible issue.
    annotated=[(item,issue_info(item)) for item in records]
    groups=[];issue_groups={};fallback={}
    for item,info in sorted(annotated,key=lambda pair:bool(pair[1] and pair[1]['date']),reverse=True):
        if info:
            candidates=issue_groups.setdefault(info['key'],[])
            matches=[g for g in candidates if (not info['date'] or g['date']==info['date']) and (info.get('kind','사망사고')=='사망사고' or g.get('kind','사망사고') in ('사망사고',info.get('kind')))]
            target=matches[0] if len(matches)==1 else next((g for g in candidates if not g['date'] and not info['date'] and g.get('kind')==info.get('kind','사망사고')),None)
            if target is None:
                target=dict(items=[],date=info['date'],label=info['label'],kind=info.get('kind','사망사고'));groups.append(target);candidates.append(target)
            if target['kind']=='사망사고' and info.get('kind'):target['kind']=info['kind']
            target['items'].append(item)
        else:
            key=(item['category'],companies(item['title']))
            candidates=fallback.setdefault(key,[])
            target=next((g for g in candidates if any(similar(item,member) for member in g['items'])),None)
            if target is None:target=dict(items=[],date=None,label='');groups.append(target);candidates.append(target)
            target['items'].append(item)
    # A truncated excerpt may omit the site. Link only when exactly one current accident fits.
    for group in list(groups):
        if group['label']:continue
        for item in list(group['items']):
            title=item['title'];actor=issue_actor(item)
            if item['category']!='안전' or is_opinion(title) or not actor or re.search(r'\d+년\s*(?:간|\d+명)|사각지대',title):continue
            if not re.search(r'끼임|끼[어여]|기계에\s*낀|심정지|사망|숨',title):continue
            site=current_place(item);date=event_date(item,'fatal_entrapment')
            matches=[]
            for key,candidates in issue_groups.items():
                if key[0]!='safety' or key[1]!=actor or (site and tuple(sorted(site))!=key[2]):continue
                for candidate in candidates:
                    if date and candidate['date']!=date:continue
                    if re.search(r'끼임|끼[어여]|기계에\s*낀',title) and candidate.get('kind') not in ('끼임','사망사고'):continue
                    matches.append(candidate)
            if len(matches)==1:
                matches[0]['items'].append(item);group['items'].remove(item)
        if not group['items']:groups.remove(group)
    result=[]
    for issue in groups:
        group=sorted(issue['items'],key=lambda n:(n['published'],n['id']),reverse=True)
        representative=max(group,key=lambda n:(bool(n['important']),n['published'],n['id']))
        row=dict(representative)
        row['related_articles']=[dict(n,stage=news_stage(n)) for n in group if n['id']!=row['id']]
        row['timeline']=[dict({k:n[k] for k in ('id','title','published','url','publisher') if k in n},stage=news_stage(n)) for n in group]
        row['issue_label']=issue['label']+((' · '+issue['date'].strftime('%m/%d')) if issue['date'] else '')
        row['article_count']=len(group);row['group_latest']=group[0]['published']
        if not row.get('has_image'):
            image=next((n for n in group if n.get('has_image')),None)
            if image:row['image_id']=image['id']
        result.append(row)
    return sorted(result,key=lambda r:(r['group_latest'],r['id']),reverse=True)
