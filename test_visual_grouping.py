import tempfile,unittest
from pathlib import Path
from PIL import Image,ImageDraw
from visual_grouping import header_signature,similarity
from batches import group_pages
class VisualTests(unittest.TestCase):
 def create(self,path,color,body):
  im=Image.new('RGB',(600,900),'white');d=ImageDraw.Draw(im)
  d.rectangle((20,20,580,140),fill=color);d.rectangle((20,145,580,165),fill='black')
  d.ellipse((35,35,110,110),fill='white');d.rectangle((135,55,500,85),fill='white')
  d.rectangle((20,250,580,850),fill=body);im.save(path)
 def test_same_header_different_body_and_filename(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=Path(tmp)/'a.jpg';b=Path(tmp)/'unrelated_name.jpg';self.create(a,'navy','red');self.create(b,'navy','green')
   sa=header_signature(a);sb=header_signature(b);self.assertGreaterEqual(similarity(sa,sb),.9)
   meta={'title':'','publishers':[],'date':'','issue':''}
   items=[{'id':'a','name':a.name,'meta':meta,'visual':sa},{'id':'b','name':b.name,'meta':meta,'visual':sb}]
   groups=group_pages(items,'auto');self.assertEqual(len(groups),1);self.assertIn('상단',groups[0]['reason'])
   items[0]['meta']=dict(meta,issue='26-01호');items[1]['meta']=dict(meta,issue='26-02호');self.assertEqual(len(group_pages(items,'auto')),2)
 def test_plain_paper_and_changed_design(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=Path(tmp)/'a.png';b=Path(tmp)/'b.png';Image.new('RGB',(600,900),'white').save(a)
   self.assertIsNone(header_signature(a));Image.new('RGB',(600,900),'blue').save(a);self.assertIsNone(header_signature(a))
   self.create(a,'navy','white');self.create(b,'orange','white');self.assertLess(similarity(header_signature(a),header_signature(b)),.9)
if __name__=='__main__':unittest.main()
