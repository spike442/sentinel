from unittest.mock import Mock

from sentinel.core.kafka.contracts import KafkaTopic, RequestKind


def test_sre_worker_starts_both_agents(monkeypatch) -> None:
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("LLM_API_KEY", "test")
    monkeypatch.setenv("SENTINEL_KAFKA_USERNAME", "sentinel-sre")
    monkeypatch.setenv("SENTINEL_KAFKA_PASSWORD", "test")
    from sentinel.sre import worker
    from sentinel.sre.incidents import runtime as incidents
    from sentinel.sre.reviews import runtime as reviews

    run_agents = Mock()
    monkeypatch.setattr(worker, "run_agents", run_agents)
    incident_runner = Mock()
    monkeypatch.setattr(incidents, "AgentRunner", incident_runner)
    review_runner = Mock()
    monkeypatch.setattr(reviews, "AgentRunner", review_runner)

    worker.main()

    (agents,) = run_agents.call_args.args
    routes = [(agent.topic, agent.return_topic, agent.kind) for agent in agents]
    assert routes == [
        (KafkaTopic.SRE_COMMANDS, KafkaTopic.SRE_RETURNS, RequestKind.INCIDENT),
        (KafkaTopic.PR_REVIEW_COMMANDS, KafkaTopic.PR_REVIEW_RETURNS, RequestKind.PR_REVIEW),
    ]
    for runner in (incident_runner, review_runner):
        runner.assert_called_once()
        runner.return_value.close.assert_called_once()
