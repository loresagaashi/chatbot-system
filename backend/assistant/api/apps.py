from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self) -> None:
        """
        Hook that runs when Django loads this app.

        We use it to ensure that the built‑in personal CV document (if you
        configured one in `personal_seed.py`) is present in the database and
        has an up‑to‑date embedding.
        """
        try:
            from .personal_seed import ensure_personal_cv_document

            ensure_personal_cv_document()
        except Exception:
            # Never block startup because of seeding problems.
            pass
