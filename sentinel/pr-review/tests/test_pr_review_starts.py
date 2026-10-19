from unittest.mock import Mock

from sentinel.core.kafka.contracts import KafkaTopic, RequestKind


def test_pr_review_agent_starts_and_builds_its_workflow(monkeypatch) -> None:
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("LLM_API_KEY", "test")
    monkeypatch.setenv("SENTINEL_KAFKA_USERNAME", "sentinel")
    monkeypatch.setenv("SENTINEL_KAFKA_PASSWORD", "test")
    from sentinel.agents.pr_review import runtime, worker

    run_agent = Mock()
    monkeypatch.setattr(worker, "run_agent", run_agent)
    review_agent = Mock()
    monkeypatch.setattr(runtime, "ReviewAgent", review_agent)

    worker.main()

    _settings, topic, return_topic, kind, _execute = run_agent.call_args.args
    assert (topic, return_topic, kind) == (
        KafkaTopic.PR_REVIEW_COMMANDS,
        KafkaTopic.PR_REVIEW_RETURNS,
        RequestKind.PR_REVIEW,
    )
    review_agent.assert_called_once()
    review_agent.return_value.close.assert_called_once()
