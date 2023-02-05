"""s3 result store backend."""

import logging
import os.path

from django.conf import settings
from django.utils.module_loading import import_string
from django.utils import timezone

from kombu.utils.encoding import bytes_to_str
from celery.exceptions import ImproperlyConfigured
from celery.backends.base import KeyValueStoreBackend

logger = logging.getLogger(__name__)

__all__ = ('StorageBackend',)


class StorageBackend(KeyValueStoreBackend):
    """A Django Storage task result store.

    Raises:
        celery.exceptions.ImproperlyConfigured
    """

    #: Override to call expiration procedure
    supports_autoexpire = False

    def __init__(self, **kwargs):
        """Constructs an instance of the backend"""
        super().__init__(**kwargs)
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

    def set(self, key, value):
        """Override to implement. Set a new value by the key"""
        key = bytes_to_str(key)
        logger.debug('Writing %s: %r', key, value)
        try:
            with self.instance.open(key, 'w') as f:
                f.write(value)
        except Exception:
            logger.exception('Exception while writing %s: %r', key, value)

    def delete(self, key):
        """Override to implement. Delete the key"""
        key = bytes_to_str(key)
        logger.debug('Deleting %s', key)
        try:
            self.instance.delete(key)
        except Exception:
            logger.exception('Exception while deleting %s', key)

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
                self.delete(file_name)
