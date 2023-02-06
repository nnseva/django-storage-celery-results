"""Tests module"""
import os
import os.path
import shlex
import subprocess
import time

from django.test import TestCase
from django.utils import timezone


class ModuleTest(TestCase):
    """Test of the module"""
    maxDiff = None

    def setUp(self):
        """Setup necessary objects"""
        self.cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Start a separate Celery process
        self.check = subprocess.Popen(
            shlex.split('celery --app=tests worker --loglevel=DEBUG --beat'),
            cwd=self.cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.inherit_env()
        )
        t1 = timezone.now()
        while 42:
            line = self.check.stdout.readline()
            if not line:  # eof
                break
            line = line.strip()
            if isinstance(line, bytes):
                line = line.decode()
            print(">", line)
            if 'INFO/MainProcess' in line and 'celery@' in line and 'ready.' in line:
                # The celery instance is ready
                break
            t2 = timezone.now()
            if (t2 - t1).total_seconds() > 10:  # the timeout backoff if something went wrong
                break

    def tearDown(self):
        """Free resources"""
        # Stop a Celery process
        self.check.terminate()
        while 42:
            line = self.check.stdout.readline()
            if not line:  # eof
                break
            line = line.strip()
            if isinstance(line, bytes):
                line = line.decode()
            print("<", line)

    def inherit_env(self, extend={}):
        """
        Inherit virtual environment for the child process
        """
        env = {}
        if os.environ.get('VIRTUAL_ENV', ''):
            env = {
                'VIRTUAL_ENV': os.environ.get('VIRTUAL_ENV'),
                'PATH': os.environ.get('PATH'),
            }
            if os.environ.get('PYTHONHOME', ''):
                env['PYTHONHOME'] = os.environ.get('PYTHONHOME')
        env.update(extend)
        return env

    def test_001_celery_starts(self):
        """Test whether the celery works fine"""
        from tests.celery import debug_task

        result = debug_task.delay()
        ret = result.get(timeout=3)
        self.assertEqual(ret, {'Hello': 'Django Storage Celery Results!'})

        self.assertTrue(os.path.exists(os.path.join(self.cwd, 'celery-results', 'celery-task-meta-%s' % result.id)))

    def test_002_celery_expiration_works(self):
        """Test whether the celery expiration procedure is called properly"""
        from celery.app.builtins import add_backend_cleanup_task
        from tests.celery import app, debug_task
        bct = add_backend_cleanup_task(app)

        result = debug_task.delay()
        ret = result.get(timeout=3)
        self.assertEqual(ret, {'Hello': 'Django Storage Celery Results!'})
        time.sleep(3)
        result2 = debug_task.delay()
        ret2 = result.get(timeout=3)
        self.assertEqual(ret2, {'Hello': 'Django Storage Celery Results!'})

        bct_result = bct.delay()
        bct_result.get(timeout=3)

        self.assertFalse(os.path.exists(os.path.join(self.cwd, 'celery-results', 'celery-task-meta-%s' % result.id)))
        self.assertTrue(os.path.exists(os.path.join(self.cwd, 'celery-results', 'celery-task-meta-%s' % result2.id)))
