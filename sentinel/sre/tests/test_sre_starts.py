from unittest.mock import Mock

from sentinel.core.kafka.contracts import KafkaTopic, RequestKind


def test_sre_agent_starts_and_builds_its_runtime(monkeypatch) -> None:
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("LLM_API_KEY", "test")
    monkeypatch.setenv("SENTINEL_KAFKA_USERNAME", "sentinel")
    monkeypatch.setenv("SENTINEL_KAFKA_PASSWORD", "test")
    from sentinel.agents.sre import runtime, worker

    run_agent = Mock()
    monkeypatch.setattr(worker, "run_agent", run_agent)
    diagnosis_engine = Mock()
    monkeypatch.setattr(runtime, "DiagnosisAgent", diagnosis_engine)

    worker.main()

    _settings, topic, return_topic, kind, _execute = run_agent.call_args.args
    assert (topic, return_topic, kind) == (KafkaTopic.SRE_COMMANDS, KafkaTopic.SRE_RETURNS, RequestKind.INCIDENT)
    diagnosis_engine.assert_called_once()
    diagnosis_engine.return_value.close.assert_called_once()
