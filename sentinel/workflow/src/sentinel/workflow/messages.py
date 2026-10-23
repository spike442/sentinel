import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from sentinel.core.config.common import CommonSettings
from sentinel.core.domain import AgentDomain
from sentinel.core.kafka.contracts import (
    AgentCommand,
    ExecutorAction,
    ExecutorCommand,
    KafkaTopic,
    RequestKind,
    RunFailure,
    WorkflowRequest,
)
from sentinel.core.kafka.producer import publish
from sentinel.workflow.discord import DiscordWebhook
from sentinel.workflow.repository import DomainRecords

logger = logging.getLogger(__name__)


class DomainMessages:
    def __init__(
        self,
        settings: CommonSettings,
        domain: AgentDomain,
        agent_topic: KafkaTopic,
        agent_kind: RequestKind,
        *,
        records: DomainRecords,
        describe: Callable[[dict[str, Any]], str],
        discord: DiscordWebhook,
    ):
        self.settings = settings
        self.domain = domain
        self.agent_topic = agent_topic
        self.agent_kind = agent_kind
        self.records = records
        self.describe = describe
        self.discord = discord

    def command_agent(self, record_id: str, workflow_id: str, prepared: BaseModel) -> None:
        payload = prepared.model_dump(mode="json")
        command = AgentCommand(kind=self.agent_kind, record_id=record_id, workflow_id=workflow_id, payload=payload)
        publish(self.settings, self.agent_topic, workflow_id, command)

    def command_executor(
        self,
        action: ExecutorAction,
        record_id: str,
        workflow_id: str,
        payload: BaseModel,
        *,
        context: BaseModel | None = None,
    ) -> None:
        payload_json = payload.model_dump(mode="json")
        context_json = context.model_dump(mode="json") if context is not None else {}
        command = ExecutorCommand(
            action=action,
            domain=self.domain,
            record_id=record_id,
            workflow_id=workflow_id,
            payload=payload_json,
            context=context_json,
        )
        publish(self.settings, KafkaTopic.EXECUTOR_COMMANDS, workflow_id, command)

    def schedule(
        self, kind: RequestKind, workflow_id: str, payload: BaseModel | None = None, *, record_id: str | None = None
    ) -> None:
        fields = payload.model_dump(mode="json") if payload is not None else {}
        request = WorkflowRequest(
            domain=self.domain, kind=kind, record_id=record_id, workflow_id=workflow_id, payload=fields
        )
        publish(self.settings, KafkaTopic.WORKFLOW_REQUESTS, workflow_id, request)

    def fail(self, record_id: str, workflow_id: str, failure: RunFailure | str) -> None:
        run_failure = RunFailure(error=failure) if isinstance(failure, str) else failure
        self.records.fail(record_id, workflow_id, run_failure)

    def notify(self, entity_id: str) -> None:
        try:
            current = self.records.get(entity_id)
            if current is None or current["workflow_id"] is None:
                return
            text = self.describe(current)
            self.discord.post(text)
        except Exception:
            logger.exception("Could not send the %s notification for %s", self.domain, entity_id)
