"""
github_api.py
=============
GitHub REST API integration client for the Repository Health & Beginner Assistant.

Handles:
- Repository URL parsing and normalization
- Authenticated and unauthenticated requests
- Rate limit tracking and warnings
- Error handling (404 Not Found, 403 Rate Limit, Network timeouts)
- Data fetching for metadata, README, community profile, commits, issues, contributors, and releases
- Strict separation of Pull Requests from Issues
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import dateutil.parser
import requests


class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class RepoNotFoundError(GitHubAPIError):
    """Raised when repository does not exist or is private."""


class RateLimitExceededError(GitHubAPIError):
    """Raised when GitHub API rate limit is reached."""

    def __init__(self, message: str, reset_time: Optional[datetime] = None):
        super().__init__(message, status_code=403)
        self.reset_time = reset_time


class AuthenticationError(GitHubAPIError):
    """Raised when GitHub token is invalid."""


class EmptyRepoError(GitHubAPIError):
    """Raised when repository has no commits or default branch."""


def parse_repo_url(url_or_slug: str) -> Tuple[str, str]:
    """
    Parse and validate a GitHub repository URL or slug.

    Accepts formats:
    - 'https://github.com/owner/repo'
    - 'http://github.com/owner/repo/'
    - 'github.com/owner/repo'
    - 'owner/repo'
    - 'https://github.com/owner/repo.git'
    - 'https://github.com/owner/repo/tree/main'

    Returns:
        (owner, repo) as clean lowercase strings

    Raises:
        ValueError if the format is invalid
    """
    if not url_or_slug or not isinstance(url_or_slug, str):
        raise ValueError("Repository input cannot be empty.")

    clean_str = url_or_slug.strip()

    # Reject consecutive slashes in the path portion
    clean_no_proto = re.sub(r"^https?://", "", clean_str)
    if "//" in clean_no_proto:
        raise ValueError("Invalid repository URL: contains consecutive slashes.")

    # If it starts with git@github.com:owner/repo.git
    ssh_match = re.match(r"^git@github\.com:([\w.-]+)/([\w.-]+?)(?:\.git)?$", clean_str)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    # Normalize url scheme if missing
    if not clean_str.startswith(("http://", "https://")):
        if clean_str.startswith("github.com/"):
            clean_str = "https://" + clean_str
        elif "/" in clean_str and not clean_str.startswith("/"):
            # Could be slug 'owner/repo'
            parts = [p for p in clean_str.split("/") if p]
            if len(parts) >= 2:
                owner, repo = parts[0], parts[1]
                repo = re.sub(r"\.git$", "", repo)
                if _validate_owner_repo(owner, repo):
                    return owner, repo

    try:
        parsed = urlparse(clean_str)
    except Exception as e:
        raise ValueError(f"Failed to parse URL: {e}")

    netloc = parsed.netloc.lower()
    if netloc and netloc != "github.com":
        raise ValueError(f"Expected github.com domain, got '{parsed.netloc}'")

    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(path_parts) < 2:
        raise ValueError(
            "Invalid GitHub repository URL. Expected format: 'owner/repo' or 'https://github.com/owner/repo'"
        )

    owner = path_parts[0]
    repo = re.sub(r"\.git$", "", path_parts[1])

    if not _validate_owner_repo(owner, repo):
        raise ValueError(
            f"Invalid repository or owner name: '{owner}/{repo}'. "
            "GitHub usernames and repository names must contain only alphanumeric characters, hyphens, periods, or underscores."
        )

    return owner, repo


def _validate_owner_repo(owner: str, repo: str) -> bool:
    """Validate GitHub owner and repository naming conventions."""
    # GitHub username: 1-39 chars, alphanumeric or single hyphens, cannot begin/end with hyphen
    # GitHub repo: 1-100 chars, alphanumeric, hyphens, underscores, dots
    owner_pattern = r"^[a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38}$"
    repo_pattern = r"^[a-zA-Z0-9_.-]{1,100}$"
    return bool(re.match(owner_pattern, owner) and re.match(repo_pattern, repo))


class GitHubClient:
    """
    Client for interacting with the GitHub REST API v3.
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None, timeout: int = 15):
        """
        Initialize the GitHub client.

        Args:
            token: Optional GitHub Personal Access Token. If None, checks GITHUB_TOKEN env var.
            timeout: Network request timeout in seconds.
        """
        self.token = token or os.environ.get("GITHUB_TOKEN", "").strip() or None
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-Repo-Health-Assistant/1.0",
        })
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})

        # Track latest rate limit info
        self.rate_limit_info: Dict[str, Any] = {
            "limit": None,
            "remaining": None,
            "reset": None,
            "reset_datetime": None,
        }

    def _update_rate_limit(self, headers: requests.structures.CaseInsensitiveDict) -> None:
        """Update rate limit metadata from response headers."""
        if "X-RateLimit-Limit" in headers:
            try:
                self.rate_limit_info["limit"] = int(headers["X-RateLimit-Limit"])
                self.rate_limit_info["remaining"] = int(headers["X-RateLimit-Remaining"])
                reset_epoch = int(headers["X-RateLimit-Reset"])
                self.rate_limit_info["reset"] = reset_epoch
                self.rate_limit_info["reset_datetime"] = datetime.fromtimestamp(
                    reset_epoch, tz=timezone.utc
                )
            except (ValueError, TypeError):
                pass

    def request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> requests.Response:
        """
        Execute an HTTP GET request against the GitHub REST API.

        Args:
            endpoint: API path (e.g. '/repos/owner/repo') or full URL.
            params: Optional query parameters.

        Returns:
            requests.Response object.

        Raises:
            RepoNotFoundError, RateLimitExceededError, AuthenticationError, GitHubAPIError
        """
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            url = endpoint
        else:
            url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
        except requests.exceptions.Timeout:
            raise GitHubAPIError(f"Request timed out after {self.timeout}s: {url}")
        except requests.exceptions.ConnectionError:
            raise GitHubAPIError("Network connection error. Please verify your internet connection.")
        except requests.exceptions.RequestException as e:
            raise GitHubAPIError(f"HTTP request failed: {e}")

        self._update_rate_limit(resp.headers)

        # Handle specific HTTP error status codes
        if resp.status_code == 404:
            raise RepoNotFoundError(
                f"Repository not found or private (HTTP 404). URL: {url}"
            )
        elif resp.status_code == 401:
            raise AuthenticationError(
                "GitHub API Authentication failed (HTTP 401). Please check your token."
            )
        elif resp.status_code in (403, 429):
            # Check if this was a rate limit error
            is_rate_limit = (
                self.rate_limit_info.get("remaining") == 0
                or "rate limit" in resp.text.lower()
            )
            if is_rate_limit:
                reset_time = self.rate_limit_info.get("reset_datetime")
                reset_str = (
                    reset_time.strftime("%H:%M:%S UTC")
                    if reset_time
                    else "shortly"
                )
                msg = (
                    f"GitHub API rate limit exceeded. Limit resets at {reset_str}. "
                    "Provide a GitHub Personal Access Token in the sidebar to increase your limit from 60 to 5,000 requests/hour."
                )
                raise RateLimitExceededError(msg, reset_time=reset_time)
            raise GitHubAPIError(f"Access forbidden (HTTP {resp.status_code}): {resp.text}")
        elif resp.status_code >= 500:
            raise GitHubAPIError(
                f"GitHub API server error (HTTP {resp.status_code}). Please try again later."
            )
        elif resp.status_code == 409:
            # 409 Git Repository is empty
            raise EmptyRepoError("Repository is empty (Git conflict / no commits on default branch).")

        return resp

    def get_rate_limit(self) -> Dict[str, Any]:
        """Fetch current rate limit status from /rate_limit endpoint."""
        try:
            resp = self.request("/rate_limit")
            data = resp.json()
            core = data.get("resources", {}).get("core", {})
            reset_epoch = core.get("reset", 0)
            reset_dt = datetime.fromtimestamp(reset_epoch, tz=timezone.utc) if reset_epoch else None
            return {
                "limit": core.get("limit", 60),
                "remaining": core.get("remaining", 0),
                "reset_epoch": reset_epoch,
                "reset_datetime": reset_dt,
                "used": core.get("used", 0),
            }
        except Exception:
            return self.rate_limit_info

    def get_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetch basic repository metadata."""
        resp = self.request(f"/repos/{owner}/{repo}")
        data = resp.json()
        return {
            "owner": data.get("owner", {}).get("login", owner),
            "name": data.get("name", repo),
            "full_name": data.get("full_name", f"{owner}/{repo}"),
            "description": data.get("description") or "",
            "html_url": data.get("html_url", f"https://github.com/{owner}/{repo}"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "pushed_at": data.get("pushed_at"),
            "default_branch": data.get("default_branch", "main"),
            "stargazers_count": data.get("stargazers_count", 0),
            "forks_count": data.get("forks_count", 0),
            "open_issues_count": data.get("open_issues_count", 0),  # Note: includes PRs in GitHub metadata
            "subscribers_count": data.get("subscribers_count", 0),
            "size": data.get("size", 0),
            "language": data.get("language") or "Not specified",
            "license": data.get("license", {}).get("spdx_id") if data.get("license") else None,
            "license_name": data.get("license", {}).get("name") if data.get("license") else None,
            "archived": data.get("archived", False),
            "disabled": data.get("disabled", False),
            "fork": data.get("fork", False),
            "topics": data.get("topics", []),
            "has_issues": data.get("has_issues", True),
            "has_wiki": data.get("has_wiki", False),
        }

    def get_readme(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Check README file existence and metadata.

        Returns dict with:
        - exists: bool
        - name: file name
        - size: size in bytes
        - html_url: link to file
        """
        try:
            resp = self.request(f"/repos/{owner}/{repo}/readme")
            data = resp.json()
            return {
                "exists": True,
                "name": data.get("name", "README.md"),
                "size": data.get("size", 0),
                "html_url": data.get("html_url", ""),
                "download_url": data.get("download_url", ""),
            }
        except RepoNotFoundError:
            # README not found is a normal condition for some repositories
            return {
                "exists": False,
                "name": None,
                "size": 0,
                "html_url": None,
                "download_url": None,
            }

    def get_community_profile(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Retrieve community profile metrics (CONTRIBUTING, LICENSE, CODE_OF_CONDUCT, templates).
        """
        profile = {
            "health_percentage": 0,
            "has_readme": False,
            "has_license": False,
            "has_contributing": False,
            "has_code_of_conduct": False,
            "has_issue_template": False,
            "has_pull_request_template": False,
            "description": "",
        }

        try:
            resp = self.request(f"/repos/{owner}/{repo}/community/profile")
            if resp.status_code == 200:
                data = resp.json()
                profile["health_percentage"] = data.get("health_percentage", 0)
                profile["description"] = data.get("description") or ""
                files = data.get("files", {})
                profile["has_readme"] = bool(files.get("readme"))
                profile["has_license"] = bool(files.get("license"))
                profile["has_contributing"] = bool(files.get("contributing"))
                profile["has_code_of_conduct"] = bool(files.get("code_of_conduct"))
                profile["has_issue_template"] = bool(files.get("issue_template"))
                profile["has_pull_request_template"] = bool(files.get("pull_request_template"))
                return profile
        except GitHubAPIError:
            pass

        # Fallback check if community profile is unavailable
        readme_info = self.get_readme(owner, repo)
        profile["has_readme"] = readme_info["exists"]
        return profile

    def get_commits(
        self, owner: str, repo: str, since: Optional[datetime] = None, per_page: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent commits (up to per_page, max 100) on default branch.

        Args:
            owner: Repository owner
            repo: Repository name
            since: Optional ISO datetime to filter commits
            per_page: Number of commits to retrieve (max 100)
        """
        params: Dict[str, Any] = {"per_page": min(per_page, 100)}
        if since:
            params["since"] = since.isoformat()

        try:
            resp = self.request(f"/repos/{owner}/{repo}/commits", params=params)
            items = resp.json()
            if not isinstance(items, list):
                return []

            commits = []
            for c in items:
                commit_obj = c.get("commit", {})
                author_obj = commit_obj.get("author", {}) or {}
                date_str = author_obj.get("date")
                parsed_dt = dateutil.parser.isoparse(date_str) if date_str else None

                commits.append({
                    "sha": c.get("sha", "")[:7],
                    "message": commit_obj.get("message", "").split("\n")[0],
                    "author": author_obj.get("name", "Unknown"),
                    "date": parsed_dt,
                    "date_str": date_str,
                    "html_url": c.get("html_url", ""),
                })
            return commits
        except EmptyRepoError:
            return []
        except GitHubAPIError:
            return []

    def get_issues(
        self,
        owner: str,
        repo: str,
        state: str = "all",
        per_page: int = 100,
        max_pages: int = 1,
    ) -> Dict[str, Any]:
        """
        Fetch repository issues, strictly excluding Pull Requests.

        IMPORTANT:
        The GitHub API endpoint `/repos/{owner}/{repo}/issues` returns BOTH issues and pull requests.
        Pull requests must be filtered out by verifying that `'pull_request'` is NOT in the issue item dict.

        Args:
            owner: Repository owner
            repo: Repository name
            state: 'open', 'closed', 'all', or 'separate'
            per_page: Number of items per page (max 100)
            max_pages: Number of pages to fetch (default 1 to respect rate limits)

        Returns:
            Dict containing:
            - issues: List of cleaned issue dicts (excluding PRs)
            - total_filtered_issues: Count of pure issues fetched
            - open_count: Count of open issues in sample
            - closed_count: Count of closed issues in sample
            - pr_count_excluded: Count of PRs filtered out
        """
        if state == "separate":
            return self.get_issues_separate_states(owner, repo, per_page=per_page, max_pages=max_pages)

        all_pure_issues = []
        prs_excluded_count = 0

        for page in range(1, max_pages + 1):
            params = {
                "state": state,
                "per_page": min(per_page, 100),
                "page": page,
                "sort": "updated",
                "direction": "desc",
            }
            try:
                resp = self.request(f"/repos/{owner}/{repo}/issues", params=params)
                items = resp.json()
                if not isinstance(items, list) or not items:
                    break

                for item in items:
                    # CRITICAL FILTER: Exclude Pull Requests
                    if "pull_request" in item:
                        prs_excluded_count += 1
                        continue

                    labels = [
                        lbl.get("name", "")
                        for lbl in item.get("labels", [])
                        if isinstance(lbl, dict)
                    ]
                    created_dt = (
                        dateutil.parser.isoparse(item["created_at"])
                        if item.get("created_at")
                        else None
                    )
                    closed_dt = (
                        dateutil.parser.isoparse(item["closed_at"])
                        if item.get("closed_at")
                        else None
                    )
                    updated_dt = (
                        dateutil.parser.isoparse(item["updated_at"])
                        if item.get("updated_at")
                        else None
                    )

                    all_pure_issues.append({
                        "number": item.get("number"),
                        "title": item.get("title", ""),
                        "state": item.get("state", "open"),
                        "created_at": created_dt,
                        "updated_at": updated_dt,
                        "closed_at": closed_dt,
                        "labels": labels,
                        "comments": item.get("comments", 0),
                        "html_url": item.get("html_url", ""),
                        "author": item.get("user", {}).get("login", "unknown") if item.get("user") else "unknown",
                    })

                # Check if there's a next page in Link header
                if "next" not in resp.links:
                    break

            except GitHubAPIError:
                break

        open_issues = [i for i in all_pure_issues if i["state"] == "open"]
        closed_issues = [i for i in all_pure_issues if i["state"] == "closed"]

        return {
            "issues": all_pure_issues,
            "total_sample_count": len(all_pure_issues),
            "open_count": len(open_issues),
            "closed_count": len(closed_issues),
            "prs_excluded_count": prs_excluded_count,
        }

    def get_issues_separate_states(
        self,
        owner: str,
        repo: str,
        per_page: int = 50,
        max_pages: int = 1,
    ) -> Dict[str, Any]:
        """
        Fetch open and closed issues separately through the GitHub REST API.

        Why separate queries?
        Querying state='all' with sort='updated' biases results toward recently-updated items
        (often open issues receiving comments), distorting the sample ratio.
        Fetching state='open' and state='closed' as distinct requests allows balanced sampling,
        cleanly measures the retrieved items, and extracts pagination headers for scale context.

        Features:
        - Strict exclusion of Pull Requests from both queries
        - Pagination support per state
        - Accurate percentage calculations based on total pure issues retrieved
        - Rate-limit guard that halts pagination before exhausting API quota
        - Parses Link headers to capture total available pages for open vs closed

        Args:
            owner: Repository owner
            repo: Repository name
            per_page: Number of items per page per state (max 100, default 50)
            max_pages: Number of pages to retrieve per state (default 1)

        Returns:
            Dict containing:
            - issues: Combined list of pure open and closed issues
            - open_issues: List of pure open issues
            - closed_issues: List of pure closed issues
            - total_sample_count: Total pure issues analyzed across both queries
            - open_count: Count of pure open issues retrieved
            - closed_count: Count of pure closed issues retrieved
            - open_sample_pct: Percentage of sample that is open (0.0 - 100.0)
            - closed_sample_pct: Percentage of sample that is closed (0.0 - 100.0)
            - prs_excluded_count: Total Pull Requests filtered out across both queries
            - open_prs_excluded: Count of open PRs filtered out
            - closed_prs_excluded: Count of closed PRs filtered out
            - is_sample: Always True (flags this as a sample, NOT repository-wide ratio)
            - sample_notice: Explanatory limitation notice
            - open_last_page: Total pages of open items indicated by Link header
            - closed_last_page: Total pages of closed items indicated by Link header
            - rate_limit_warning: Present if pagination was halted to conserve quota
        """
        rate_limit_warning = None

        def _fetch_state(target_state: str) -> Tuple[List[Dict[str, Any]], int, Optional[int]]:
            nonlocal rate_limit_warning
            pure_items = []
            prs_excluded = 0
            last_page = None

            for page in range(1, max_pages + 1):
                # Rate limit safety check: stop if quota is critically low (<= 2)
                remaining = self.rate_limit_info.get("remaining")
                if remaining is not None and remaining <= 2:
                    rate_limit_warning = (
                        f"Pagination halted for '{target_state}' issues to conserve remaining API quota "
                        f"({remaining} requests remaining)."
                    )
                    break

                params = {
                    "state": target_state,
                    "per_page": min(per_page, 100),
                    "page": page,
                    "sort": "updated",
                    "direction": "desc",
                }
                try:
                    resp = self.request(f"/repos/{owner}/{repo}/issues", params=params)
                    items = resp.json()
                    if not isinstance(items, list) or not items:
                        break

                    for item in items:
                        # CRITICAL: Filter out Pull Requests
                        if "pull_request" in item:
                            prs_excluded += 1
                            continue

                        labels = [
                            lbl.get("name", "")
                            for lbl in item.get("labels", [])
                            if isinstance(lbl, dict)
                        ]
                        created_dt = (
                            dateutil.parser.isoparse(item["created_at"])
                            if item.get("created_at")
                            else None
                        )
                        closed_dt = (
                            dateutil.parser.isoparse(item["closed_at"])
                            if item.get("closed_at")
                            else None
                        )
                        updated_dt = (
                            dateutil.parser.isoparse(item["updated_at"])
                            if item.get("updated_at")
                            else None
                        )

                        pure_items.append({
                            "number": item.get("number"),
                            "title": item.get("title", ""),
                            "state": item.get("state", target_state),
                            "created_at": created_dt,
                            "updated_at": updated_dt,
                            "closed_at": closed_dt,
                            "labels": labels,
                            "comments": item.get("comments", 0),
                            "html_url": item.get("html_url", ""),
                            "author": item.get("user", {}).get("login", "unknown") if item.get("user") else "unknown",
                        })

                    # Parse total pages from Link header if available
                    if "last" in resp.links:
                        last_url = resp.links["last"]["url"]
                        match = re.search(r"[?&]page=(\d+)", last_url)
                        if match:
                            last_page = int(match.group(1))

                    if "next" not in resp.links:
                        break

                except GitHubAPIError:
                    break

            return pure_items, prs_excluded, last_page

        open_pure, open_prs, open_last_page = _fetch_state("open")
        closed_pure, closed_prs, closed_last_page = _fetch_state("closed")

        total_sample = len(open_pure) + len(closed_pure)
        total_prs = open_prs + closed_prs

        open_pct = round((len(open_pure) / total_sample) * 100, 1) if total_sample > 0 else 0.0
        closed_pct = round((len(closed_pure) / total_sample) * 100, 1) if total_sample > 0 else 0.0

        sample_notice = (
            f"Sample of {total_sample} pure issues analyzed ({len(open_pure)} open, {len(closed_pure)} closed; "
            f"{total_prs} pull requests excluded). This reflects the retrieved sample, not the entire repository-wide ratio."
        )

        all_pure_issues = open_pure + closed_pure

        return {
            "issues": all_pure_issues,
            "open_issues": open_pure,
            "closed_issues": closed_pure,
            "total_sample_count": total_sample,
            "open_count": len(open_pure),
            "closed_count": len(closed_pure),
            "open_sample_pct": open_pct,
            "closed_sample_pct": closed_pct,
            "prs_excluded_count": total_prs,
            "open_prs_excluded": open_prs,
            "closed_prs_excluded": closed_prs,
            "is_sample": True,
            "sample_notice": sample_notice,
            "open_last_page": open_last_page,
            "closed_last_page": closed_last_page,
            "rate_limit_warning": rate_limit_warning,
        }

    def get_beginner_friendly_issues(
        self, owner: str, repo: str, max_count: int = 25
    ) -> List[Dict[str, Any]]:
        """
        Fetch open issues labeled with beginner-friendly tags.

        Recognized label patterns:
        - good first issue / good-first-issue
        - help wanted / help-wanted
        - beginner / beginner-friendly
        - easy / up-for-grabs / first-timers-only / starter
        """
        beginner_keywords = [
            "good first issue",
            "good-first-issue",
            "help wanted",
            "help-wanted",
            "beginner",
            "beginner-friendly",
            "up-for-grabs",
            "easy",
            "first-timers-only",
            "low-hanging-fruit",
            "starter",
        ]

        # First try fetching open issues
        issues_res = self.get_issues(owner, repo, state="open", per_page=100, max_pages=1)
        open_issues = issues_res["issues"]

        beginner_issues = []
        now = datetime.now(timezone.utc)

        for issue in open_issues:
            matched_labels = []
            for label in issue["labels"]:
                lbl_lower = label.lower().strip()
                for kw in beginner_keywords:
                    if kw in lbl_lower:
                        matched_labels.append(label)
                        break

            if matched_labels:
                age_days = None
                if issue["created_at"]:
                    age_days = max(0, (now - issue["created_at"]).days)

                beginner_issues.append({
                    "number": issue["number"],
                    "title": issue["title"],
                    "labels": issue["labels"],
                    "beginner_labels": list(set(matched_labels)),
                    "comments": issue["comments"],
                    "created_at": issue["created_at"],
                    "age_days": age_days,
                    "html_url": issue["html_url"],
                    "author": issue["author"],
                })

            if len(beginner_issues) >= max_count:
                break

        return beginner_issues

    def get_contributors(self, owner: str, repo: str, per_page: int = 100) -> Dict[str, Any]:
        """
        Fetch top contributors and pagination metadata.

        Note:
        GitHub returns up to 100 contributors per page. For large repositories (e.g. Linux, CPython),
        retrieving all contributors requires multiple requests and could exhaust rate limits.
        This function retrieves the first sample page and parses the 'Link' header to estimate total pages.
        """
        try:
            resp = self.request(f"/repos/{owner}/{repo}/contributors", params={"per_page": min(per_page, 100), "anon": "false"})

            # GitHub may return 202 Accepted if it's computing contributor stats
            if resp.status_code == 202:
                return {
                    "count": 0,
                    "is_sample": True,
                    "top_contributors": [],
                    "message": "GitHub is currently compiling statistics for this repository. Please retry in a few moments.",
                    "total_estimated": None,
                }

            items = resp.json()
            if not isinstance(items, list):
                return {
                    "count": 0,
                    "is_sample": False,
                    "top_contributors": [],
                    "message": "No contributors found or data unavailable.",
                    "total_estimated": 0,
                }

            contributors = []
            for c in items:
                contributors.append({
                    "login": c.get("login", "unknown"),
                    "contributions": c.get("contributions", 0),
                    "avatar_url": c.get("avatar_url", ""),
                    "html_url": c.get("html_url", ""),
                })

            # Check if Link header gives total pages
            total_estimated = len(contributors)
            is_sample = False
            if "last" in resp.links:
                is_sample = True
                last_url = resp.links["last"]["url"]
                match = re.search(r"[?&]page=(\d+)", last_url)
                if match:
                    total_pages = int(match.group(1))
                    total_estimated = total_pages * len(contributors)

            return {
                "count": len(contributors),
                "is_sample": is_sample,
                "top_contributors": contributors[:10],
                "message": None,
                "total_estimated": total_estimated,
            }
        except GitHubAPIError as e:
            return {
                "count": 0,
                "is_sample": False,
                "top_contributors": [],
                "message": f"Contributor data unavailable: {e}",
                "total_estimated": None,
            }

    def get_releases(self, owner: str, repo: str, per_page: int = 10) -> List[Dict[str, Any]]:
        """Fetch latest releases."""
        try:
            resp = self.request(f"/repos/{owner}/{repo}/releases", params={"per_page": min(per_page, 10)})
            items = resp.json()
            if not isinstance(items, list):
                return []

            releases = []
            for r in items:
                pub_str = r.get("published_at")
                pub_dt = dateutil.parser.isoparse(pub_str) if pub_str else None
                releases.append({
                    "tag_name": r.get("tag_name", ""),
                    "name": r.get("name") or r.get("tag_name", ""),
                    "published_at": pub_dt,
                    "html_url": r.get("html_url", ""),
                    "prerelease": r.get("prerelease", False),
                })
            return releases
        except GitHubAPIError:
            return []
