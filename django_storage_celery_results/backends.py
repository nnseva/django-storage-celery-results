"""The backend using Django File Storage backends to store results"""

import logging
import os.path

from celery.backends.base import KeyValueStoreBackend
from celery.exceptions import ImproperlyConfigured
from kombu.utils.encoding import bytes_to_str

from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string


logger = logging.getLogger(__name__)

__all__ = ('StorageBackend',)


class StorageBackend(KeyValueStoreBackend):
    """A Django Storage task result store.

    Raises:
        celery.exceptions.ImproperlyConfigured
    """

    #: Override to call expiration procedure
    supports_autoexpire = False

    def __init__(self, *av, **kwargs):
        """Constructs an instance of the backend"""
        super().__init__(*av, **kwargs)
        self.storage = self.app.conf.get('result_storage')
        if self.storage:
            self.storage_config = self.app.conf.get('result_storage_config')
        else:
            self.storage = 'django.core.files.storage.FileSystemStorage'
            self.storage_config = {
                'location': os.path.join(settings.MEDIA_ROOT, 'celery-results')
            }
        logger.debug(
            'Celery Storage Backend: %s(%s)',
            self.storage,
            self.storage_config
        )
        try:
            self.StorageBackend = import_string(self.storage)
        except Exception:
            logger.exception('Exception while inmport a storage backend')
            raise ImproperlyConfigured(
                'Can not import storage backend implementation: %s',
                self.storage
            )
        try:
            self.instance = self.StorageBackend(**self.storage_config)
        except Exception:
            logger.exception('Exception while creating an instance of the storage backend')
            raise ImproperlyConfigured(
                'Can not create an instance of the storage backend: %s(%s)',
                self.storage, self.storage_config
            )
        self.safe_to_retry = self.app.conf.get('result_safe_to_retry', False)
        self.always_retry = bool(self.safe_to_retry)

    def get(self, key):
        """Override to implement. Get the value by the key"""
        key = bytes_to_str(key)
        logger.debug('Reading %s', key)
        try:
            with self.instance.open(key, 'r') as f:
                return f.read()
        except FileNotFoundError:
            logger.info('File not found reading %s, ignored', key)
        except Exception:
            logger.exception('Exception while reading %s', key)
            # The caller probably might have a logic to resolve it
            raise

    def set(self, key, value):
        """Override to implement. Set a new value by the key"""
        key = bytes_to_str(key)
        logger.debug('Writing %s: %r', key, value)
        try:
            with self.instance.open(key, 'w') as f:
                f.write(value)
        except Exception:
            logger.exception('Exception while writing %s: %r', key, value)
            # The caller probably might have a logic to resolve it
            raise

    def delete(self, key):
        """Override to implement. Delete the key"""
        key = bytes_to_str(key)
        logger.debug('Deleting %s', key)
        try:
            self.instance.delete(key)
        except Exception:
            logger.exception('Exception while deleting %s', key)
            # The caller probably might have a logic to resolve it
            raise

    def cleanup(self):
        """
        Override to implement. Cleans up old results.

        NOTICE: checks and cleans up files in the
        location directory by the modification time!
        """
        logger.debug('Cleaning up, expires: %s', self.expires)
        now = timezone.now()
        for file_name in self.instance.listdir('.')[1]:
            logger.debug('Check: %s', file_name)
            modified_time = self.instance.get_modified_time(file_name)
            if not any(file_name.startswith(bytes_to_str(prefix)) for prefix in (
                self.task_keyprefix,
                self.group_keyprefix,
                self.chord_keyprefix,
            )):
                logger.debug('File is not produced by me, skipped: %s', file_name)
                continue
            if (now - modified_time).total_seconds() > self.expires:
                logger.debug('File %s modified time %s should be deleted', file_name, modified_time)
                try:
                    self.delete(file_name)
                except Exception:
                    # Ignore deletion exception to allow cleanup as much as possible
                    pass

    def exception_safe_to_retry(self, exc):
        """
        Override to implement.

        Returns True if the exception is safe to retry.
        """
        logger.debug('Check if the exception is safe to retry:', exc)
        if not self.safe_to_retry:
            return False
        if callable(self.safe_to_retry):
            return (self.safe_to_retry)(exc)
        if self.safe_to_retry is True:
            return True
        return isinstance(exc, self.safe_to_retry)
