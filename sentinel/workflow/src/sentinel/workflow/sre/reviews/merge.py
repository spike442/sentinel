from sentinel.core.config.workflow import PrReviewSettings
from sentinel.core.contracts.executor import MergeOutcome, MergePullRequest, MergeStatus
from sentinel.core.contracts.reviews import PullRequest
from sentinel.core.kafka.contracts import ExecutorAction, ExecutorReturn
from sentinel.workflow.messages import DomainMessages
from sentinel.workflow.sre.reviews.repository import PrReviewRepository


class Merge:
    def __init__(self, settings: PrReviewSettings, reviews: PrReviewRepository, messages: DomainMessages):
        self.merge_method = settings.merge_method
        self.reviews = reviews
        self.messages = messages

    def start_merge(self, review_id: str, pull_request: PullRequest, workflow_id: str) -> None:
        merge = MergePullRequest(pull_request=pull_request, merge_method=self.merge_method)
        self.messages.command_executor(ExecutorAction.MERGE_PULL_REQUEST, review_id, workflow_id, merge)

    def on_executor_return(self, executor_return: ExecutorReturn) -> None:
        review_id = executor_return.record_id
        workflow_id = executor_return.workflow_id
        if executor_return.result is None:
            self.messages.fail(
                review_id, workflow_id, f"GitHub merge failed: {executor_return.error or 'ExecutorFailed'}"
            )
            return
        outcome = MergeOutcome.model_validate(executor_return.result)
        if outcome.status is not MergeStatus.MERGED:
            self.messages.fail(review_id, workflow_id, "GitHub no longer reports the PR mergeable and clean")
            return
        self.reviews.mark_merged(review_id, outcome.sha)
