import unittest,tempfile,json,shutil
from pathlib import Path
import test_app,app
from folder_import import FolderImporter
class FolderTests(unittest.TestCase):
 setUp=test_app.Tests.setUp
 img=test_app.Tests.img
 def config(self,folder):
  with app.db() as c:c.execute("UPDATE settings SET value=? WHERE key='inbox'",(json.dumps({'enabled':True,'path':str(folder)}),))
 def test_stability_batch_duplicates_and_restart(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);self.config(folder)
   for color,name in [('red','a.png'),('blue','a_01.png'),('green','b.png'),('yellow','b_01.png')]: (folder/name).write_bytes(self.img(color).getvalue())
   m=FolderImporter(app);m.scan(0);m.scan(10)
   self.assertEqual(self.c.get('/api/batches').json,[])
   m.scan(16);rows=self.c.get('/api/batches').json;self.assertEqual(len(rows),1);self.assertEqual(rows[0]['total'],4)
   self.assertEqual(self.v.get('/api/documents').json,[])
   shutil.copyfile(folder/'a.png',folder/'renamed.png');m.scan(20);m.scan(36)
   self.assertEqual(len(self.c.get('/api/batches').json),1)
   m=FolderImporter(app);m.scan(40);m.scan(56)
   self.assertEqual(len(self.c.get('/api/batches').json),1)
   with app.db() as c:c.execute('DELETE FROM batches')
   m=FolderImporter(app);m.scan(60);m.scan(76)
   self.assertEqual(self.c.get('/api/batches').json,[])
   self.assertTrue((folder/'a.png').exists())
 def test_copy_change_resets_wait_and_bad_file_does_not_block(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);self.config(folder);p=folder/'x.png';p.write_bytes(b'partial')
   m=FolderImporter(app);m.scan(0);p.write_bytes(self.img('red').getvalue());m.scan(10);m.scan(20)
   self.assertEqual(self.c.get('/api/batches').json,[])
   (folder/'bad.png').write_bytes(b'invalid');m.scan(21);m.scan(37)
   self.assertEqual(self.c.get('/api/batches').json[0]['total'],1);self.assertEqual(len(m.info['errors']),1)
 def test_permissions_and_settings(self):
  self.assertEqual(self.v.get('/api/inbox').status_code,403)
  self.assertEqual(app.app.test_client().get('/api/inbox').status_code,401)
  with tempfile.TemporaryDirectory() as tmp:
   body={'enabled':False,'path':tmp}
   self.assertEqual(self.c.post('/api/inbox',json=body).status_code,403)
   self.assertEqual(self.c.post('/api/inbox',json=body,headers=self.h).status_code,200)
   self.assertFalse(self.c.get('/api/inbox').json['config']['enabled'])
   self.assertEqual(self.c.post('/api/inbox',json={'enabled':True,'path':str(app.DATA)},headers=self.h).status_code,400)
 def test_manual_upload_is_not_collected_again(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);self.config(folder);raw=self.img('orange').getvalue();(folder/'x.png').write_bytes(raw)
   self.c.post('/api/batches',headers=self.h,data={'files':(self.img('orange'),'manual.png')})
   m=FolderImporter(app);m.scan(0);m.scan(16)
   self.assertEqual(len(self.c.get('/api/batches').json),1);self.assertEqual(m.info['imported'],0)
 def test_more_than_twenty_files_are_collected_in_bounded_batches(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);self.config(folder)
   for i in range(21):(folder/(str(i)+'.png')).write_bytes(self.img((i,0,0)).getvalue())
   m=FolderImporter(app);m.scan(0);m.scan(16);m.scan(21)
   rows=self.c.get('/api/batches').json;self.assertEqual(len(rows),2);self.assertEqual(sum(r['total'] for r in rows),21)
if __name__=='__main__':unittest.main()
