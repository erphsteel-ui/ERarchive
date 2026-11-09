import datetime as dt,time,unittest
from unittest.mock import patch
import test_app,app

class AutoSyncTests(unittest.TestCase):
 def setUp(self):
  test_app.Tests.setUp(self)
  with app.db() as c:
   c.execute("DELETE FROM settings WHERE key IN ('last_news_sync_at','last_auto_news_sync_at')")
 def wait(self):
  for _ in range(100):
   result=self.c.get('/api/admin/status').json
   if not result['sync']['running']:return result
   time.sleep(.02)
  self.fail('synchronization did not finish')
 def test_success_cooldown_manual_override_and_permissions(self):
  self.assertEqual(self.v.get('/api/admin/status').status_code,403)
  self.assertEqual(self.v.post('/api/admin/sync',headers=self.vh,json={}).status_code,403)
  with patch.object(app,'collect_news',return_value=({'ok':True},200)) as news,patch.object(app,'collect_steel_press',return_value={'ok':True}) as press:
   self.assertTrue(app.start_news_sync()[0]);status=self.wait();self.assertTrue(status['sync']['last_auto_success'])
   self.assertFalse(app.start_news_sync()[0]);self.assertEqual(news.call_count,1);self.assertEqual(press.call_count,1)
   self.assertTrue(self.c.post('/api/admin/sync',headers=self.h,json={}).json['started']);self.wait();self.assertEqual(news.call_count,2);self.assertEqual(press.call_count,2)
 def test_partial_failure_does_not_set_success_or_block_retry(self):
  with patch.object(app,'collect_news',return_value=({'error':'키 없음'},400)),patch.object(app,'collect_steel_press',return_value={'ok':True}) as press:
   self.assertTrue(app.start_news_sync()[0]);status=self.wait();self.assertFalse(status['sync']['last_success']);self.assertIn('키 없음',status['sync']['error']);self.assertEqual(press.call_count,1)
   self.assertTrue(app.start_news_sync()[0]);self.wait();self.assertEqual(press.call_count,2)
