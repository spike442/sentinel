from sentinel.core.contracts.reviews import PullRequest
from sentinel.core.domain import RepositoryIdentity
from sentinel.core.github import GitHubAppAuth, GitHubReader
from sentinel.executor.settings import ExecutorSettings


class GitHubGateway(GitHubReader):
    def __init__(self, settings: ExecutorSettings):
        private_key = settings.github_private_key.get_secret_value()
        auth = GitHubAppAuth(settings.github_app_id, settings.github_installation_id, private_key)
        super().__init__(auth)

    def create_pull_request(
        self,
        repository: RepositoryIdentity,
        *,
        base_branch: str,
        head_branch: str,
        title: str,
        body: str,
        labels: list[str],
    ) -> str:
        path = f"/repos/{repository.owner}/{repository.name}/pulls"
        content = {"title": title, "head": head_branch, "base": base_branch, "body": body}
        created = self._json("POST", path, json=content)
        self.add_labels(repository, created["number"], labels)
        return created["html_url"]

    def find_pull_request(self, repository: RepositoryIdentity, base_branch: str, head_branch: str) -> dict | None:
        params = {"state": "all", "base": base_branch, "head": f"{repository.owner}:{head_branch}"}
        items = self._json("GET", f"/repos/{repository.owner}/{repository.name}/pulls", params=params)
        return items[0] if items else None

    def merge_pull_request(self, pull_request: PullRequest, merge_method: str) -> str:
        path = f"/repos/{pull_request.owner}/{pull_request.repository}/pulls/{pull_request.number}/merge"
        content = {"sha": pull_request.head_sha, "merge_method": merge_method}
        result = self._json("PUT", path, json=content)
        if not result["merged"]:
            raise RuntimeError(result["message"])
        return result["sha"]

    def add_labels(self, repository: RepositoryIdentity, number: int, labels: list[str]) -> None:
        path = f"/repos/{repository.owner}/{repository.name}/issues/{number}/labels"
        self._json("POST", path, json={"labels": labels})

    def create_commit(self, repository: RepositoryIdentity, parent_sha: str, tree: list[dict], message: str) -> str:
        """Create one commit of ``tree`` entries on ``parent_sha`` and return its SHA.

        It names no author, committer, or signature, so GitHub authors it as the App and signs it as verified.
        """
        git_path = f"/repos/{repository.owner}/{repository.name}/git"
        parent = self._json("GET", f"{git_path}/commits/{parent_sha}")
        created_tree = self._json("POST", f"{git_path}/trees", json={"base_tree": parent["tree"]["sha"], "tree": tree})
        content = {"message": message, "tree": created_tree["sha"], "parents": [parent_sha]}
        created = self._json("POST", f"{git_path}/commits", json=content)
        return created["sha"]

    def create_branch(self, repository: RepositoryIdentity, branch: str, sha: str) -> None:
        path = f"/repos/{repository.owner}/{repository.name}/git/refs"
        self._json("POST", path, json={"ref": f"refs/heads/{branch}", "sha": sha})

    def update_branch(self, repository: RepositoryIdentity, branch: str, sha: str) -> None:
        path = f"/repos/{repository.owner}/{repository.name}/git/refs/heads/{branch}"
        self._json("PATCH", path, json={"sha": sha, "force": False})
