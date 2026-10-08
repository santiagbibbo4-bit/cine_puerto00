from django.apps import AppConfig


class CineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "cine"
    verbose_name = "Cine de Cortos"

    def ready(self):
        from . import signals  # noqa: F401
