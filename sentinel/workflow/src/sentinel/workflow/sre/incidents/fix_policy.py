from sentinel.core.contracts.changes import ProposedChange
from sentinel.core.contracts.executor import CreatePullRequest, PullRequestCreated
from sentinel.core.contracts.incidents import IncidentResult
from sentinel.core.digest import json_digest
from sentinel.core.domain import IncidentStatus, RepositoryIdentity
from sentinel.core.state import change_rules


def blocked(result: IncidentResult, reason: str) -> IncidentResult:
    diagnosis = result.diagnosis.model_copy(update={"hypothesis": f"Sentinel blocked the proposed fix. {reason}"})
    return result.model_copy(update={"status": IncidentStatus.BLOCKED, "diagnosis": diagnosis})


def failed(result: IncidentResult, error: str) -> IncidentResult:
    hypothesis = f"The incident fix could not be published: {error}."
    diagnosis = result.diagnosis.model_copy(update={"hypothesis": hypothesis})
    return result.model_copy(update={"status": IncidentStatus.FAILED, "diagnosis": diagnosis})


def fix_branch(changes: list[ProposedChange], prefix: str) -> str:
    dumped = [change.model_dump() for change in changes]
    ordered = sorted(dumped, key=lambda change: change["file_path"])
    digest = json_digest(ordered)
    return f"{prefix}/{digest[:16]}"


def decide(result: IncidentResult) -> IncidentResult | None:
    if not result.diagnosis.proposes_fix:
        return result.model_copy(update={"status": IncidentStatus.BLOCKED})
    reason = change_rules.rejection(result.diagnosis.proposed_changes)
    return blocked(result, reason) if reason else None


def pull_request_request(
    result: IncidentResult, repository: RepositoryIdentity, base_branch: str, branch_prefix: str
) -> CreatePullRequest:
    changes = result.diagnosis.proposed_changes
    branch = fix_branch(changes, branch_prefix)
    labels = [f"confidence:{result.diagnosis.confidence}", f"risk:{result.diagnosis.risk}"]
    return CreatePullRequest(
        repository=repository,
        base_branch=base_branch,
        branch=branch,
        changes=changes,
        title=result.diagnosis.pr_title or result.diagnosis.incident,
        body=result.diagnosis.pr_body or result.diagnosis.hypothesis,
        labels=labels,
    )


def submitted(result: IncidentResult, created: PullRequestCreated) -> IncidentResult:
    if created.rejected:
        return blocked(result, f"An identical fix was closed without merging: {created.url}.")
    return result.model_copy(update={"pull_request_url": created.url, "status": IncidentStatus.AWAITING})
