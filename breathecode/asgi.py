"""
ASGI config for breathecode project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/howto/deployment/asgi/
"""

from breathecode.websocket.urls import websocket_urlpatterns
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import breathecode.settings as app_settings
from django.conf import settings
import os
from django.core.asgi import get_asgi_application
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'breathecode.settings')

django.setup()
app = get_asgi_application()


# settings.configure(INSTALLED_APPS=app_settings.INSTALLED_APPS, DATABASES=app_settings.DATABASES)

application = ProtocolTypeRouter({
    'http': app,
})
