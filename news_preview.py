"""Best-effort public-page OG images. DNS-pinned connections never reach private networks."""
import http.client,ipaddress,socket,ssl,urllib.parse,io,time
from html.parser import HTMLParser
from PIL import Image,ImageOps

class PinnedHTTPS(http.client.HTTPSConnection):
    def connect(self):
        raw=socket.create_connection((self.public_ip,self.port),self.timeout)
        try:self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
        except BaseException:raw.close();raise
class PinnedHTTP(http.client.HTTPConnection):
    def connect(self):self.sock=socket.create_connection((self.public_ip,self.port),self.timeout)
def fetch_public(url,limit,redirects=3):
    deadline=time.monotonic()+12
    for _ in range(redirects+1):
        u=urllib.parse.urlsplit(url)
        if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:raise ValueError('URL')
        port=u.port or (443 if u.scheme=='https' else 80)
        if port not in (80,443):raise ValueError('port')
        addresses=socket.getaddrinfo(u.hostname,port,type=socket.SOCK_STREAM)
        ips=[x[4][0] for x in addresses]
        if not ips or any(not ipaddress.ip_address(ip).is_global or ipaddress.ip_address(ip).is_multicast for ip in ips):raise ValueError('non-public host')
        cls=PinnedHTTPS if u.scheme=='https' else PinnedHTTP
        connection=cls(u.hostname,port,timeout=4);connection.public_ip=ips[0]
        try:
            path=urllib.parse.urlunsplit(('','',u.path or '/',u.query,''))
            connection.request('GET',path,headers={'User-Agent':'ERArchive-NewsPreview/1.0','Accept-Encoding':'identity','Accept':'text/html,image/*'})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location:raise ValueError('redirect')
                url=urllib.parse.urljoin(url,location);continue
            if response.status!=200:raise ValueError('status')
            result=bytearray()
            while True:
                if time.monotonic()>deadline:raise TimeoutError()
                chunk=response.read(min(32768,limit+1-len(result)))
                if not chunk:break
                result.extend(chunk)
                if len(result)>limit:raise ValueError('too large')
            return bytes(result),response.getheader('Content-Type',''),url
        finally:connection.close()
    raise ValueError('redirects')
class MetaImage(HTMLParser):
    def __init__(self):super().__init__();self.og='';self.twitter=''
    def handle_starttag(self,tag,attrs):
        if tag.lower()!='meta':return
        values={k.lower():v for k,v in attrs};name=(values.get('property') or values.get('name') or '').lower()
        if name in ('og:image','og:image:url') and not self.og:self.og=values.get('content','')
        if name in ('twitter:image','twitter:image:src') and not self.twitter:self.twitter=values.get('content','')
def make_preview(url):
    raw,content,final=fetch_public(url,512*1024)
    if 'html' not in content.lower():raise ValueError('not HTML')
    parser=MetaImage();parser.feed(raw.decode('utf-8',errors='replace'))
    image_url=parser.og or parser.twitter
    if not image_url:raise ValueError('no image')
    raw,content,_=fetch_public(urllib.parse.urljoin(final,image_url),3*1024*1024)
    if not content.lower().startswith('image/'):raise ValueError('not image')
    with Image.open(io.BytesIO(raw)) as source:
        if source.width*source.height>20000000:raise ValueError('large image')
        image=ImageOps.exif_transpose(source).convert('RGB');image.thumbnail((480,320))
        output=io.BytesIO();image.save(output,'JPEG',quality=80);image.close();return output.getvalue()
