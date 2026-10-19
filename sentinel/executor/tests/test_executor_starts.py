from unittest.mock import Mock

from sentinel.core.kafka.contracts import KafkaTopic


def test_executor_starts_consuming_commands(monkeypatch) -> None:
    monkeypatch.setenv("SENTINEL_GITHUB_APP_ID", "1")
    monkeypatch.setenv("SENTINEL_GITHUB_INSTALLATION_ID", "2")
    monkeypatch.setenv("SENTINEL_GITHUB_APP_PRIVATE_KEY", "test")
    monkeypatch.setenv("SENTINEL_KAFKA_USERNAME", "sentinel")
    monkeypatch.setenv("SENTINEL_KAFKA_PASSWORD", "test")
    from sentinel.executor import worker

    consumer = Mock()
    consumer_class = Mock(return_value=consumer)
    monkeypatch.setattr(worker, "GitHubGateway", Mock())
    monkeypatch.setattr(worker, "KafkaConsumer", consumer_class)
    monkeypatch.setattr(worker, "stop_on_signals", Mock())

    worker.main()

    assert consumer_class.call_args.args[1] is KafkaTopic.EXECUTOR_COMMANDS
    handler = consumer.run.call_args.args[0]
    assert isinstance(handler, worker.CommandHandler)
    consumer.close.assert_called_once()
