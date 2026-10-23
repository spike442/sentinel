from sentinel.core.contracts.executor import PushFix
from sentinel.core.contracts.reviews import ProposedPrFix, RepositoryConfig
from sentinel.core.state import change_rules


def rejection(proposal: ProposedPrFix) -> str | None:
    fix = proposal.fix
    if not fix.changes:
        return f"The reviewer proposed no change. {fix.summary}"
    unsafe = change_rules.rejection(fix.changes)
    if unsafe:
        return unsafe
    failing = [check.name for check in proposal.checks if not check.passed]
    if failing:
        names = ", ".join(failing)
        return f"The fixed revision still fails {names}."
    return None


def push_request(proposal: ProposedPrFix, repository: RepositoryConfig) -> PushFix:
    pull_request = proposal.pull_request
    message = proposal.fix.commit_message or f"Fix review findings of #{pull_request.number}"
    return PushFix(
        repository=repository,
        branch=pull_request.head_ref,
        head_sha=pull_request.head_sha,
        changes=proposal.fix.changes,
        message=message,
    )
