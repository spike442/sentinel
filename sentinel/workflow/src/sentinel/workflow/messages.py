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
    WorkflowRequest,
)
from sentinel.core.kafka.producer import publish, publish_outcome
from sentinel.core.persistence.queries import RecordReader
from sentinel.workflow.discord import DiscordWebhook

logger = logging.getLogger(__name__)


class DomainMessages:
    def __init__(
        self,
        settings: CommonSettings,
        domain: AgentDomain,
        agent_topic: KafkaTopic,
        agent_kind: RequestKind,
        *,
        records: RecordReader,
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

    def command_agent(self, workflow_id: str, prepared: BaseModel) -> None:
        payload = prepared.model_dump(mode="json")
        command = AgentCommand(kind=self.agent_kind, workflow_id=workflow_id, payload=payload)
        publish(self.settings, self.agent_topic, workflow_id, command)

    def command_executor(
        self, action: ExecutorAction, workflow_id: str, payload: BaseModel, context: BaseModel | None = None
    ) -> None:
        payload_json = payload.model_dump(mode="json")
        context_json = context.model_dump(mode="json") if context is not None else {}
        command = ExecutorCommand(
            action=action,
            domain=self.domain,
            workflow_id=workflow_id,
            payload=payload_json,
            context=context_json,
        )
        publish(self.settings, KafkaTopic.EXECUTOR_COMMANDS, workflow_id, command)

    def schedule(self, kind: RequestKind, workflow_id: str, payload: BaseModel | None = None) -> None:
        fields = payload.model_dump(mode="json") if payload is not None else {}
        request = WorkflowRequest(domain=self.domain, kind=kind, workflow_id=workflow_id, payload=fields)
        publish(self.settings, KafkaTopic.WORKFLOW_REQUESTS, workflow_id, request)

    def announce_outcome(self, entity_id: str, workflow_id: str, *, require_owner: bool = True) -> None:
        current = self.records.get(entity_id)
        if current is None:
            return
        if require_owner and current["workflow_id"] != workflow_id:
            return
        publish_outcome(self.settings, self.domain, workflow_id, current)

    def notify(self, entity_id: str) -> None:
        try:
            current = self.records.get(entity_id)
            if current is None or current["workflow_id"] is None:
                return
            text = self.describe(current)
            self.discord.post(text)
        except Exception:
            logger.exception("Could not send the %s notification for %s", self.domain, entity_id)
