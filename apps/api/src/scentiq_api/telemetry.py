from collections.abc import Callable

from azure.monitor.opentelemetry import configure_azure_monitor

AzureMonitorConfigurator = Callable[..., None]


def configure_runtime_telemetry(
    connection_string: str | None,
    *,
    configurator: AzureMonitorConfigurator = configure_azure_monitor,
) -> bool:
    if not connection_string:
        return False

    configurator(
        connection_string=connection_string,
        disable_offline_storage=True,
        enable_trace_based_sampling_for_logs=True,
    )
    return True
