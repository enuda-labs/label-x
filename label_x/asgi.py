"""
ASGI config for label_x project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "label_x.settings")

django_asgi_app = get_asgi_application()
from channels.routing import ProtocolTypeRouter, URLRouter
import account.routing
import alert.routing
from alert.middleware import JWTAuthMiddleWare

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleWare(
        URLRouter(
            alert.routing.websocket_urlpatterns +
            account.routing.websocket_urlpatterns,
            
        )
    )
})
