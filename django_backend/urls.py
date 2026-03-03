from django.urls import path

from django_app import views

urlpatterns = [
    path("", views.root),
    path("chat-demo", views.chat_demo_page),
    path("health", views.health_check),
    path("api/upload", views.upload_pdf),
    path("api/ask", views.ask_question),
    path("api/settings", views.settings_handler),
]
