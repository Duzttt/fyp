from django.apps import AppConfig


class DjangoAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_app"

    def ready(self) -> None:
        from django.db.utils import OperationalError, ProgrammingError

        try:
            from app.services.summary_executor import mark_interrupted

            mark_interrupted()
        except (OperationalError, ProgrammingError):
            # Table missing during initial migration — ignore.
            pass
