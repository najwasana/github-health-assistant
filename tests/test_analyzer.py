"""
tests/test_analyzer.py
======================
Unit tests for analyzer.py scoring methodology, category weights,
deduction explanations, and edge cases.
"""

from datetime import datetime, timezone, timedelta
import pytest
from analyzer import CATEGORY_WEIGHTS, analyze_repository


@pytest.fixture
def perfect_repo_data():
    now = datetime.now(timezone.utc)
    return {
        "repo_data": {
            "full_name": "awesome-org/perfect-repo",
            "description": "An exemplary repository for testing.",
            "language": "Python",
            "license": "MIT",
            "license_name": "MIT License",
            "stargazers_count": 500,
            "forks_count": 80,
            "pushed_at": (now - timedelta(days=2)).isoformat(),
            "archived": False,
            "disabled": False,
            "has_issues": True,
        },
        "readme_data": {
            "exists": True,
            "size": 3500,
            "name": "README.md",
        },
        "community_profile": {
            "has_readme": True,
            "has_license": True,
            "has_contributing": True,
            "has_code_of_conduct": True,
            "has_issue_template": True,
            "has_pull_request_template": True,
        },
        "commits_data": [{"sha": f"sha{i}", "date": now} for i in range(30)],
        "issues_data": {
            "issues": [
                {
                    "number": i,
                    "state": "closed" if i % 2 == 0 else "open",
                    "labels": ["bug" if i % 2 == 0 else "enhancement"],
                    "created_at": now - timedelta(days=i * 2),
                }
                for i in range(1, 21)
            ],
            "total_sample_count": 20,
            "open_count": 10,
            "closed_count": 10,
            "prs_excluded_count": 5,
        },
        "beginner_issues": [
            {"number": 101, "title": "First issue", "labels": ["good first issue"]},
            {"number": 102, "title": "Second issue", "labels": ["help wanted"]},
            {"number": 103, "title": "Third issue", "labels": ["beginner"]},
        ],
        "contributors_data": {
            "count": 20,
            "total_estimated": 20,
            "is_sample": False,
        },
        "releases_data": [
            {"tag_name": "v1.2.0", "published_at": now - timedelta(days=20)}
        ],
    }


@pytest.fixture
def empty_dormant_repo_data():
    now = datetime.now(timezone.utc)
    return {
        "repo_data": {
            "full_name": "abandoned/old-project",
            "description": "",
            "language": None,
            "license": None,
            "stargazers_count": 0,
            "forks_count": 0,
            "pushed_at": (now - timedelta(days=500)).isoformat(),
            "archived": False,
            "disabled": False,
            "has_issues": True,
        },
        "readme_data": {
            "exists": False,
            "size": 0,
            "name": None,
        },
        "community_profile": {
            "has_readme": False,
            "has_license": False,
            "has_contributing": False,
            "has_code_of_conduct": False,
            "has_issue_template": False,
            "has_pull_request_template": False,
        },
        "commits_data": [],
        "issues_data": {
            "issues": [],
            "total_sample_count": 0,
            "open_count": 0,
            "closed_count": 0,
            "prs_excluded_count": 0,
        },
        "beginner_issues": [],
        "contributors_data": {
            "count": 0,
            "total_estimated": 0,
            "is_sample": False,
        },
        "releases_data": [],
    }


def test_category_weights_sum_to_100():
    total_weight = sum(CATEGORY_WEIGHTS.values())
    assert total_weight == 100, f"Category weights must sum to 100, got {total_weight}"


def test_perfect_repo_scoring(perfect_repo_data):
    result = analyze_repository(**perfect_repo_data)
    assert result["overall_score"] == 100
    assert result["health_rating"] == "Excellent"
    for cat_name, cat in result["category_scores"].items():
        assert cat["score"] == cat["max"]
    assert len(result["deductions"]) == 0


def test_empty_dormant_repo_scoring(empty_dormant_repo_data):
    result = analyze_repository(**empty_dormant_repo_data)
    assert 0 <= result["overall_score"] <= 25
    assert result["health_rating"] in ["Needs Attention", "Dormant / Critical"]
    # Check that deductions are logged with actionable recommendations
    assert len(result["deductions"]) > 0
    for deduction in result["deductions"]:
        assert "points_lost" in deduction
        assert "evidence" in deduction
        assert "recommendation" in deduction
        assert "priority" in deduction


def test_archived_repo_penalized(perfect_repo_data):
    # Mark repo as archived
    perfect_repo_data["repo_data"]["archived"] = True
    result = analyze_repository(**perfect_repo_data)
    # Activity score must be 0 for archived repos
    assert result["category_scores"]["activity"]["score"] == 0
    assert any(d["title"] == "Repository is Archived / Disabled" for d in result["deductions"])


def test_missing_readme_deduction(perfect_repo_data):
    perfect_repo_data["readme_data"]["exists"] = False
    result = analyze_repository(**perfect_repo_data)
    readme_deductions = [d for d in result["deductions"] if "README" in d["title"]]
    assert len(readme_deductions) > 0
    assert readme_deductions[0]["points_lost"] == 12


def test_pull_requests_excluded_from_issue_count(perfect_repo_data):
    result = analyze_repository(**perfect_repo_data)
    summary = result["summary"]
    assert summary["prs_excluded"] == 5
    assert summary["pure_issues_sampled"] == 20


def test_issue_resolution_separate_states_sample_notice(perfect_repo_data):
    """Verify that analyzer records sample percentages and notice from separate queries."""
    perfect_repo_data["issues_data"] = {
        "issues": [
            {"number": 1, "state": "open", "labels": ["bug"], "created_at": None},
            {"number": 2, "state": "open", "labels": [], "created_at": None},
            {"number": 3, "state": "closed", "labels": ["enhancement"], "created_at": None},
        ],
        "open_issues": [
            {"number": 1, "state": "open", "labels": ["bug"], "created_at": None},
            {"number": 2, "state": "open", "labels": [], "created_at": None},
        ],
        "closed_issues": [
            {"number": 3, "state": "closed", "labels": ["enhancement"], "created_at": None},
        ],
        "total_sample_count": 3,
        "open_count": 2,
        "closed_count": 1,
        "open_sample_pct": 66.7,
        "closed_sample_pct": 33.3,
        "prs_excluded_count": 4,
        "is_sample": True,
        "sample_notice": "Sample of 3 pure issues analyzed (2 open, 1 closed; 4 pull requests excluded). This reflects the retrieved sample, not the entire repository-wide ratio.",
    }

    result = analyze_repository(**perfect_repo_data)
    summary = result["summary"]
    assert summary["pure_issues_sampled"] == 3
    assert summary["open_pure_issues"] == 2
    assert summary["closed_pure_issues"] == 1
    assert summary["open_sample_pct"] == 66.7
    assert summary["closed_sample_pct"] == 33.3
    assert summary["prs_excluded"] == 4
    assert any("not the entire repository-wide ratio" in notice for notice in result["data_limitations"])

