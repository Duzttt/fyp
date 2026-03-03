from django.urls import path

from django_app import views

urlpatterns = [
    path("", views.root),
    path("chat-demo", views.chat_demo_page),
    path("health", views.health_check),
    path("health/", views.health_check),
    path("api/upload", views.upload_pdf),
    path("api/upload/", views.upload_pdf),
    path("api/ask", views.ask_question),
    path("api/ask/", views.ask_question),
    path("api/chat", views.ask_qwen),
    path("api/chat/", views.ask_qwen),
    path("api/ask_qwen", views.ask_qwen),
    path("api/ask_qwen/", views.ask_qwen),
    path("api/settings", views.settings_handler),
    path("api/settings/", views.settings_handler),
]
