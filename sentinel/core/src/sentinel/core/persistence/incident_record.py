from datetime import datetime
from typing import Any

from sentinel.core.persistence.postgres import Base
from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class IncidentRecord(Base):
    __tablename__ = "incidents"
    __table_args__ = (Index("incidents_listing", "updated_at"),)

    entity_id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_id: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    alert: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    diagnosis: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    pull_request_url: Mapped[str | None] = mapped_column(String)
    review_id: Mapped[str | None] = mapped_column(String)
    replayed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    manual_actions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    timeline: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    attempts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    tool_budget: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.entity_id,
            "workflow_id": self.workflow_id,
            "updated_at": self.updated_at.isoformat(),
            "status": self.status,
            "repository": self.repository,
            "source": self.source,
            "alert": self.alert,
            "diagnosis": self.diagnosis,
            "pull_request_url": self.pull_request_url,
            "review_id": self.review_id,
            "replayed_at": self.replayed_at.isoformat() if self.replayed_at else None,
            "manual_actions": self.manual_actions,
            "timeline": self.timeline,
            "attempts": self.attempts,
            "tool_budget": self.tool_budget,
        }
