from collections.abc import Callable


def _load_configurator() -> Callable[..., bool] | None:
    try:
        from scentiq_api.telemetry import configure_runtime_telemetry
    except ModuleNotFoundError:
        return None
    return configure_runtime_telemetry


def test_telemetry_is_disabled_without_a_connection_string() -> None:
    configure_runtime_telemetry = _load_configurator()
    assert configure_runtime_telemetry is not None

    def unexpected_configuration(**_: object) -> None:
        raise AssertionError("Azure Monitor must remain disabled in local development")

    enabled = configure_runtime_telemetry(None, configurator=unexpected_configuration)

    assert enabled is False


def test_telemetry_configures_azure_monitor_without_offline_secret_storage() -> None:
    configure_runtime_telemetry = _load_configurator()
    assert configure_runtime_telemetry is not None
    received: dict[str, object] = {}

    def record_configuration(**options: object) -> None:
        received.update(options)

    enabled = configure_runtime_telemetry(
        "InstrumentationKey=00000000-0000-0000-0000-000000000000",
        configurator=record_configuration,
    )

    assert enabled is True
    assert received == {
        "connection_string": "InstrumentationKey=00000000-0000-0000-0000-000000000000",
        "disable_offline_storage": True,
        "enable_trace_based_sampling_for_logs": True,
    }
