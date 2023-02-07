"""Tests module"""
import os
import os.path
import shlex
import subprocess
import time
from unittest import mock, skipUnless

import celery

from django.test import TestCase, override_settings
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


@skipUnless(celery.VERSION.major >= 5, 'Celery>=5 required')
class SafeToRetryTest(TestCase):
    """Unit test for safe_to_retry settings"""
    # NOTICE: experimental feature
    maxDiff = None

    def setUp(self):
        """Setup necessary objects"""

    def tearDown(self):
        """Free resources"""

    def test_celery_safe_to_retry_boolean(self):
        """Test whether the celery works with boolean safe_to_retry"""
        from celery.exceptions import BackendGetMetaError, BackendStoreError
        from tests.celery import app

        from django_storage_celery_results.backends import StorageBackend

        with override_settings(
            CELERY_RESULT_SAFE_TO_RETRY=True,
            CELERY_RESULT_BACKEND_MAX_RETRIES=3,
        ):
            storage_backend = StorageBackend(app)

            ret = storage_backend.get_task_meta('qwertyuiop')
            self.assertEqual(ret, {'status': 'PENDING', 'result': None})

            def test_open(*av, **kw):
                self.cnt += 1
                raise Exception('Test Exception')

            self.cnt = 0
            with mock.patch('django.core.files.storage.FileSystemStorage.open', mock.MagicMock(side_effect=test_open)):
                with self.assertRaises(BackendGetMetaError):
                    ret = storage_backend.get_task_meta('qwertyuiop')
            self.assertEqual(self.cnt, 4)

            self.cnt = 0
            with mock.patch('django.core.files.storage.FileSystemStorage.open', mock.MagicMock(side_effect=test_open)):
                with self.assertRaises(BackendStoreError):
                    ret = storage_backend.mark_as_started('qwertyuiop')
            self.assertEqual(self.cnt, 4)

    def test_celery_safe_to_retry_callable(self):
        """Test whether the celery works with callable safe_to_retry"""
        from celery.exceptions import BackendGetMetaError, BackendStoreError
        from tests.celery import app

        from django_storage_celery_results.backends import StorageBackend

        def test_safe_to_retry(exc):
            return getattr(self, 'safe', False)

        with override_settings(
            CELERY_RESULT_SAFE_TO_RETRY=test_safe_to_retry,
            CELERY_RESULT_BACKEND_MAX_RETRIES=3,
        ):
            storage_backend = StorageBackend(app)

            ret = storage_backend.get_task_meta('qwertyuiop')
            self.assertEqual(ret, {'status': 'PENDING', 'result': None})

            def test_open(*av, **kw):
                self.cnt += 1
                raise Exception('Test Exception')

            self.cnt = 0
            with mock.patch('django.core.files.storage.FileSystemStorage.open', mock.MagicMock(side_effect=test_open)):
                with self.assertRaises(Exception) as r:
                    ret = storage_backend.get_task_meta('qwertyuiop')
            self.assertEqual(self.cnt, 1)
            self.assertEqual(str(r.exception), 'Test Exception')

            self.safe = True

            self.cnt = 0
            with mock.patch('django.core.files.storage.FileSystemStorage.open', mock.MagicMock(side_effect=test_open)):
                with self.assertRaises(BackendGetMetaError) as r:
                    ret = storage_backend.get_task_meta('qwertyuiop')
            self.assertEqual(self.cnt, 4)

            self.cnt = 0
            with mock.patch('django.core.files.storage.FileSystemStorage.open', mock.MagicMock(side_effect=test_open)):
                with self.assertRaises(BackendStoreError) as r:
                    ret = storage_backend.mark_as_started('qwertyuiop')
            self.assertEqual(self.cnt, 4)

    def test_celery_safe_to_retry_tuple(self):
        """Test whether the celery works with tuple safe_to_retry"""
        from celery.exceptions import BackendGetMetaError
        from tests.celery import app

        from django_storage_celery_results.backends import StorageBackend

        class E1(Exception):
            pass

        class E2(Exception):
            pass

        class E3(E1):
            pass

        with override_settings(
            CELERY_RESULT_SAFE_TO_RETRY=(E1,),
            CELERY_RESULT_BACKEND_MAX_RETRIES=3,
        ):
            storage_backend = StorageBackend(app)

            ret = storage_backend.get_task_meta('qwertyuiop')
            self.assertEqual(ret, {'status': 'PENDING', 'result': None})

            with mock.patch('django.core.files.storage.FileSystemStorage.open', mock.MagicMock(side_effect=E2('e2'))):
                with self.assertRaises(Exception) as r:
                    ret = storage_backend.get_task_meta('qwertyuiop')
            self.assertTrue(isinstance(r.exception, E2))

            with mock.patch('django.core.files.storage.FileSystemStorage.open', mock.MagicMock(side_effect=E1('e1'))):
                with self.assertRaises(BackendGetMetaError) as r:
                    ret = storage_backend.get_task_meta('qwertyuiop')

            with mock.patch('django.core.files.storage.FileSystemStorage.open', mock.MagicMock(side_effect=E3('e3'))):
                with self.assertRaises(BackendGetMetaError) as r:
                    ret = storage_backend.get_task_meta('qwertyuiop')
