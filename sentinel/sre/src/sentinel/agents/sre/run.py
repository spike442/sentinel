import logging
import subprocess
from datetime import datetime
from functools import partial
from pathlib import Path

from sentinel.agents.sre.agent import DiagnosisAgent
from sentinel.core.contracts.incidents import Diagnosis, IncidentResult, PreparedIncident
from sentinel.core.contracts.reviews import RepositoryConfig
from sentinel.core.deadline import RunTimedOut, remaining_seconds
from sentinel.core.domain import DiagnosisStatus, IncidentStatus
from sentinel.core.git import sync_checkout
from sentinel.core.observability.audit import AuditLog

logger = logging.getLogger(__name__)

REPOSITORY_ROOT = Path("/data/repositories")


def git(arguments: list[str], deadline: datetime) -> str:
    timeout = remaining_seconds(deadline)
    try:
        result = subprocess.run(["git", *arguments], capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RunTimedOut("git did not finish before the run's deadline") from exc
    if result.returncode:
        raise RuntimeError(f"git operation failed: {result.stderr[-1000:]}")
    return result.stdout


def sync_repository(repository: RepositoryConfig, deadline: datetime) -> dict[str, str]:
    path = REPOSITORY_ROOT / repository.name
    run_git = partial(git, deadline=deadline)
    sync_checkout(run_git, path, repository.clone_url, repository.branch)
    output = run_git(["-C", str(path), "rev-parse", "HEAD"])
    commit = output.strip()
    return {"path": str(path), "branch": repository.branch, "commit": commit}


def incident_status(diagnosis: Diagnosis) -> IncidentStatus:
    return IncidentStatus.BLOCKED if diagnosis.status is DiagnosisStatus.BLOCKED else IncidentStatus.RUNNING


def failed_diagnosis(error: Exception) -> Diagnosis:
    return Diagnosis(
        incident="alert investigation failed",
        hypothesis=f"The investigation could not complete: {type(error).__name__}.",
        evidence=["The incident can be retried because no completed incident fix was recorded."],
        validation=["No fix was proposed."],
        rollback="No change was made.",
    )


class IncidentInvestigation:
    def __init__(self, agent: DiagnosisAgent):
        self.agent = agent

    def investigate(self, request: PreparedIncident, deadline: datetime) -> IncidentResult:
        audit = AuditLog()
        incident_id = request.incident_id
        logger.info("incident investigation started incident_id=%s kind=%s", incident_id, request.kind)
        try:
            remaining_seconds(deadline)
            synced = sync_repository(request.repository, deadline)
            audit.record("repository_sync", synced)
            logger.info("repository synced incident_id=%s commit=%s", incident_id, synced["commit"])
            workspace = Path(synced["path"])
            diagnosis = self.agent.diagnose(request, workspace, audit, deadline)
            status = incident_status(diagnosis)
            logger.info(
                "incident investigated incident_id=%s status=%s risk=%s confidence=%s",
                incident_id,
                status,
                diagnosis.risk,
                diagnosis.confidence,
            )
        except Exception as exc:
            logger.exception("incident investigation failed incident_id=%s", incident_id)
            error_type = type(exc).__name__
            audit.record("workflow_failed", {"error": error_type})
            status = IncidentStatus.FAILED
            diagnosis = failed_diagnosis(exc)
        budget = audit.tool_budget
        if budget.exhausted:
            exhausted = ",".join(budget.exhausted_tools)
            logger.warning(
                "incident tool budget exhausted incident_id=%s limit=%s tools=%s calls=%s",
                incident_id,
                budget.limit,
                exhausted,
                budget.calls,
            )
        return IncidentResult(status=status, diagnosis=diagnosis, audit_actions=audit.actions, tool_budget=budget)
