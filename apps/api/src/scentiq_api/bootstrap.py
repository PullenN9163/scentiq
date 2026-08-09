from scentiq_api.config import Settings
from scentiq_api.telemetry import configure_runtime_telemetry

settings = Settings()
configure_runtime_telemetry(settings.applicationinsights_connection_string_value)

from scentiq_api.main import create_app  # noqa: E402

app = create_app(settings)
