import contextlib
import json
import os
import pathlib
import typing as T
import urllib.error

import fastcore.basics
from ghapi.all import GhApi

import dandori.exception
import dandori.log
import dandori.ops

HTTPError = urllib.error.HTTPError
URLError = urllib.error.URLError

L = dandori.log.get_logger(__name__)


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
        self.payload: fastcore.basics.AttrDict = fastcore.basics.AttrDict()
        if self._path.exists():
            with self._path.open() as f:
                self.payload = fastcore.basics.AttrDict(json.load(f))
        self.api = GhApi(owner=self.owner, repo=self.name)
        self._pull_request = {}
        #
        if self.event_name == "issue_comment":
            if self.is_pull_request():
                self.event_name = "pull_request_comment"
                self._checkout_pull_request_branch()
        if self.event_name == "pull_request":
            if self.payload.get("action") == "synchronize":
                self.event_name = "pull_request_push"

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

    def pull_request(self, number: int = None):
        """Get pull request details"""
        try:
            if number is None and self.is_pull_request():
                if self._pull_request is None:
                    if "pull_request" in self.payload:
                        self._pull_request = self.payload["pull_request"]
                        L.debug("pull_request object from payload: keys=%s", self._pull_request.keys())
                    else:
                        self._pull_request = self.api.pulls.get(self.issue_number)
                        L.debug("pull_request object from API: keys=%s", self._pull_request.keys())
                return self._pull_request
            else:
                return self.api.pulls.get(number)
        except HTTPError as e:
            if e.code == 404:
                return None
            raise

    def is_pull_request(self):
        """event is related to pull request (pull request, pull request comment)"""
        if self.event_name == "pull_request":
            return True
        elif "pull_request" in self.payload.get("issue", {}):
            return True
        return False

    def latest_release_tag(self) -> str:
        """Return latest relesed tag"""
        try:
            resp = self.api.get_latest_release()
        except HTTPError as e:
            if e.code == 404:
                return ""
        return resp.tag_name

    def has_tag(self, tag: str):
        """Check a tag already exists"""
        results = self.api.list_tags(tag)
        refs = [x.ref for x in results]
        return f"refs/tags/{tag}" in refs

    def create_comment(self, body: str):
        """Create comment to its issue/pull_request"""
        if not self.issue_number:
            raise ValueError("issue number not found.")
        self.api.issues.create_comment(self.issue_number, body)

    def comment_body(self) -> str:
        """Get comment body if exists"""
        return self.payload.get("comment", {}).get("body", "")

    def create_release(self, *args, **kwargs):
        """Shorthand for api.create_release"""
        self.api.create_release(*args, **kwargs)

    @contextlib.contextmanager
    def check(self, name: str, sha=None):
        """Some proc with GitHub Checks API"""
        if sha is None:
            if self.is_pull_request():
                sha = self.pull_request()["head"]["sha"]
            elif self.sha:
                sha = self.sha
        try:
            conclusion = "success"
            check = self.api.checks.create(name=name, head_sha=sha, status="in_progress")
            yield
        except dandori.exception.Cancel:
            conclusion = "cancelled"
            raise
        except Exception:
            conclusion = "failure"
            raise
        finally:
            self.api.checks.update(name=name, check_run_id=check, status="completed", conclusion=conclusion)

    def _checkout_pull_request_branch(self):
        if pathlib.Path(".git").is_dir():
            ops = dandori.ops.Operation()
            pr = self.pull_request()
            ref = pr["merge_commit_sha"]
            L.info("Checkout to merge commit of PR #%d: %s", self.issue_number, ref)
            ops.run(["git", "fetch", "origin", f"+{ref}:refs/remotes/origin/merge_commit"])
            ops.run(["git", "checkout", "--force", "-B", "merge_commit", "refs/remotes/origin/merge_commit"])
