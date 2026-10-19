from collections.abc import Generator, Mapping
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

import httpx
import jwt
from sentinel.core.contracts.reviews import PullRequest, PullRequestState, RepositoryConfig

GITHUB_API_URL = "https://api.github.com"
TOKEN_REFRESH_MARGIN = timedelta(minutes=1)
READ_ONLY = MappingProxyType({"metadata": "read", "pull_requests": "read"})
MAX_REASON_CHARS = 500


class GitHubRejected(RuntimeError):
    def __init__(self, method: str, path: str, status_code: int, reason: str):
        super().__init__(f"GitHub rejected {method} {path}: HTTP {status_code}: {reason[:MAX_REASON_CHARS]}")


def clean_and_mergeable(item: dict) -> bool:
    return item.get("mergeable") is True and item.get("mergeable_state") == "clean"


def rejected(pull_request: dict) -> bool:
    return pull_request.get("state") == "closed" and not pull_request.get("merged_at")


def merged_commit(item: dict, head_sha: str) -> str | None:
    if item["merged"] and item["head"]["sha"] == head_sha:
        return item["merge_commit_sha"]
    return None


def pull_request_from(repository: RepositoryConfig, item: dict) -> PullRequest:
    labels = [label["name"] for label in item["labels"]]
    head_repo = item["head"]["repo"] or {}
    head_repository = head_repo.get("full_name", "")
    return PullRequest(
        owner=repository.owner,
        repository=repository.name,
        number=item["number"],
        base_sha=item["base"]["sha"],
        head_sha=item["head"]["sha"],
        html_url=item["html_url"],
        updated_at=item["updated_at"],
        title=item["title"],
        author=item["user"]["login"],
        head_ref=item["head"]["ref"],
        head_repository=head_repository,
        labels=labels,
    )


def open_revision(repository: RepositoryConfig, item: dict) -> PullRequest | None:
    if item["state"] != "open":
        return None
    current = pull_request_from(repository, item)
    mergeable = clean_and_mergeable(item)
    return current.model_copy(update={"mergeable": mergeable})


class GitHubAppAuth(httpx.Auth):
    """Authenticate every request as the installed GitHub App, caching its token until shortly before expiry.

    ``permissions`` narrows each installation token to a subset of the App's permissions.
    """

    def __init__(
        self,
        app_id: str,
        installation_id: str,
        private_key: str,
        permissions: Mapping[str, str] | None = None,
    ) -> None:
        self._token_url = f"{GITHUB_API_URL}/app/installations/{installation_id}/access_tokens"
        self._app_id = app_id
        self._private_key = private_key
        self._permissions = dict(permissions) if permissions else None
        self._client = httpx.Client(timeout=30)
        self._token = ""
        self._token_expires_at = datetime.min.replace(tzinfo=UTC)

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        token = self.installation_token()
        request.headers["Authorization"] = f"Bearer {token}"
        yield request

    def installation_token(self) -> str:
        now = datetime.now(UTC)
        if self._token and now < self._token_expires_at - TOKEN_REFRESH_MARGIN:
            return self._token
        issued_at = now - timedelta(seconds=30)
        expires_at = now + timedelta(minutes=9)
        issued_seconds = issued_at.timestamp()
        expires_seconds = expires_at.timestamp()
        claims = {"iat": int(issued_seconds), "exp": int(expires_seconds), "iss": self._app_id}
        app_jwt = jwt.encode(claims, self._private_key, algorithm="RS256")
        body = {"permissions": self._permissions} if self._permissions else None
        response = self._client.post(self._token_url, headers={"Authorization": f"Bearer {app_jwt}"}, json=body)
        response.raise_for_status()
        payload = response.json()
        self._token = payload["token"]
        expiry = payload["expires_at"].replace("Z", "+00:00")
        self._token_expires_at = datetime.fromisoformat(expiry)
        return self._token

    def close(self) -> None:
        self._client.close()


class GitHubReader:
    def __init__(self, auth: GitHubAppAuth):
        self.auth = auth
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        self.client = httpx.Client(base_url=GITHUB_API_URL, headers=headers, auth=auth, timeout=30)

    def open_pull_requests(self, repository: RepositoryConfig) -> list[PullRequest]:
        path = f"/repos/{repository.owner}/{repository.name}/pulls"
        params = {"state": "open", "sort": "updated", "direction": "desc", "per_page": 100}
        items = self._json("GET", path, params=params)
        return [pull_request_from(repository, item) for item in items]

    def current(self, owner: str, repository: str, number: int) -> dict:
        return self._json("GET", f"/repos/{owner}/{repository}/pulls/{number}")

    def reviewable_pull_requests(self, repositories: list[RepositoryConfig]) -> list[PullRequest]:
        pull_requests: list[PullRequest] = []
        for repository in repositories:
            open_pull_requests = self.open_pull_requests(repository)
            for pull_request in open_pull_requests:
                item = self.current(pull_request.owner, pull_request.repository, pull_request.number)
                mergeable = clean_and_mergeable(item)
                current = pull_request.model_copy(update={"mergeable": mergeable})
                pull_requests.append(current)
        return pull_requests

    def pull_request_state(self, repository: RepositoryConfig, number: int, head_sha: str) -> PullRequestState:
        item = self.current(repository.owner, repository.name, number)
        merged_sha = merged_commit(item, head_sha)
        if merged_sha:
            return PullRequestState(merged_sha=merged_sha)
        revision = open_revision(repository, item)
        return PullRequestState(pull_request=revision)

    def close(self) -> None:
        self.client.close()
        self.auth.close()

    def _json(self, method: str, path: str, **kwargs) -> dict | list:
        response = self.client.request(method, path, **kwargs)
        if response.is_error:
            raise GitHubRejected(method, path, response.status_code, response.text)
        return response.json()
