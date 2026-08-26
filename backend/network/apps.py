from django.apps import AppConfig


class NetworkConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "network"
    verbose_name = "网络实时域"

    def ready(self) -> None:
        from network.runtime_starter import maybe_start_in_process_collector

        maybe_start_in_process_collector()
