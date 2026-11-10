"""Deployment startup checks use isolated directories and subprocesses."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent

class CloudDeployTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = os.environ.copy()
        for key in ('ERARCHIVE_DATA_DIR', 'ARCHIVE_DATA', 'ERARCHIVE_REQUIRE_VOLUME',
                    'ERARCHIVE_ADMIN_USER', 'ERARCHIVE_ADMIN_PASSWORD'):
            self.env.pop(key, None)

    def run_app(self, code, **variables):
        return subprocess.run([sys.executable, '-c', code], cwd=ROOT,
                              env={**self.env, **variables}, capture_output=True, text=True)

    def test_bootstrap_only_once_and_data_directory_precedence(self):
        data = str(self.root / 'data')
        legacy = str(self.root / 'legacy')
        variables = dict(ERARCHIVE_DATA_DIR=data, ARCHIVE_DATA=legacy,
                         ERARCHIVE_ADMIN_USER='first', ERARCHIVE_ADMIN_PASSWORD='first-password-123')
        first = self.run_app('import app; app.ensure_admin()', **variables)
        self.assertEqual(first.returncode, 0, first.stderr)
        variables.update(ERARCHIVE_ADMIN_USER='second', ERARCHIVE_ADMIN_PASSWORD='second-password-123')
        again = self.run_app('import app; app.ensure_admin()', **variables)
        self.assertEqual(again.returncode, 0, again.stderr)
        with sqlite3.connect(Path(data) / 'archive.db') as db:
            self.assertEqual(db.execute('SELECT name FROM users WHERE role=?', ('admin',)).fetchall(), [('first',)])
        self.assertFalse(Path(legacy).exists())

    def test_initial_admin_accepts_eight_characters_and_rejects_seven(self):
        too_short = self.run_app('import app; app.ensure_admin()', ERARCHIVE_DATA_DIR=str(self.root / 'short'), ERARCHIVE_ADMIN_USER='admin', ERARCHIVE_ADMIN_PASSWORD='1234567')
        self.assertNotEqual(too_short.returncode, 0)
        valid = self.run_app('import app; app.ensure_admin()', ERARCHIVE_DATA_DIR=str(self.root / 'valid'), ERARCHIVE_ADMIN_USER='admin', ERARCHIVE_ADMIN_PASSWORD='12345678')
        self.assertEqual(valid.returncode, 0, valid.stderr)

    def test_required_volume_fails_before_creating_database(self):
        data = str(self.root / 'not-a-mount')
        result = self.run_app('import app', ERARCHIVE_DATA_DIR=data, ERARCHIVE_REQUIRE_VOLUME='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Persistent volume is not mounted', result.stderr)
        self.assertFalse(Path(data).exists())

if __name__ == '__main__':
    unittest.main()
