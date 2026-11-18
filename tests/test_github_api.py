"""
tests/test_github_api.py
========================
Unit tests for URL parsing, GitHub API client, error handling,
and pull-request exclusion.
"""

from unittest.mock import MagicMock, patch
import pytest

from github_api import (
    AuthenticationError,
    GitHubAPIError,
    GitHubClient,
    RateLimitExceededError,
    RepoNotFoundError,
    parse_repo_url,
)


class TestURLParsing:
    """Tests for parse_repo_url function."""

    @pytest.mark.parametrize(
        "input_val,expected",
        [
            ("https://github.com/psf/requests", ("psf", "requests")),
            ("https://github.com/pallets/flask/", ("pallets", "flask")),
            ("http://github.com/django/django", ("django", "django")),
            ("github.com/pandas-dev/pandas", ("pandas-dev", "pandas")),
            ("tiangolo/fastapi", ("tiangolo", "fastapi")),
            ("https://github.com/facebook/react.git", ("facebook", "react")),
            ("git@github.com:torvalds/linux.git", ("torvalds", "linux")),
            ("https://github.com/angular/angular/tree/main", ("angular", "angular")),
            ("https://github.com/scikit-learn/scikit-learn/issues/123", ("scikit-learn", "scikit-learn")),
        ],
    )
    def test_valid_urls(self, input_val, expected):
        assert parse_repo_url(input_val) == expected

    @pytest.mark.parametrize(
        "invalid_val",
        [
            "",
            "   ",
            "https://gitlab.com/owner/repo",
            "https://bitbucket.org/owner/repo",
            "just-a-string",
            "https://github.com/",
            "https://github.com/singlepart",
            "owner//repo",
            "invalid owner/repo",
            "-invalid-owner/repo",
        ],
    )
    def test_invalid_urls(self, invalid_val):
        with pytest.raises(ValueError):
            parse_repo_url(invalid_val)


class TestGitHubClient:
    """Tests for GitHubClient methods and error handling."""

    def test_client_initialization_no_token(self):
        client = GitHubClient(token=None)
        assert "Authorization" not in client.session.headers
        assert client.session.headers["Accept"] == "application/vnd.github.v3+json"

    def test_client_initialization_with_token(self):
        client = GitHubClient(token="ghp_test12345")
        assert client.session.headers["Authorization"] == "Bearer ghp_test12345"

    @patch("requests.Session.get")
    def test_get_repo_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"X-RateLimit-Limit": "60", "X-RateLimit-Remaining": "59", "X-RateLimit-Reset": "1700000000"}
        mock_resp.json.return_value = {
            "owner": {"login": "psf"},
            "name": "requests",
            "full_name": "psf/requests",
            "description": "A simple, yet elegant, HTTP library.",
            "html_url": "https://github.com/psf/requests",
            "created_at": "2011-02-13T18:38:17Z",
            "updated_at": "2026-01-01T12:00:00Z",
            "pushed_at": "2026-01-01T12:00:00Z",
            "default_branch": "main",
            "stargazers_count": 50000,
            "forks_count": 9000,
            "open_issues_count": 120,
            "subscribers_count": 1400,
            "size": 15000,
            "language": "Python",
            "license": {"spdx_id": "Apache-2.0", "name": "Apache License 2.0"},
            "archived": False,
            "disabled": False,
            "fork": False,
            "topics": ["python", "http"],
            "has_issues": True,
            "has_wiki": False,
        }
        mock_get.return_value = mock_resp
        client = GitHubClient()
        repo_data = client.get_repo("psf", "requests")
        assert repo_data["name"] == "requests"
        assert repo_data["stargazers_count"] == 50000
        assert repo_data["license"] == "Apache-2.0"
        assert client.rate_limit_info["remaining"] == 59

    @patch("requests.Session.get")
    def test_get_repo_404_raises_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.headers = {}
        mock_get.return_value = mock_resp

        client = GitHubClient()
        with pytest.raises(RepoNotFoundError):
            client.get_repo("nonexistent", "repo")

    @patch("requests.Session.get")
    def test_rate_limit_exceeded(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.headers = {
            "X-RateLimit-Limit": "60",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1700000000",
        }
        mock_resp.text = "API rate limit exceeded for user"
        mock_get.return_value = mock_resp

        client = GitHubClient()
        with pytest.raises(RateLimitExceededError) as exc_info:
            client.get_repo("psf", "requests")
        assert "rate limit exceeded" in str(exc_info.value).lower()

    @patch("requests.Session.get")
    def test_get_readme_missing_handled_gracefully(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.headers = {}
        mock_get.return_value = mock_resp

        client = GitHubClient()
        readme = client.get_readme("owner", "no-readme")
        assert readme["exists"] is False
        assert readme["size"] == 0

    @patch("requests.Session.get")
    def test_issues_exclude_pull_requests(self, mock_get):
        """CRITICAL: GitHub /issues endpoint returns PRs too. They must be excluded."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.links = {}
        mock_resp.json.return_value = [
            {
                "number": 101,
                "title": "Bug in parser",
                "state": "open",
                "created_at": "2026-01-01T00:00:00Z",
                "labels": [{"name": "bug"}],
                "comments": 2,
                "html_url": "https://github.com/org/repo/issues/101",
                # Note: No 'pull_request' key -> THIS IS A PURE ISSUE
            },
            {
                "number": 102,
                "title": "Fix bug in parser",
                "state": "open",
                "created_at": "2026-01-02T00:00:00Z",
                "labels": [{"name": "fix"}],
                "comments": 1,
                "html_url": "https://github.com/org/repo/pull/102",
                "pull_request": {"url": "https://api.github.com/repos/org/repo/pulls/102"},
                # Note: 'pull_request' key present -> THIS MUST BE EXCLUDED
            },
            {
                "number": 103,
                "title": "Documentation typo",
                "state": "closed",
                "created_at": "2026-01-03T00:00:00Z",
                "labels": [{"name": "documentation"}],
                "comments": 0,
                "html_url": "https://github.com/org/repo/issues/103",
                # Pure issue
            },
        ]
        mock_get.return_value = mock_resp

        client = GitHubClient()
        res = client.get_issues("org", "repo", state="all")
        assert res["total_sample_count"] == 2
        assert res["prs_excluded_count"] == 1
        numbers = [i["number"] for i in res["issues"]]
        assert 101 in numbers
        assert 103 in numbers
        assert 102 not in numbers

    @patch("requests.Session.get")
    def test_beginner_friendly_issues(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {}
        mock_resp.links = {}
        mock_resp.json.return_value = [
            {
                "number": 1,
                "title": "Fix doc typo",
                "state": "open",
                "created_at": "2026-01-01T00:00:00Z",
                "labels": [{"name": "good first issue"}, {"name": "docs"}],
                "comments": 0,
                "html_url": "https://github.com/org/repo/issues/1",
            },
            {
                "number": 2,
                "title": "Refactor entire backend architecture",
                "state": "open",
                "created_at": "2026-01-01T00:00:00Z",
                "labels": [{"name": "architecture"}, {"name": "complex"}],
                "comments": 12,
                "html_url": "https://github.com/org/repo/issues/2",
            },
            {
                "number": 3,
                "title": "Add Spanish translation",
                "state": "open",
                "created_at": "2026-01-01T00:00:00Z",
                "labels": [{"name": "help wanted"}],
                "comments": 1,
                "html_url": "https://github.com/org/repo/issues/3",
            },
        ]
        mock_get.return_value = mock_resp

        client = GitHubClient()
        beginner_issues = client.get_beginner_friendly_issues("org", "repo")
        assert len(beginner_issues) == 2
        titles = [i["title"] for i in beginner_issues]
        assert "Fix doc typo" in titles
        assert "Add Spanish translation" in titles
        assert "Refactor entire backend architecture" not in titles

    @patch("requests.Session.get")
    def test_get_issues_separate_states_success(self, mock_get):
        """Test separate queries for open and closed issues with PR exclusion and accurate percentages."""
        # First call: state=open -> 2 pure issues, 1 PR
        resp_open = MagicMock()
        resp_open.status_code = 200
        resp_open.headers = {"X-RateLimit-Limit": "60", "X-RateLimit-Remaining": "50", "X-RateLimit-Reset": "1700000000"}
        resp_open.links = {"last": {"url": "https://api.github.com/repos/org/repo/issues?state=open&page=8"}}
        resp_open.json.return_value = [
            {"number": 1, "title": "Open bug 1", "state": "open", "created_at": "2026-01-01T00:00:00Z", "labels": []},
            {"number": 2, "title": "Open PR 1", "state": "open", "created_at": "2026-01-01T00:00:00Z", "pull_request": {}, "labels": []},
            {"number": 3, "title": "Open bug 2", "state": "open", "created_at": "2026-01-02T00:00:00Z", "labels": []},
        ]

        # Second call: state=closed -> 1 pure issue, 2 PRs
        resp_closed = MagicMock()
        resp_closed.status_code = 200
        resp_closed.headers = {"X-RateLimit-Limit": "60", "X-RateLimit-Remaining": "49", "X-RateLimit-Reset": "1700000000"}
        resp_closed.links = {"last": {"url": "https://api.github.com/repos/org/repo/issues?state=closed&page=20"}}
        resp_closed.json.return_value = [
            {"number": 4, "title": "Closed PR 1", "state": "closed", "created_at": "2026-01-01T00:00:00Z", "pull_request": {}, "labels": []},
            {"number": 5, "title": "Closed bug 1", "state": "closed", "created_at": "2026-01-01T00:00:00Z", "labels": []},
            {"number": 6, "title": "Closed PR 2", "state": "closed", "created_at": "2026-01-02T00:00:00Z", "pull_request": {}, "labels": []},
        ]

        mock_get.side_effect = [resp_open, resp_closed]

        client = GitHubClient()
        res = client.get_issues_separate_states("org", "repo", per_page=10, max_pages=1)

        assert res["open_count"] == 2
        assert res["closed_count"] == 1
        assert res["total_sample_count"] == 3
        assert res["prs_excluded_count"] == 3  # 1 from open, 2 from closed
        assert res["open_prs_excluded"] == 1
        assert res["closed_prs_excluded"] == 2

        # Percentages calculated on actual retrieved pure issues: 2/3 and 1/3
        assert res["open_sample_pct"] == 66.7
        assert res["closed_sample_pct"] == 33.3

        assert res["is_sample"] is True
        assert "not the entire repository-wide ratio" in res["sample_notice"]
        assert res["open_last_page"] == 8
        assert res["closed_last_page"] == 20

    @patch("requests.Session.get")
    def test_get_issues_separate_states_rate_limit_halt(self, mock_get):
        """Test that pagination safely halts when API quota is critically low."""
        client = GitHubClient()
        client.rate_limit_info["remaining"] = 1  # critically low quota

        res = client.get_issues_separate_states("org", "repo", per_page=10, max_pages=2)
        assert res["total_sample_count"] == 0
        assert res["rate_limit_warning"] is not None
        assert "conserve remaining API quota" in res["rate_limit_warning"]

