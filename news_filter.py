"""Conservative ER relevance rules, calibrated with user-labelled headlines."""
import re,unicodedata
VERSION='2026-10-29.4'
CORE=re.compile(r'현대\s*제철|포스코|POSCO',re.I)
DROP=re.compile(r'레드\s*엔젤스|여자\s*축구|양궁단|스틸러스|\[\s*특징주\s*\]|목표가\s*[↑↓]|부고|인사')
PROMOTION=re.compile(r'견학|장학금|성료|봉사\s*활동|기부|캠페인|모집|개선\s*활동')
OTHER_COMPANY=re.compile(r'현대\s*모비스|포스코\s*퓨처엠|현대\s*자동차|현대차|기아|현대\s*위아|현대\s*트랜시스|현대\s*로템|동국\s*제강|세아\s*제강')
def should_drop(title):return bool(DROP.search(unicodedata.normalize('NFKC',title or '')))
POSCO_ISSUES=re.compile(r'파업|노조|노동조합|교섭|임단협|결의대회|쟁의|고로|가동\s*중단|폐쇄|감산|구조조정|사망|폭발|화재|중대재해|철강\s*산단')
DIRECT=re.compile(r'현대\s*제철|포항\s*철강\s*산단')
def strict_drop(title,description='',category_name=None):
    title=unicodedata.normalize('NFKC',title or '')
    text=title+' '+unicodedata.normalize('NFKC',description or '')
    if re.search(r'포스코|POSCO',text,re.I) and not re.search(r'현대\s*제철',text) and not POSCO_ISSUES.search(text):return True
    return category_name=='기타' and not DIRECT.search(text)
def demoted(title,description=''):
    title=unicodedata.normalize('NFKC',title or '')
    description=unicodedata.normalize('NFKC',description or '')
    return bool(PROMOTION.search(title) or (OTHER_COMPANY.search(title) and not re.search(r'현대\s*제철',title) and re.search(r'현대\s*제철',description)))
ISSUE=re.compile(r'노조|노사|교섭|임단협|임금|단체협약|파업|고용|감원|인력\s*(?:감축|감소)|구조조정|해고|희망퇴직|정리해고|공장|생산|가동|폐쇄|폐업|투자|증설|산재|중대재해|사망|화재|관세|전기요금|전력비|탄소|실적|영업이익|매출|적자|흑자|경영|원청|하청|불법파견|노동|불황|위기|전환|매각|인수')
def classify(title,description=''):
    t=unicodedata.normalize('NFKC',title or '')
    d=unicodedata.normalize('NFKC',description or '')
    if should_drop(t):return 'exclude','스포츠·특징주·부고·인사 제외'
    if strict_drop(t,d):return 'exclude','포스코 핵심 현안 이외 기사 제외'
    # Roundups stay excluded even when the excerpt mentions the company.
    if re.search(r'오늘의\s*주요\s*일정|오늘의\s*경기|손바닥\s*뉴스|위클립|\d+월\s*\d+주\s*주요\s*제조업\s*전망|\[산업소식\]|금주의.*의회',t):
        return 'exclude','종합 일정·뉴스 모음·정기 전망'
    if demoted(t,d):return 'keep','낮은 우선순위 · 단순 행사·홍보 또는 타사 중심 기사'
    if re.search(r'포스코|POSCO',t+' '+d,re.I) and POSCO_ISSUES.search(t+' '+d):return 'keep','포스코 핵심 현안'
    # Keep actual industrial issues, including columns about POSCO labor relations.
    if CORE.search(t) and ISSUE.search(t):return 'keep','현대제철·포스코의 노사·경영·산업 현안'
    if re.search(r'철강|제철|조선',t) and re.search(r'인력\s*감축|감원|고용|구조조정|해고|희망퇴직|임단협|교섭|파업|불황|관세|전기요금|탄소',t):
        return 'keep','철강 관련 고용·교섭·산업 환경'
    if re.search(r'축구|양궁|WK리그|K리그|여자\s*축구|올림픽|스포츠|우승|골잡이',t):return 'exclude','스포츠 경기·선수 소식'
    if re.search(r'바다에\s*빠진.*구조|시민.*구조.*(?:감사장|표창)|인명\s*구조.*(?:미담|표창|감사장)',t):return 'exclude','인명 구조 미담·표창'
    if re.search(r'교육청|교육지원청|초등학교|고교\s*캠퍼스|중1\s*대상|세대\s*잇는|어르신.*선생님|구의회|군의회',t):return 'exclude','일반 지역·교육·의회 소식'
    if re.search(r'코스피|코스닥|오늘의\s*증시|증시.*마감',t) and not CORE.search(t):return 'exclude','시장 전체 시황·다른 종목 소식'
    if re.search(r'폴리텍',t):
        if CORE.search(t) and re.search(r'채용|인력|양성|직업|훈련|협약',t):return 'review','회사 인력 양성과 연결 가능 · 확인 필요'
        return 'exclude','일반 대학·교육 홍보'
    if not CORE.search(t) and re.search(r'공장.*(?:준공|인증)|(?:준공|인증).*공장',t):return 'exclude','다른 업체의 공장 준공·인증'
    if CORE.search(t):return 'review','관련 회사가 제목에 있지만 업무 현안인지 확인 필요'
    if CORE.search(d) and ISSUE.search(t+' '+d):return 'review','본문 발췌에만 관련 회사 등장 · 확인 필요'
    return 'exclude','제목·발췌문에서 업무 관련 근거 부족'
