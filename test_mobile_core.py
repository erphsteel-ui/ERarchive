"""Isolated regression checks for the manual mobile and cloud workflow."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT=Path(__file__).resolve().parent

class MobileCoreTests(unittest.TestCase):
 def test_reader_is_read_only_and_manual_pdf_is_preserved(self):
  with tempfile.TemporaryDirectory() as folder:
   env=os.environ.copy();env.pop('ERARCHIVE_REQUIRE_VOLUME',None);env['ERARCHIVE_DATA_DIR']=folder
   code=textwrap.dedent('''
    import io,sys
    import app
    from werkzeug.security import generate_password_hash
    with app.db() as c:
     c.executemany('INSERT INTO users VALUES(?,?,?)',[(name,generate_password_hash('password-12345'),role) for name,role in [('admin','admin'),('reader','viewer')]])
    admin=app.app.test_client();reader=app.app.test_client();guest=app.app.test_client()
    ah={'X-CSRF':admin.post('/api/login',json={'name':'admin','password':'password-12345'}).json['csrf']}
    rh={'X-CSRF':reader.post('/api/login',json={'name':'reader','password':'password-12345'}).json['csrf']}
    assert reader.post('/api/schedule/event',json={},headers=rh).status_code==403
    assert reader.post('/api/manual-upload',data={'title':'x','files':(io.BytesIO(b'%PDF-1.4'),'x.pdf')},headers=rh).status_code==403
    assert guest.get('/api/regulations/fulltexts').status_code==401
    assert reader.get('/api/regulations/fulltexts').status_code==200
    assert reader.post('/api/logout',json={},headers=rh).status_code==200
    r=admin.post('/api/manual-upload',data={'title':'sample','files':(io.BytesIO(b'%PDF-1.4'),'x.pdf')},headers=ah)
    assert r.status_code==200, r.json
    doc=admin.get('/api/documents').json[0]
    assert doc['pages'][0]['is_pdf']
    assert guest.get('/api/image/'+doc['pages'][0]['id']).status_code==401
    img=admin.get('/api/image/'+doc['pages'][0]['id']);assert img.status_code==200 and img.data.startswith(b'%PDF-')
    img.close()
    assert not any(x in sys.modules for x in ('ocr_engine','paddle_adapter','visual_grouping','schedule_extract'))
   ''')
   result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=env,text=True,capture_output=True)
   self.assertEqual(result.returncode,0,result.stderr)
 def test_law_search_parses_results_without_disclosing_key(self):
  code=textwrap.dedent('''
   import io
   from unittest.mock import patch
   import law_api
   xml='<LawSearch><law><법령명한글>근로기준법</법령명한글><법령ID>001872</법령ID><시행일자>20260101</시행일자></law></LawSearch>'.encode()
   class Response(io.BytesIO):
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
   with patch('urllib.request.build_opener') as opener:
    opener.return_value.open.return_value=Response(xml)
    items=law_api.search_laws('근로','private-key')
   assert len(items)==1 and items[0]['name']=='근로기준법' and 'private-key' not in str(items)
  ''')
  result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,text=True,capture_output=True)
  self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
