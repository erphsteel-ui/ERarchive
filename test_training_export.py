import json, unittest
import test_app, app
class TrainingExportTests(unittest.TestCase):
 def setUp(self):
  self.base=test_app.Tests();self.base.setUp();self.c=self.base.c;self.v=self.base.v;self.h=self.base.h
 def test_export_reviews_and_changes(self):
  did=self.base.upload(['purple']);doc=self.base.doc(did)
  self.assertEqual(self.v.get('/api/classification-export').status_code,403)
  self.assertEqual(self.v.post('/api/classification-review/'+did,json={'version':doc['version'],'note':'','reviewed':True},headers=self.base.vh).status_code,403)
  self.assertEqual(self.c.post('/api/classification-review/'+did,json={'version':doc['version'],'note':'확인 근거','reviewed':True},headers=self.h).status_code,200)
  result=self.c.get('/api/classification-export');self.assertEqual(result.status_code,200);self.assertIn('attachment',result.headers['Content-Disposition'])
  export=json.loads(result.data);row=next(x for x in export['records'] if x['id']==did)
  self.assertEqual(export['schema'],'erarchive.classification.v1');self.assertEqual(row['review']['status'],'reviewed');self.assertEqual(row['review']['note'],'확인 근거')
  self.assertEqual(len(row['pages']),1);self.assertIn('original_text',row['pages'][0]);self.assertNotIn('path',row['pages'][0]);self.assertNotIn('password',result.get_data(as_text=True))
  self.assertEqual(self.base.save(doc).status_code,200)
  row=next(x for x in json.loads(self.c.get('/api/classification-export').data)['records'] if x['id']==did)
  self.assertEqual(row['review']['status'],'changed_after_review')
  self.assertEqual(self.c.post('/api/classification-review/'+did,json={'version':doc['version'],'note':'','reviewed':True},headers=self.h).status_code,409)
  new=self.base.doc(did);self.assertEqual(self.c.post('/api/classification-review/'+did,json={'version':new['version'],'note':'','reviewed':False},headers=self.h).status_code,200)
  row=next(x for x in json.loads(self.c.get('/api/classification-export').data)['records'] if x['id']==did);self.assertEqual(row['review']['status'],'unreviewed')
 def test_requires_csrf_and_delete_cleanup(self):
  did=self.base.upload(['red']);doc=self.base.doc(did);payload={'version':doc['version'],'note':'','reviewed':True}
  self.assertEqual(self.c.post('/api/classification-review/'+did,json=payload).status_code,403)
  self.assertEqual(self.c.post('/api/classification-review/'+did,json=payload,headers=self.h).status_code,200)
  self.assertEqual(self.c.post('/api/documents/'+did+'/delete',json={},headers=self.h).status_code,200)
  with app.db() as c:self.assertIsNone(c.execute('SELECT doc FROM classification_review WHERE doc=?',(did,)).fetchone())
if __name__=='__main__':unittest.main()
