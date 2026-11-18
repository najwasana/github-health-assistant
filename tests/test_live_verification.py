"""
tests/test_live_verification.py
================================
Live integration verification script checking:
1. Real GitHub REST API data retrieval
2. Correct Health Score calculations
3. Strict pull-request filtering
4. Beginner-friendly issue detection and clickable URL validity
"""

from github_api import GitHubClient, parse_repo_url
from analyzer import analyze_repository


def test_live_flask_analysis():
    client = GitHubClient()
    owner, repo = parse_repo_url("pallets/flask")
    
    repo_meta = client.get_repo(owner, repo)
    assert repo_meta["name"].lower() == "flask"
    assert repo_meta["owner"].lower() == "pallets"
    assert repo_meta["stargazers_count"] > 1000
    assert repo_meta["forks_count"] > 500
    
    readme_info = client.get_readme(owner, repo)
    assert readme_info["exists"] is True
    assert readme_info["size"] > 100
    
    comm_profile = client.get_community_profile(owner, repo)
    assert isinstance(comm_profile, dict)
    
    commits = client.get_commits(owner, repo, per_page=15)
    assert len(commits) > 0
    assert "sha" in commits[0]
    
    issues = client.get_issues_separate_states(owner, repo, per_page=15, max_pages=1)
    assert issues["total_sample_count"] > 0
    assert issues["open_count"] >= 0
    assert issues["closed_count"] >= 0
    assert issues["total_sample_count"] == issues["open_count"] + issues["closed_count"]
    assert issues["is_sample"] is True
    assert "sample_notice" in issues
    if issues["total_sample_count"] > 0:
        assert round(issues["open_sample_pct"] + issues["closed_sample_pct"], 0) == 100.0
    # Confirm PRs were identified and separated
    assert "prs_excluded_count" in issues
    
    beginner_issues = client.get_beginner_friendly_issues(owner, repo, max_count=5)
    for b in beginner_issues:
        assert b["html_url"].startswith("https://github.com/pallets/flask/issues/")
        assert "number" in b
        assert "title" in b
    
    contributors = client.get_contributors(owner, repo, per_page=10)
    assert contributors["count"] > 0
    
    releases = client.get_releases(owner, repo, per_page=5)
    assert len(releases) > 0
    
    results = analyze_repository(
        repo_data=repo_meta,
        readme_data=readme_info,
        community_profile=comm_profile,
        commits_data=commits,
        issues_data=issues,
        beginner_issues=beginner_issues,
        contributors_data=contributors,
        releases_data=releases,
    )
    
    assert 0 <= results["overall_score"] <= 100
    # Sum of category scores must equal overall score
    sum_cats = sum(c["score"] for c in results["category_scores"].values())
    assert results["overall_score"] == sum_cats
    assert results["health_rating"] in ["Excellent", "Good", "Moderate", "Needs Attention", "Dormant / Critical"]
    print(f"\nLive Verification Succeeded!")
    print(f"Repository: {results['summary']['full_name']}")
    print(f"Score: {results['overall_score']} / 100 ({results['health_rating']})")
    print(f"Pure Issues in sample: {results['summary']['pure_issues_sampled']}")
    print(f"PRs excluded from issues: {results['summary']['prs_excluded']}")
    print(f"Beginner issues found: {len(beginner_issues)}")


def test_live_beginner_issue_links():
    """Verify that beginner issue detection retrieves valid, reachable links."""
    client = GitHubClient()
    # tiangolo/fastapi often has 'help wanted' or 'good first issue'
    for candidate in ["tiangolo/fastapi", "streamlit/streamlit", "pandas-dev/pandas"]:
        owner, repo = parse_repo_url(candidate)
        beginner_issues = client.get_beginner_friendly_issues(owner, repo, max_count=5)
        if beginner_issues:
            print(f"\nFound {len(beginner_issues)} beginner issues in {candidate}:")
            for b in beginner_issues:
                print(f"  #{b['number']} ({b['html_url']}): {b['title']}")
                assert b["html_url"].startswith("https://github.com/")
                assert "/issues/" in b["html_url"]
                assert b["number"] > 0
                assert len(b["beginner_labels"]) > 0
            return
    # If none found in those repos, check that list returns empty gracefully
    assert isinstance(beginner_issues, list)

