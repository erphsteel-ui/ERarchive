import io,unittest
from unittest.mock import patch
import test_app,app
from PIL import Image

class ThumbnailTests(unittest.TestCase):
 setUp=test_app.Tests.setUp
 def img(self,color):
  buffer=io.BytesIO();Image.new('RGB',(900,1200),color).save(buffer,format='PNG');buffer.seek(0);return buffer
 upload=test_app.Tests.upload
 doc=test_app.Tests.doc
 save=test_app.Tests.save
 def test_cached_thumbnail_respects_visibility_and_sizes(self):
  did=self.upload(['orange']);d=self.doc(did);pid=d['pages'][0]['id'];url='/api/thumbnail/'+pid
  with self.c.get(url) as r:self.assertEqual(r.status_code,200)
  self.assertEqual(self.v.get(url).status_code,404)
  self.assertEqual(self.save(d).status_code,200)
  for variant,limit in [('small',(120,160)),('card',(480,680))]:
   with self.v.get(url+'?size='+variant) as r:
    self.assertEqual(r.status_code,200)
    with Image.open(io.BytesIO(r.data)) as im:
     self.assertEqual(im.format,'JPEG');self.assertLessEqual(im.width,limit[0]);self.assertLessEqual(im.height,limit[1])
  with patch.object(app.Image,'open',side_effect=AssertionError('cache must avoid decoding')):
   with self.v.get(url) as r:self.assertEqual(r.status_code,200)
  d=self.doc(did);self.assertEqual(self.save(d,'draft').status_code,200)
  self.assertEqual(self.v.get(url).status_code,404)
  self.assertEqual(self.c.get(url+'?size=unknown').status_code,400)
