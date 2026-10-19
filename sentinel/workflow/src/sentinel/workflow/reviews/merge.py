from pydantic import BaseModel
from sentinel.core.config.workflow import PrReviewSettings
from sentinel.core.contracts.executor import MergeOutcome, MergePullRequest, MergeStatus
from sentinel.core.contracts.reviews import PullRequest
from sentinel.core.kafka.contracts import ExecutorAction, ExecutorReturn
from sentinel.workflow.messages import DomainMessages
from sentinel.workflow.reviews.repository import PrReviewRepository


class MergeContext(BaseModel):
    review_id: str


class Merge:
    def __init__(self, settings: PrReviewSettings, reviews: PrReviewRepository, messages: DomainMessages):
        self.merge_method = settings.merge_method
        self.reviews = reviews
        self.messages = messages

    def start_merge(self, review_id: str, pull_request: PullRequest, workflow_id: str) -> None:
        merge = MergePullRequest(pull_request=pull_request, merge_method=self.merge_method)
        context = MergeContext(review_id=review_id)
        self.messages.command_executor(ExecutorAction.MERGE_PULL_REQUEST, workflow_id, merge, context)

    def on_executor_return(self, executor_return: ExecutorReturn) -> None:
        review_id = MergeContext.model_validate(executor_return.context).review_id
        workflow_id = executor_return.workflow_id
        if executor_return.result is None:
            error = f"GitHub merge failed: {executor_return.error or 'ExecutorFailed'}"
            self.reviews.fail_review(review_id, workflow_id, error)
        else:
            outcome = MergeOutcome.model_validate(executor_return.result)
            if outcome.status is MergeStatus.MERGED:
                self.reviews.mark_merged(review_id, outcome.sha)
            else:
                self.reviews.fail_review(review_id, workflow_id, "GitHub no longer reports the PR mergeable and clean")
        self.messages.announce_outcome(review_id, workflow_id)
