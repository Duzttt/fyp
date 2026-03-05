from django.urls import re_path

from django_app import consumers

websocket_urlpatterns = [
    re_path(r"ws/dashboard/$", consumers.DashboardConsumer.as_asgi()),
    re_path(r"ws/upload/$", consumers.UploadProgressConsumer.as_asgi()),
]
