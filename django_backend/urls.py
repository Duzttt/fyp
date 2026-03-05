from django.urls import path, re_path
from django.conf import settings
from django.conf.urls.static import static

from django_app import views

urlpatterns = [
    # API endpoints
    path("api", views.root),
    path("api/", views.root),
    path("api/upload", views.upload_pdf),
    path("api/upload/", views.upload_pdf),
    path("api/upload/status", views.upload_index_status),
    path("api/upload/status/", views.upload_index_status),
    path("api/files", views.list_files),
    path("api/files/", views.list_files),
    path("api/documents", views.list_documents),
    path("api/documents/", views.list_documents),
    path("api/documents/delete", views.delete_document),
    path("api/documents/delete/", views.delete_document),
    path("api/summarize", views.summarize_doc),
    path("api/summarize/", views.summarize_doc),
    path("api/podcast", views.generate_podcast),
    path("api/podcast/", views.generate_podcast),
    path("api/ask", views.ask_question),
    path("api/ask/", views.ask_question),
    path("api/chat", views.ask_qwen),
    path("api/chat/", views.ask_qwen),
    path("api/ask_qwen", views.ask_qwen),
    path("api/ask_qwen/", views.ask_qwen),
    path("api/settings", views.settings_handler),
    path("api/settings/", views.settings_handler),
    path("api/rag-config", views.get_rag_config),
    path("api/rag-config/", views.get_rag_config),
    path("api/rag-config/update", views.update_rag_config),
    path("api/rag-config/update/", views.update_rag_config),
    path("api/index/reset", views.reset_faiss_index),
    path("api/index/reset/", views.reset_faiss_index),
    path("chat-htmx", views.chat_htmx),
    path("chat-htmx/", views.chat_htmx),
    path("api/retrieve", views.retrieve_chunks),
    path("api/retrieve/", views.retrieve_chunks),
    path("api/compare", views.compare_documents),
    path("api/compare/", views.compare_documents),
    # Dashboard API endpoints
    path("api/dashboard/stats", views.dashboard_stats),
    path("api/dashboard/stats/", views.dashboard_stats),
    path("api/dashboard/metrics", views.dashboard_metrics),
    path("api/dashboard/metrics/", views.dashboard_metrics),
    path("api/dashboard/chunks/distribution", views.dashboard_chunks_distribution),
    path("api/dashboard/chunks/distribution/", views.dashboard_chunks_distribution),
    path("api/dashboard/similarity/distribution", views.dashboard_similarity_distribution),
    path("api/dashboard/similarity/distribution/", views.dashboard_similarity_distribution),
    path("api/dashboard/documents/timeline", views.dashboard_documents_timeline),
    path("api/dashboard/documents/timeline/", views.dashboard_documents_timeline),
    path("api/dashboard/config", views.dashboard_update_config),
    path("api/dashboard/config/", views.dashboard_update_config),
    path("api/dashboard/reindex", views.dashboard_reindex),
    path("api/dashboard/reindex/", views.dashboard_reindex),
    # Embedding Model Management endpoints
    path("api/settings/embedding-models", views.list_embedding_models),
    path("api/settings/embedding-models/", views.list_embedding_models),
    path("api/settings/embedding-model", views.get_current_embedding_model),
    path("api/settings/embedding-model/", views.get_current_embedding_model),
    path("api/settings/embedding-model/switch", views.switch_embedding_model),
    path("api/settings/embedding-model/switch/", views.switch_embedding_model),
    path("api/settings/embedding-model/test", views.test_embedding_model),
    path("api/settings/embedding-model/test/", views.test_embedding_model),
    path("api/settings/embedding-model/metrics", views.get_embedding_model_metrics),
    path("api/settings/embedding-model/metrics/", views.get_embedding_model_metrics),
    path("api/settings/embedding-model/cache/clear", views.clear_embedding_model_cache),
    path("api/settings/embedding-model/cache/clear/", views.clear_embedding_model_cache),
    # Document Summarization endpoints
    path("api/summary/generate", views.generate_summary),
    path("api/summary/generate/", views.generate_summary),
    path("api/summary/history", views.get_summary_history),
    path("api/summary/history/", views.get_summary_history),
    path("api/summary/<str:summary_id>/delete", views.delete_summary),
    path("api/summary/<str:summary_id>/delete/", views.delete_summary),
    path("api/summary/regenerate", views.regenerate_summary),
    path("api/summary/regenerate/", views.regenerate_summary),
    # SPA catch-all: serve Vue frontend for any non-API route
    re_path(r"^(?!api/).*$", views.index_page),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
