from __future__ import annotations

from typing import Any

from sentinel.core.persistence.incident_record import IncidentRecord
from sentinel.core.persistence.postgres import PostgresDatabase
from sentinel.core.persistence.pr_review_record import PrReviewRecord
from sqlalchemy import func, select

RUNNING_ACTIONS_LIMIT = 500


class RecordReader:
    model: type[IncidentRecord] | type[PrReviewRecord]

    def __init__(self, database: PostgresDatabase):
        self.database = database

    def get(self, entity_id: str) -> dict[str, Any] | None:
        with self.database.sessions() as session:
            record = session.get(self.model, entity_id)
            return record.to_dict() if record else None

    def list(self, limit: int, status: str | None = None, *, oldest_first: bool = False) -> list[dict[str, Any]]:
        statement = select(self.model)
        if status:
            statement = statement.where(self.model.status == status)
        updated = self.model.updated_at.asc() if oldest_first else self.model.updated_at.desc()
        statement = statement.order_by(updated, self.model.entity_id).limit(limit)
        with self.database.sessions() as session:
            records = session.scalars(statement)
            return [record.to_dict() for record in records]

    def status_counts(self) -> dict[str, int]:
        with self.database.sessions() as session:
            statement = select(self.model.status, func.count()).group_by(self.model.status)
            rows = session.execute(statement)
            pairs = rows.all()
            return dict(pairs)


class IncidentReader(RecordReader):
    model = IncidentRecord

    def incident_for(self, pull_request_url: str) -> str | None:
        statement = select(IncidentRecord.entity_id).where(IncidentRecord.pull_request_url == pull_request_url).limit(1)
        with self.database.sessions() as session:
            return session.scalar(statement)

    def running_manual_actions(self) -> list[dict[str, Any]]:
        statement = (
            select(IncidentRecord)
            .where(IncidentRecord.manual_actions.contains([{"status": "running"}]))
            .order_by(IncidentRecord.updated_at)
            .limit(RUNNING_ACTIONS_LIMIT)
        )
        with self.database.sessions() as session:
            records = session.scalars(statement)
            return [record.to_dict() for record in records]


class PrReviewReader(RecordReader):
    model = PrReviewRecord
