import json
import os
import pathlib
import typing as T

from ghapi.all import GhApi


class GitHub:
    def __init__(self):
        """Read GitHub Actions info automatically, and provide some convenient methods"""
        self._path = pathlib.Path(os.environ["GITHUB_EVENT_PATH"])
        self.repository: str = os.environ["GITHUB_REPOSITORY"]
        self.event_name: str = os.environ["GITHUB_EVENT_NAME"]
        self.sha: str = os.environ["GITHUB_SHA"]
        self.ref: str = os.environ["GITHUB_REF"]
        self.workflow: str = os.environ["GITHUB_WORKFLOW"]
        self.action: str = os.environ["GITHUB_ACTION"]
        self.actor: str = os.environ["GITHUB_ACTOR"]
        self.job: str = os.environ["GITHUB_JOB"]
        self.run_number: int = int(os.environ["GITHUB_RUN_NUMBER"])
        self.run_id: int = int(os.environ["GITHUB_RUN_ID"])
        self.payload: dict = {}
        if self._path.exists():
            with self._path.open() as f:
                self.payload = json.load(f)
        self.api = GhApi(owner=self.owner, repo=self.name)

    def create_comment(self, body: str):
        """Create comment to its issue/pull_request"""
        if not self.issue_number:
            raise ValueError("issue number not found.")
        self.api.issues.create_comment(self.issue_number, body)

    def comment_body(self) -> str:
        """Get comment body if exists"""
        return self.payload.get("body", "")

    @property
    def owner(self) -> str:
        """Return owner: repository=owner/name"""
        return self.repository.split("/")[0]

    @property
    def name(self) -> str:
        """Return repository name: repository=owner/name"""
        return self.repository.split("/")[1]

    @property
    def issue_number(self) -> T.Optional[int]:
        """issue number if exists"""
        if "issue" in self.payload:
            return self.payload["issue"]["number"]
        elif "pull_request" in self.payload:
            return self.payload["pull_request"]["number"]
        return None
