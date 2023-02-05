[![Build Status](https://travis-ci.org/nnseva/django-storage-celery-results.svg?branch=master)](https://travis-ci.org/nnseva/django-storage-celery-results)

# Django Storage Celery Results

The Django Storage Celery Results application introduces custom
Celery Result storage based on the Django Storage for the Django-based project.

It allows using any existent core or third-party Django Storage implementation
to store Celery results.

## Inspiration

The Celery package provides some number of result backends to store task results
in different local, network, and cloud storages. The django-celery-result
package adds options to use Django-specific ORM-based result storage,
as well as Django-specific cache subsystem.

On the other side, the Django itself, together with a django-storages package,
provides a wide range of file-like storage backends also using local, network, and
cloud storages.

The common interface of the Django Storage allows adopt it to store
the Celery task results.

That's exactly what this package does. It's a simple thin wrapper appropriate
to use with any Django Storage backend to adopt it to the Celery task results
storage.

## Installation

*Stable version* from the PyPi package repository
```bash
pip install django-storage-celery-results
```

*Last development version* from the GitHub source version control system
```bash
pip install git+git://github.com/nnseva/django-storage-celery-results.git
```

## Configuration

Include the `django_storage_celery_results` application into the `INSTALLED_APPS` list, like:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    ...
    'django_storage_celery_results',
    ...
]
```

## Using

### Settings

Use `settings.py` file to provide common settings of the Celery switching to the
custom storage:

```python
CELERY_RESULT_BACKEND = 'django_storage_celery_results.backends.StorageBackend'
```

The Celery package allows to use short labels to refer to own or third-party
backends, you can use ones *instead* of the full path to the custom backend of
the installed package:

```python
CELERY_RESULT_BACKEND = 'django-storage'
```

You can use two ways to provide django storage backend-specific parameters
to the backend constructor simultaneously.

For the first, you can use classic Django way declaring separate
backend-specific prefixed variables in the `settings.py` file. For example,
accordingly to the django-storage package documentation, you can use
`GS_`-prefixed variables to provide Google Storage specific
parameters to the django storage, like:

```python
from google.oauth2 import service_account

GS_BUCKET_NAME = 'YOUR_BUCKET_NAME_GOES_HERE'
GS_CREDENTIALS = service_account.Credentials.from_service_account_file(
    "path/to/credentials.json"
)
```

For the second, you can use one settings variable to provide all necessary
parameters directly to the storage backend constructor (see the particular
storage backend constructor names inside the storage backend source code):

```python
from google.oauth2 import service_account

CELERY_RESULT_STORAGE_CONFIG = {
    'credentials': service_account.Credentials.from_service_account_file(
        'path/to/credentials.json'
    ),
    'bucket_name': 'YOUR_BUCKET_NAME_GOES_HERE',
    'location': 'celery-results/develop'
}
```

Mixing these two ways, directly passed parameters are preferred by
the constructor as a rule (depends on the storage backend implementation).

# Known Django storage backends

This appendix lists several Django Storage backends tested by the author
to be compatible with the package, with the table of used
backend-specific Django `settings.py` variables
and the corresponding backend constructor parameters appropriate
to use as keys of the `CELERY_RESULT_STORAGE_CONFIG` variable.

## Core Django `FileSystemStorage` for local files

see also the current [documentation](https://docs.djangoproject.com/en/stable/ref/files/storage/)

```python
CELERY_RESULT_STORAGE = 'django.core.files.storage.FileSystemStorage'
```

`settings.py` variable | backend constructor parameter | Meaning from doc
-------------------------------------------------------------------------
MEDIA_ROOT             | location                      | Absolute filesystem path to the directory that will hold the files.

## Django Storages package

see also the current [documentation](https://django-storages.readthedocs.io/en/latest/)

**NOTICE** that the direct backend constructor parameter names are not documented
in the documentation, so may be changed from version to version.

**NOTICE** that the chapters below describe only some important parameters, not all.

See the original package [documentation](https://django-storages.readthedocs.io/en/latest/)
and the method `get_default_settings` of every backend to see the full list of
the backend constructor parameters.

### Amazon S3

```python
CELERY_RESULT_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
```

`settings.py` variable | backend constructor parameter | Meaning from doc
-------------------------------------------------------------------------
AWS_S3_ACCESS_KEY_ID, AWS_ACCESS_KEY_ID|access_key| Access Key
AWS_S3_SECRET_ACCESS_KEY, AWS_SECRET_ACCESS_KEY|secret_key| Access Secret
AWS_STORAGE_BUCKET_NAME|bucket_name| Bucket Name
AWS_LOCATION|location| Storage Location (folder) inside a bucket

### Google Cloud Storage

`settings.py` variable | backend constructor parameter | Meaning from doc
-------------------------------------------------------------------------
GS_CREDENTIALS|credentials| Credentials object created by the Google library
GS_BUCKET_NAME|bucket_name| Bucket Name
GS_LOCATION|location| Storage Location (folder) inside a bucket

# Contribution

I would glad to see PRs and ideas for the package unit testing, as well as
reports about integration experience in different environments.
