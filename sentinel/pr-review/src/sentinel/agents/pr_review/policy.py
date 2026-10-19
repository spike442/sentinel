from sentinel.agents.pr_review.settings import PrReviewConfig
from sentinel.core.contracts.reviews import PrReviewDecision, PrReviewResult


def decide_merge(review: PrReviewResult, config: PrReviewConfig, checks_passed: bool) -> PrReviewDecision:
    if not checks_passed:
        return PrReviewDecision(merge=False, reason="one or more validation checks failed")
    if review.risk not in config.allowed_risk_levels:
        return PrReviewDecision(merge=False, reason=f"risk level is {review.risk}")
    if review.confidence not in config.allowed_confidence_levels:
        return PrReviewDecision(merge=False, reason=f"confidence level is {review.confidence}")
    return PrReviewDecision(merge=True, reason="validation passed and policy allows merge")
