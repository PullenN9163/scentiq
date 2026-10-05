from scentiq_api.hybrid.__main__ import build_parser


def test_hybrid_cli_exposes_operational_commands() -> None:
    parser = build_parser()

    assert parser.parse_args(["dispatch", "--catalog-version", "catalog-a"]).command == "dispatch"
    assert parser.parse_args(["apply-results"]).command == "apply-results"
    worker = parser.parse_args(["worker", "--once", "--algorithm-version", "1"])
    assert worker.command == "worker"
    assert worker.once is True
