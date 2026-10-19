from unittest.mock import Mock

from sentinel.core.kafka.contracts import KafkaTopic


def test_workflow_starts_enabled_domain_consumers(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_DATABASE_PASSWORD", "test")
    monkeypatch.setenv("SENTINEL_KAFKA_USERNAME", "sentinel")
    monkeypatch.setenv("SENTINEL_KAFKA_PASSWORD", "test")
    monkeypatch.setenv("SENTINEL_GITHUB_APP_ID", "1")
    monkeypatch.setenv("SENTINEL_GITHUB_INSTALLATION_ID", "2")
    monkeypatch.setenv("SENTINEL_GITHUB_APP_PRIVATE_KEY", "test")
    monkeypatch.setenv("SENTINEL_DISCORD_WEBHOOK_URL", "https://discord.example/api/webhooks/1/test")
    from sentinel.workflow import __main__ as workflow

    monkeypatch.setattr(workflow, "PostgresDatabase", Mock())
    monkeypatch.setattr(workflow, "KnowledgeClient", Mock())
    monkeypatch.setattr(workflow, "AlertmanagerClient", Mock())
    monkeypatch.setattr(workflow, "GitHubReader", Mock())
    monkeypatch.setattr(workflow, "DiscordWebhook", Mock())
    run = Mock()
    monkeypatch.setattr(workflow, "run", run)

    shared = [KafkaTopic.WORKFLOW_REQUESTS, KafkaTopic.EXECUTOR_RETURNS]
    scenarios = [
        (
            '["sre", "pr-review"]',
            [KafkaTopic.CLUSTER_ALERTS, KafkaTopic.SRE_RETURNS, KafkaTopic.PR_REVIEW_RETURNS, *shared],
            3,
        ),
        ('["sre"]', [KafkaTopic.CLUSTER_ALERTS, KafkaTopic.SRE_RETURNS, *shared], 1),
        ('["pr-review"]', [KafkaTopic.PR_REVIEW_RETURNS, *shared], 2),
    ]
    for agents, expected_topics, expected_jobs in scenarios:
        monkeypatch.setenv("SENTINEL_AGENTS", agents)
        workflow.main()
        _settings, routes, jobs = run.call_args.args
        assert [topic for topic, _ in routes] == expected_topics
        assert len(jobs) == expected_jobs
