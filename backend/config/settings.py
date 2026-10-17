import os

SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
DEBUG = False
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '10.0.2.2', 'testserver', 'backend']
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes',
                  'rest_framework', 'rest_framework.authtoken', 'drf_spectacular', 'bank']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'bank.logging.RequestLogMiddleware',
              'django.middleware.common.CommonMiddleware']
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'APP_DIRS': True}]
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': os.environ.get('POSTGRES_DB', 'banklab'),
    'USER': os.environ.get('POSTGRES_USER', 'banklab'),
    'PASSWORD': os.environ['POSTGRES_PASSWORD'],
    'HOST': os.environ.get('POSTGRES_HOST', 'db'), 'PORT': '5432',
}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
TIME_ZONE = 'Asia/Almaty'
LANGUAGE_CODE = 'ru'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.TokenAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle',
                                'rest_framework.throttling.UserRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'anon': '60/min', 'user': '300/min'},
}
SPECTACULAR_SETTINGS = {'TITLE': 'Bank Lab API', 'VERSION': '1.0.0',
                         'DESCRIPTION': 'Учебный банк. Все средства вымышленные.'}
ENABLE_TEST_TOPUP = os.environ.get('ENABLE_TEST_TOPUP', 'false').lower() == 'true'
LOGGING = {'version': 1, 'disable_existing_loggers': False,
           'handlers': {'console': {'class': 'logging.StreamHandler'}},
           'root': {'handlers': ['console'], 'level': 'INFO'}}
