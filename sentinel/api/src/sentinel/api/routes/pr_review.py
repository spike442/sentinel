from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sentinel.api.requests import PrReviewWorkflowRequests
from sentinel.api.routes.enabled import enabled_reader
from sentinel.core.domain import AgentDomain
from sentinel.core.persistence.queries import PrReviewReader

router = APIRouter(tags=["pr-review"])


class OperatorPrompt(BaseModel):
    prompt: str = ""


def _repository(request: Request) -> PrReviewReader:
    return enabled_reader(request, AgentDomain.PULL_REQUEST_REVIEW)


def _requests(request: Request) -> PrReviewWorkflowRequests:
    reviews = _repository(request)
    return PrReviewWorkflowRequests(request.app.state.settings, reviews)


@router.post("/events/pr-reviews/check", status_code=202)
async def check_reviews(
    request: Request,
) -> dict[str, str]:
    workflow_id = await _requests(request).check_reviews()
    return {"status": "accepted", "workflow_id": workflow_id}


@router.get("/pr-reviews")
def reviews(
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
    status: str | None = Query(default=None),
) -> dict:
    return {"reviews": _repository(request).list(limit, status)}


@router.delete("/pr-reviews/{review_id}", status_code=202)
async def delete_review(
    review_id: str,
    request: Request,
) -> dict[str, str]:
    workflow_id = await _requests(request).delete_review(review_id)
    return {"status": "accepted", "workflow_id": workflow_id}


@router.post("/pr-reviews/{review_id}/replay", status_code=202)
async def replay_review(
    review_id: str,
    request: Request,
    replay: OperatorPrompt,
) -> dict[str, str]:
    prompt = replay.prompt.strip()
    workflow_id = await _requests(request).replay_review(review_id, prompt)
    return {"status": "accepted", "workflow_id": workflow_id}


@router.post("/pr-reviews/{review_id}/fix", status_code=202)
async def fix_review(
    review_id: str,
    request: Request,
    fix: OperatorPrompt,
) -> dict[str, str]:
    prompt = fix.prompt.strip()
    workflow_id = await _requests(request).fix_review(review_id, prompt)
    return {"status": "accepted", "workflow_id": workflow_id}
