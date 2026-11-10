"""National law API: fetch validated current law XML and prepare a review copy."""
import os,re,urllib.parse,urllib.request,urllib.error
from xml.etree import ElementTree as ET

LAWS={'labor_act':('001872','근로기준법'),'union_act':('000143','노동조합 및 노동관계조정법')}
URL='https://www.law.go.kr/DRF/lawService.do'
MAX_BYTES=8*1024*1024
class LawApiError(Exception):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def prepare_law(category,xml):
 if category not in LAWS:raise LawApiError('지원하지 않는 법령입니다.')
 if len(xml)>MAX_BYTES or re.search(br'<!\s*(?:DOCTYPE|ENTITY)',xml,re.I):raise LawApiError('지원하지 않는 XML 응답입니다.')
 try:root=ET.fromstring(xml)
 except ET.ParseError:raise LawApiError('법령정보센터 XML을 읽을 수 없습니다. 인증값과 API 신청 상태를 확인하세요.')
 def tag(node):return node.tag.rsplit('}',1)[-1] if isinstance(node.tag,str) else ''
 def text(node):return ''.join(node.itertext()).strip()
 def first(name):return next((text(x) for x in root.iter() if tag(x)==name and text(x)), '')
 expected_id,expected_name=LAWS[category];actual_id=first('법령ID');name=first('법령명_한글')
 if not actual_id.isdigit() or int(actual_id)!=int(expected_id) or re.sub(r'\s+','',name)!=re.sub(r'\s+','',expected_name):raise LawApiError('요청한 법령과 응답의 법령명 또는 ID가 다릅니다.')
 clauses=[x for x in root.iter() if tag(x)=='조문단위']
 if not clauses:raise LawApiError('응답에 조문이 없습니다. 인증값과 API 신청 상태를 확인하세요.')
 lines=[];content_tags={'조문내용','항내용','호내용','목내용','부칙내용','별표내용','별표제목','편장절관내용','전문내용'}
 for node in root.iter():
  if tag(node) in content_tags:
   value=text(node)
   if value:lines.append(value)
 if not any(tag(n)=='조문내용' and text(n) for n in root.iter()):raise LawApiError('응답에서 법령 본문을 확인할 수 없습니다.')
 result='\n'.join(lines)
 if not result or len(result)>2000000:raise LawApiError('법령 본문이 비어 있거나 저장 가능 크기를 초과합니다.')
 return {'body':result,'law_id':actual_id,'law_name':name,'effective_date':first('시행일자'),'promulgation_date':first('공포일자'),'promulgation_number':first('공포번호'),'article_count':len(clauses)}

def validate_oc(oc):
 if not isinstance(oc,str) or not re.fullmatch(r'[A-Za-z0-9._@+\-]{1,100}',oc.strip()):raise LawApiError('API 인증값 형식을 확인하세요.')
 return oc.strip()

def fetch_law(category,oc=None):
 if category not in LAWS:raise LawApiError('지원하지 않는 법령입니다.')
 oc=(oc or os.environ.get('LAW_API_OC','')).strip()
 if not oc:raise LawApiError('법령 등록/관리에서 API 인증값을 먼저 저장하세요. (LAW_API_OC 환경변수도 사용 가능)')
 oc=validate_oc(oc)
 params=urllib.parse.urlencode({'OC':oc,'target':'eflaw','ID':LAWS[category][0],'type':'XML'})
 request=urllib.request.Request(URL+'?'+params,headers={'User-Agent':'ERArchive/1.0','Accept':'application/xml,text/xml'})
 try:
  with urllib.request.build_opener(NoRedirect).open(request,timeout=20) as response:xml=response.read(MAX_BYTES+1)
 except (urllib.error.URLError,TimeoutError,OSError):raise LawApiError('법령정보센터 연결에 실패했습니다. 네트워크와 인증값을 확인하세요.')
 result=prepare_law(category,xml);return result,xml

def search_laws(query, oc):
 """Search law titles and return links to the official site."""
 if not isinstance(query,str) or not query.strip() or len(query)>100:raise LawApiError('검색어를 100자 이하로 입력하세요.')
 oc=validate_oc(oc)
 params=urllib.parse.urlencode({'OC':oc,'target':'law','type':'XML','query':query.strip(),'display':'20'})
 req=urllib.request.Request('https://www.law.go.kr/DRF/lawSearch.do?'+params,headers={'User-Agent':'ERArchive/1.0','Accept':'application/xml,text/xml'})
 try:
  with urllib.request.build_opener(NoRedirect).open(req,timeout=15) as response:raw=response.read(2_000_001)
  if len(raw)>2_000_000 or re.search(br'<!\s*(?:DOCTYPE|ENTITY)',raw,re.I):raise LawApiError('지원하지 않는 법령 API 응답입니다.')
  root=ET.fromstring(raw)
 except (urllib.error.URLError,TimeoutError,OSError,ET.ParseError):raise LawApiError('법령 API에 연결하지 못했습니다. 인증값과 네트워크를 확인하세요.')
 result=[]
 for node in root.iter():
  if node.tag.rsplit('}',1)[-1]!='law':continue
  fields={child.tag.rsplit('}',1)[-1]:(child.text or '').strip() for child in node}
  name=fields.get('법령명한글','');law_id=fields.get('법령ID','')
  if name and law_id.isdigit():result.append({'name':name,'date':fields.get('시행일자',''),'url':'https://www.law.go.kr/법령/'+urllib.parse.quote(name,safe='')})
 return result
