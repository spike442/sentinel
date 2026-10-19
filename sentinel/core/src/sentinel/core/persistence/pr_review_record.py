from datetime import datetime
from typing import Any

from sentinel.core.persistence.postgres import Base
from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class PrReviewRecord(Base):
    __tablename__ = "pr_reviews"
    __table_args__ = (Index("reviews_listing", "updated_at"),)

    entity_id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_id: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    owner: Mapped[str] = mapped_column(String, nullable=False)
    pull_request_number: Mapped[int] = mapped_column(Integer, nullable=False)
    base_sha: Mapped[str] = mapped_column(String, nullable=False)
    head_sha: Mapped[str] = mapped_column(String, nullable=False)
    pull_request_url: Mapped[str] = mapped_column(String, nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    risk: Mapped[str | None] = mapped_column(String)
    confidence: Mapped[str | None] = mapped_column(String)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    findings: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    merge: Mapped[bool | None] = mapped_column(Boolean)
    decision_reason: Mapped[str] = mapped_column(String, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merge_commit_sha: Mapped[str] = mapped_column(String, nullable=False)
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
            "owner": self.owner,
            "pull_request_number": self.pull_request_number,
            "base_sha": self.base_sha,
            "head_sha": self.head_sha,
            "pull_request_url": self.pull_request_url,
            "checks": self.checks,
            "risk": self.risk,
            "confidence": self.confidence,
            "summary": self.summary,
            "findings": self.findings,
            "merge": self.merge,
            "decision_reason": self.decision_reason,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "merged_at": self.merged_at.isoformat() if self.merged_at else None,
            "merge_commit_sha": self.merge_commit_sha,
            "timeline": self.timeline,
            "attempts": self.attempts,
            "tool_budget": self.tool_budget,
        }
