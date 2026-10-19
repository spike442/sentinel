import logging
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path

from sentinel.core.kafka.consumer import KafkaConsumer, exit_on_signals, stop_on_signals
from sentinel.core.kafka.contracts import (
    ExecutorAction,
    ExecutorCommand,
    ExecutorReturn,
    KafkaMessage,
    KafkaTopic,
)
from sentinel.core.kafka.producer import publish_return
from sentinel.core.observability.logging import configure_logging
from sentinel.executor.actions import WORKSPACE, Executor
from sentinel.executor.git_workspace import GitWorkspace
from sentinel.executor.github import GitHubGateway
from sentinel.executor.settings import ExecutorSettings

logger = logging.getLogger(__name__)

HEARTBEAT = Path("/tmp/sentinel-worker-heartbeat")
AT_MOST_ONCE = frozenset({ExecutorAction.RUN_COMMAND})


class CommandHandler:
    def __init__(self, settings: ExecutorSettings, executor: Executor):
        self.settings = settings
        self.executor = executor

    def __call__(self, message: KafkaMessage) -> None:
        command = ExecutorCommand.model_validate(message.payload)
        if command.action in AT_MOST_ONCE:
            message.commit()
        event = self._execute(command)
        publish_return(self.settings, KafkaTopic.EXECUTOR_RETURNS, event)

    def _execute(self, command: ExecutorCommand) -> ExecutorReturn:
        try:
            outcome = self.executor.execute_command(command)
            result = outcome.model_dump(mode="json")
            error = None
        except Exception as exc:
            logger.exception("Executor action failed action=%s workflow_id=%s", command.action, command.workflow_id)
            result, error = None, type(exc).__name__
        command_fields = command.model_dump(exclude={"payload"})
        return ExecutorReturn(**command_fields, result=result, error=error)


def main() -> None:
    exit_on_signals()
    settings = ExecutorSettings()
    configure_logging(settings.logging.level)
    with ExitStack() as resources:
        github = GitHubGateway(settings)
        resources.callback(github.close)
        config = settings.executor
        git = GitWorkspace(WORKSPACE / "repositories", github)
        executor = Executor(config, github, git)
        consumer = KafkaConsumer(settings, KafkaTopic.EXECUTOR_COMMANDS, "executor", HEARTBEAT)
        resources.callback(consumer.close)
        stop_on_signals(consumer.stop)
        release = version("sentinel-core")
        logger.info("sentinel-executor ready version=%s", release)
        handler = CommandHandler(settings, executor)
        consumer.run(handler)


if __name__ == "__main__":
    main()
