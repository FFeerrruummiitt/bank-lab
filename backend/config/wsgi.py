import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from bank.tracing import configure_tracing
configure_tracing()
application = get_wsgi_application()
