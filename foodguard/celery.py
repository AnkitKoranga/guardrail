import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'foodguard.settings')

# Import settings to check eager mode
import django
django.setup()
from django.conf import settings

# Check if eager mode is enabled
CELERY_TASK_ALWAYS_EAGER = getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False)

# Create Celery app - set broker in constructor to prevent override
if CELERY_TASK_ALWAYS_EAGER:
    app = Celery('foodguard', broker='memory://', backend='cache://')
else:
    app = Celery('foodguard')

# Load configuration from settings, but we'll override broker after
app.config_from_object('django.conf:settings', namespace='CELERY')

# CRITICAL: Force broker_url to memory:// AFTER config load
# The config_from_object might be loading a Redis URL from somewhere
if CELERY_TASK_ALWAYS_EAGER:
    # Directly set on the connection object to prevent any override
    app.conf.broker_url = 'memory://'
    app.conf.result_backend = 'cache://'
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True
    app.conf.broker_connection_retry_on_startup = False
    app.conf.broker_connection_retry = False
    app.conf.broker_transport = 'memory'
    
    # Force the connection to use memory transport by clearing any cached connection
    if hasattr(app, 'broker_connection'):
        app.broker_connection = None
    # Ensure the broker_connection() method will use memory://
    app.conf.broker_url = 'memory://'

app.autodiscover_tasks()

