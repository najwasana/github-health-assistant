"""
analyzer.py
===========
Repository Health Analysis and Scoring Engine.

Computes transparent, explainable scores across 5 categories totalling 100 points:
1. Documentation (25 points)
2. Activity & Maintenance (25 points)
3. Issue Management (20 points) - strictly excludes pull requests
4. Community Participation (15 points)
5. Beginner Accessibility (15 points)

Features:
- Component-level scoring breakdown
- Explicit deduction logging with evidence
- Prioritized actionable improvement recommendations
- Missing data & API limitation tracking
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# Category Maximum Weights
CATEGORY_WEIGHTS = {
    "documentation": 25,
    "activity": 25,
    "issue_management": 20,
    "community": 15,
    "beginner_friendly": 15,
}


def analyze_repository(
    repo_data: Dict[str, Any],
    readme_data: Dict[str, Any],
    community_profile: Dict[str, Any],
    commits_data: List[Dict[str, Any]],
    issues_data: Dict[str, Any],
    beginner_issues: List[Dict[str, Any]],
    contributors_data: Dict[str, Any],
    releases_data: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Perform a comprehensive health analysis of a repository.

    Returns a structured dictionary containing:
    - overall_score: 0 - 100
    - health_rating: "Excellent", "Good", "Moderate", "Needs Attention", "Dormant"
    - category_scores: breakdown per category
    - deductions: list of all points deducted with reasons and evidence
    - recommendations: prioritized list of actionable steps
    - summary: clean summary metrics for the repository
    - beginner_issues: beginner-tagged issues with caveats
    - data_limitations: transparency notices regarding API limits or partial data
    """
    now = datetime.now(timezone.utc)
    deductions: List[Dict[str, Any]] = []
    data_limitations: List[str] = []

    # -------------------------------------------------------------
    # 1. Documentation Analysis (Max 25 pts)
    # -------------------------------------------------------------
    doc_score = 0
    doc_max = CATEGORY_WEIGHTS["documentation"]

    # 1.1 README existence and size (Max 12 pts)
    readme_exists = readme_data.get("exists", False)
    readme_size = readme_data.get("size", 0)

    if not readme_exists:
        deductions.append({
            "category": "Documentation",
            "points_lost": 12,
            "title": "Missing README file",
            "evidence": "No README found at repository root or standard paths.",
            "recommendation": "Add a comprehensive README.md introducing the project, setup instructions, and examples.",
            "priority": "High",
        })
    else:
        # README exists: base 6 points
        doc_score += 6
        if readme_size >= 2000:
            doc_score += 6  # Full depth
        elif readme_size >= 500:
            doc_score += 3
            deductions.append({
                "category": "Documentation",
                "points_lost": 3,
                "title": "Brief README content",
                "evidence": f"README file is relatively short ({readme_size} bytes).",
                "recommendation": "Expand README with prerequisites, installation steps, configuration guides, and screenshots.",
                "priority": "Medium",
            })
        else:
            deductions.append({
                "category": "Documentation",
                "points_lost": 6,
                "title": "Minimal README content",
                "evidence": f"README is very small ({readme_size} bytes).",
                "recommendation": "Flesh out the README. A good README includes architecture, installation, test running, and examples.",
                "priority": "High",
            })

    # 1.2 License (Max 5 pts)
    has_license = bool(repo_data.get("license")) or community_profile.get("has_license", False)
    if has_license:
        doc_score += 5
    else:
        deductions.append({
            "category": "Documentation",
            "points_lost": 5,
            "title": "No Open-Source License",
            "evidence": "No LICENSE file detected via GitHub Community Profile or Repository metadata.",
            "recommendation": "Add an OSI-approved open-source license (such as MIT, Apache-2.0, or GPL-3.0) to clarify reuse and contribution terms.",
            "priority": "High",
        })

    # 1.3 Contributing Guidelines (Max 4 pts)
    has_contributing = community_profile.get("has_contributing", False)
    if has_contributing:
        doc_score += 4
    else:
        deductions.append({
            "category": "Documentation",
            "points_lost": 4,
            "title": "Missing CONTRIBUTING guide",
            "evidence": "No CONTRIBUTING.md found.",
            "recommendation": "Create a CONTRIBUTING.md describing how to set up the dev environment, run tests, and submit pull requests.",
            "priority": "Medium",
        })

    # 1.4 Code of Conduct & Templates (Max 4 pts)
    has_coc = community_profile.get("has_code_of_conduct", False)
    has_issue_tmpl = community_profile.get("has_issue_template", False)
    has_pr_tmpl = community_profile.get("has_pull_request_template", False)

    if has_coc:
        doc_score += 2
    else:
        deductions.append({
            "category": "Documentation",
            "points_lost": 2,
            "title": "Missing Code of Conduct",
            "evidence": "No CODE_OF_CONDUCT.md detected.",
            "recommendation": "Add a standard Contributor Covenant Code of Conduct to set respectful community expectations.",
            "priority": "Low",
        })

    if has_issue_tmpl or has_pr_tmpl:
        doc_score += 2
    else:
        deductions.append({
            "category": "Documentation",
            "points_lost": 2,
            "title": "Missing Issue / PR Templates",
            "evidence": "No GitHub Issue or Pull Request templates found in .github/.",
            "recommendation": "Add GitHub Issue and PR templates to standardize bug reports and feature proposals.",
            "priority": "Low",
        })

    doc_score = min(doc_score, doc_max)

    # -------------------------------------------------------------
    # 2. Activity & Maintenance (Max 25 pts)
    # -------------------------------------------------------------
    act_score = 0
    act_max = CATEGORY_WEIGHTS["activity"]

    is_archived = repo_data.get("archived", False)
    is_disabled = repo_data.get("disabled", False)

    # Parse last commit / push timestamp
    pushed_at_str = repo_data.get("pushed_at")
    days_since_push = None
    if pushed_at_str:
        try:
            import dateutil.parser
            pushed_dt = dateutil.parser.isoparse(pushed_at_str)
            days_since_push = max(0, (now - pushed_dt).days)
        except Exception:
            pass

    if is_archived or is_disabled:
        act_score = 0
        deductions.append({
            "category": "Activity & Maintenance",
            "points_lost": 25,
            "title": "Repository is Archived / Disabled",
            "evidence": "Repository is marked archived or disabled by maintainers.",
            "recommendation": "This repository is read-only and no longer accepting contributions.",
            "priority": "Critical",
        })
    else:
        # 2.1 Commit Recency (Max 10 pts)
        if days_since_push is None:
            data_limitations.append("Unable to determine last push date from repository metadata.")
        elif days_since_push <= 30:
            act_score += 10
        elif days_since_push <= 90:
            act_score += 7
            deductions.append({
                "category": "Activity & Maintenance",
                "points_lost": 3,
                "title": "Moderate time since last push",
                "evidence": f"Last push was {days_since_push} days ago.",
                "recommendation": "Regular commits or maintenance cycles help keep dependencies up to date.",
                "priority": "Medium",
            })
        elif days_since_push <= 180:
            act_score += 4
            deductions.append({
                "category": "Activity & Maintenance",
                "points_lost": 6,
                "title": "Infrequent maintenance",
                "evidence": f"Last push was {days_since_push} days ago (>3 months).",
                "recommendation": "Consider reviewing pending issues/PRs or scheduling routine maintenance.",
                "priority": "Medium",
            })
        elif days_since_push <= 365:
            act_score += 2
            deductions.append({
                "category": "Activity & Maintenance",
                "points_lost": 8,
                "title": "Inactive repository",
                "evidence": f"Last push was {days_since_push} days ago (>6 months).",
                "recommendation": "Repository has not been updated in over six months.",
                "priority": "High",
            })
        else:
            deductions.append({
                "category": "Activity & Maintenance",
                "points_lost": 10,
                "title": "Stagnant repository",
                "evidence": f"Last push was {days_since_push} days ago (>1 year).",
                "recommendation": "Repository appears dormant. Inactive projects can lead to unmerged PRs and security drift.",
                "priority": "High",
            })

        # 2.2 Commit Sample Volume (Max 8 pts)
        commit_count = len(commits_data)
        if commit_count >= 25:
            act_score += 8
        elif commit_count >= 10:
            act_score += 6
        elif commit_count >= 3:
            act_score += 3
            deductions.append({
                "category": "Activity & Maintenance",
                "points_lost": 5,
                "title": "Low commit volume in recent sample",
                "evidence": f"Found {commit_count} commits in recent history.",
                "recommendation": "Active continuous integration and smaller incremental commits signal ongoing work.",
                "priority": "Low",
            })
        elif commit_count > 0:
            act_score += 1
            deductions.append({
                "category": "Activity & Maintenance",
                "points_lost": 7,
                "title": "Very low commit count",
                "evidence": f"Only {commit_count} commit(s) in default branch history.",
                "recommendation": "Increase project activity with regular commits.",
                "priority": "Medium",
            })
        else:
            deductions.append({
                "category": "Activity & Maintenance",
                "points_lost": 8,
                "title": "No commits found in default branch",
                "evidence": "Commit log returned 0 commits or repository is empty.",
                "recommendation": "Push initial commits to default branch.",
                "priority": "High",
            })

        # 2.3 Release Cadence (Max 7 pts)
        if releases_data:
            latest_release = releases_data[0]
            rel_dt = latest_release.get("published_at")
            if rel_dt:
                days_since_rel = max(0, (now - rel_dt).days)
                if days_since_rel <= 180:
                    act_score += 7
                elif days_since_rel <= 365:
                    act_score += 5
                    deductions.append({
                        "category": "Activity & Maintenance",
                        "points_lost": 2,
                        "title": "Older latest release",
                        "evidence": f"Latest release was {days_since_rel} days ago.",
                        "recommendation": "Publish a newer tagged release if significant changes were made.",
                        "priority": "Low",
                    })
                else:
                    act_score += 3
                    deductions.append({
                        "category": "Activity & Maintenance",
                        "points_lost": 4,
                        "title": "Stale release history",
                        "evidence": f"Latest release was {days_since_rel} days ago (>1 year).",
                        "recommendation": "Publish a new tagged release to provide users with a stable reference version.",
                        "priority": "Medium",
                    })
            else:
                act_score += 4
        else:
            deductions.append({
                "category": "Activity & Maintenance",
                "points_lost": 7,
                "title": "No tagged releases",
                "evidence": "No published releases found via the GitHub Releases API.",
                "recommendation": "Use semantic versioned releases (e.g., v1.0.0) with changelogs so consumers can rely on stable versions.",
                "priority": "Medium",
            })

    act_score = min(act_score, act_max)

    # -------------------------------------------------------------
    # 3. Issue Management (Max 20 pts)
    # (Excludes Pull Requests strictly!)
    # -------------------------------------------------------------
    iss_score = 0
    iss_max = CATEGORY_WEIGHTS["issue_management"]

    pure_issues = issues_data.get("issues", [])
    open_pure_issues = issues_data.get("open_issues") if "open_issues" in issues_data else [i for i in pure_issues if i["state"] == "open"]
    closed_pure_issues = issues_data.get("closed_issues") if "closed_issues" in issues_data else [i for i in pure_issues if i["state"] == "closed"]
    total_pure = issues_data.get("total_sample_count", len(pure_issues))

    # Add transparency note regarding issue sample
    if issues_data.get("sample_notice"):
        data_limitations.append(issues_data["sample_notice"])
    if issues_data.get("rate_limit_warning"):
        data_limitations.append(issues_data["rate_limit_warning"])

    has_issues_enabled = repo_data.get("has_issues", True)
    if not has_issues_enabled:
        deductions.append({
            "category": "Issue Management",
            "points_lost": 20,
            "title": "Issues are disabled",
            "evidence": "Repository settings have disabled GitHub Issues.",
            "recommendation": "Enable GitHub Issues in repository settings so users can report bugs and request features.",
            "priority": "High",
        })
    elif total_pure == 0:
        # No issues in sample
        iss_score = 12
        deductions.append({
            "category": "Issue Management",
            "points_lost": 8,
            "title": "No issues in recent sample",
            "evidence": "No issues available in sample to assess triage responsiveness.",
            "recommendation": "Encourage bug reports and track work openly using GitHub Issues.",
            "priority": "Low",
        })
    else:
        # 3.1 Closed vs Total Ratio in sample (Max 8 pts)
        closed_ratio = len(closed_pure_issues) / total_pure if total_pure > 0 else 0
        if closed_ratio >= 0.40:
            iss_score += 8
        elif closed_ratio >= 0.20:
            iss_score += 6
            deductions.append({
                "category": "Issue Management",
                "points_lost": 2,
                "title": "Moderate issue resolution rate in sample",
                "evidence": f"{round(closed_ratio * 100, 1)}% of analyzed sample ({len(closed_pure_issues)}/{total_pure}) are closed.",
                "recommendation": "Continue actively closing resolved or stale issues.",
                "priority": "Low",
            })
        elif closed_ratio >= 0.05:
            iss_score += 3
            deductions.append({
                "category": "Issue Management",
                "points_lost": 5,
                "title": "Low issue closure rate",
                "evidence": f"Only {round(closed_ratio * 100, 1)}% of sampled issues are resolved.",
                "recommendation": "Triage and resolve long-standing open issues to reduce backlog.",
                "priority": "Medium",
            })
        else:
            deductions.append({
                "category": "Issue Management",
                "points_lost": 8,
                "title": "Unresolved issue backlog",
                "evidence": f"Almost all sampled issues ({len(open_pure_issues)}/{total_pure}) remain open.",
                "recommendation": "Review open issues and close obsolete or answered items.",
                "priority": "Medium",
            })

        # 3.2 Issue Labeling Hygiene (Max 6 pts)
        labeled_count = sum(1 for i in pure_issues if i.get("labels"))
        label_ratio = labeled_count / total_pure if total_pure > 0 else 0
        if label_ratio >= 0.50:
            iss_score += 6
        elif label_ratio >= 0.20:
            iss_score += 3
            deductions.append({
                "category": "Issue Management",
                "points_lost": 3,
                "title": "Incomplete issue labeling",
                "evidence": f"{round(label_ratio * 100, 1)}% of sampled issues have categorization labels.",
                "recommendation": "Add descriptive labels (e.g., 'bug', 'enhancement', 'documentation') to help contributors filter work.",
                "priority": "Medium",
            })
        else:
            deductions.append({
                "category": "Issue Management",
                "points_lost": 6,
                "title": "Lack of issue labels",
                "evidence": f"Only {round(label_ratio * 100, 1)}% of sampled issues have labels.",
                "recommendation": "Implement an issue tagging system with labels like 'bug', 'documentation', and 'good first issue'.",
                "priority": "Medium",
            })

        # 3.3 Issue Age / Freshness (Max 6 pts)
        if open_pure_issues:
            ages = []
            for i in open_pure_issues:
                if i.get("created_at"):
                    ages.append(max(0, (now - i["created_at"]).days))
            median_age = (sorted(ages)[len(ages) // 2]) if ages else 0

            if median_age <= 60:
                iss_score += 6
            elif median_age <= 180:
                iss_score += 4
                deductions.append({
                    "category": "Issue Management",
                    "points_lost": 2,
                    "title": "Moderate median issue age",
                    "evidence": f"Median age of sampled open issues is {median_age} days.",
                    "recommendation": "Check for stale open issues and respond to community queries.",
                    "priority": "Low",
                })
            else:
                iss_score += 2
                deductions.append({
                    "category": "Issue Management",
                    "points_lost": 4,
                    "title": "Aging open issue backlog",
                    "evidence": f"Median age of sampled open issues is {median_age} days (>6 months).",
                    "recommendation": "Set up a stale-issue bot or conduct a triage day to address aged inquiries.",
                    "priority": "Medium",
                })
        else:
            iss_score += 6

    iss_score = min(iss_score, iss_max)

    # -------------------------------------------------------------
    # 4. Community Participation (Max 15 pts)
    # (Note: Stars alone do not prove quality; they reflect awareness)
    # -------------------------------------------------------------
    comm_score = 0
    comm_max = CATEGORY_WEIGHTS["community"]

    # 4.1 Contributor count (Max 7 pts)
    contributor_count = contributors_data.get("count", 0)
    total_est_contributors = contributors_data.get("total_estimated") or contributor_count

    if total_est_contributors >= 10:
        comm_score += 7
    elif total_est_contributors >= 5:
        comm_score += 5
    elif total_est_contributors >= 2:
        comm_score += 3
        deductions.append({
            "category": "Community Participation",
            "points_lost": 4,
            "title": "Small contributor base",
            "evidence": f"Repository has {total_est_contributors} contributor(s) in sample.",
            "recommendation": "Lower barrier to entry by advertising good first issues and accepting community PRs.",
            "priority": "Medium",
        })
    elif total_est_contributors == 1:
        comm_score += 1
        deductions.append({
            "category": "Community Participation",
            "points_lost": 6,
            "title": "Single maintainer (High bus factor)",
            "evidence": "Only 1 contributor detected. Project depends entirely on a single person.",
            "recommendation": "Encourage co-maintainers or external contributors to reduce project risk.",
            "priority": "High",
        })
    else:
        deductions.append({
            "category": "Community Participation",
            "points_lost": 7,
            "title": "No contributors found",
            "evidence": "Contributor list returned empty or data is being compiled by GitHub.",
            "recommendation": "Encourage contributions and acknowledge collaborators.",
            "priority": "Medium",
        })

    # Note pagination limitations in transparency
    if contributors_data.get("is_sample"):
        data_limitations.append(
            f"Contributor count ({contributor_count} fetched) is sampled from the first page of GitHub API results to respect rate limits. Estimated total is ~{total_est_contributors}."
        )

    # 4.2 Forks (Max 4 pts)
    forks_count = repo_data.get("forks_count", 0)
    if forks_count >= 20:
        comm_score += 4
    elif forks_count >= 5:
        comm_score += 3
    elif forks_count >= 1:
        comm_score += 1
        deductions.append({
            "category": "Community Participation",
            "points_lost": 3,
            "title": "Few forks",
            "evidence": f"Repository has {forks_count} fork(s).",
            "recommendation": "Clear documentation and modular design encourage developers to fork and extend your project.",
            "priority": "Low",
        })
    else:
        deductions.append({
            "category": "Community Participation",
            "points_lost": 4,
            "title": "Zero forks",
            "evidence": "No forks detected.",
            "recommendation": "Make the project easier to run locally to stimulate community experimentation.",
            "priority": "Low",
        })

    # 4.3 Stars / Community Interest (Max 4 pts)
    stars_count = repo_data.get("stargazers_count", 0)
    if stars_count >= 50:
        comm_score += 4
    elif stars_count >= 10:
        comm_score += 3
    elif stars_count >= 1:
        comm_score += 1
        deductions.append({
            "category": "Community Participation",
            "points_lost": 3,
            "title": "Modest community visibility",
            "evidence": f"Repository has {stars_count} star(s).",
            "recommendation": "Share the repository in relevant developer forums, conferences, or student showcases.",
            "priority": "Low",
        })
    else:
        deductions.append({
            "category": "Community Participation",
            "points_lost": 4,
            "title": "No stars",
            "evidence": "Repository has 0 stars.",
            "recommendation": "Promote the repository to increase developer awareness.",
            "priority": "Low",
        })

    comm_score = min(comm_score, comm_max)

    # -------------------------------------------------------------
    # 5. Beginner Accessibility (Max 15 pts)
    # -------------------------------------------------------------
    beg_score = 0
    beg_max = CATEGORY_WEIGHTS["beginner_friendly"]

    # 5.1 Beginner-friendly labeled issues (Max 8 pts)
    beginner_issue_count = len(beginner_issues)
    if beginner_issue_count >= 3:
        beg_score += 8
    elif beginner_issue_count >= 1:
        beg_score += 5
        deductions.append({
            "category": "Beginner Accessibility",
            "points_lost": 3,
            "title": "Few beginner-friendly issues",
            "evidence": f"Found {beginner_issue_count} issue(s) labeled with beginner tags.",
            "recommendation": "Curate more starter issues with explicit step-by-step guidance for new contributors.",
            "priority": "Medium",
        })
    else:
        deductions.append({
            "category": "Beginner Accessibility",
            "points_lost": 8,
            "title": "No beginner-friendly issues found",
            "evidence": "No open issues found with labels like 'good first issue' or 'help wanted'.",
            "recommendation": "Label approachable bug fixes or documentation tasks as 'good first issue' to attract newcomers.",
            "priority": "High",
        })

    # 5.2 Onboarding / Contributing documentation (Max 4 pts)
    if has_contributing:
        beg_score += 4
    else:
        deductions.append({
            "category": "Beginner Accessibility",
            "points_lost": 4,
            "title": "No onboarding guide for beginners",
            "evidence": "Missing CONTRIBUTING.md file.",
            "recommendation": "Provide a step-by-step guide explaining how to clone, run tests, and open a PR.",
            "priority": "High",
        })

    # 5.3 Open issues available for newcomers (Max 3 pts)
    if len(open_pure_issues) > 0:
        beg_score += 3
    else:
        deductions.append({
            "category": "Beginner Accessibility",
            "points_lost": 3,
            "title": "No open issues available",
            "evidence": "No open issues found in recent sample.",
            "recommendation": "Maintain an open backlog of minor improvements, bug fixes, or documentation tasks.",
            "priority": "Medium",
        })

    beg_score = min(beg_score, beg_max)

    # -------------------------------------------------------------
    # Total Score Calculation
    # -------------------------------------------------------------
    overall_score = doc_score + act_score + iss_score + comm_score + beg_score
    overall_score = max(0, min(100, round(overall_score)))

    # Determine qualitative rating
    if overall_score >= 85:
        health_rating = "Excellent"
        rating_color = "#28a745"
    elif overall_score >= 70:
        health_rating = "Good"
        rating_color = "#17a2b8"
    elif overall_score >= 50:
        health_rating = "Moderate"
        rating_color = "#ffc107"
    elif overall_score >= 30:
        health_rating = "Needs Attention"
        rating_color = "#fd7e14"
    else:
        health_rating = "Dormant / Critical"
        rating_color = "#dc3545"

    category_scores = {
        "documentation": {
            "name": "Documentation",
            "score": doc_score,
            "max": doc_max,
            "percentage": round((doc_score / doc_max) * 100, 1),
        },
        "activity": {
            "name": "Activity & Maintenance",
            "score": act_score,
            "max": act_max,
            "percentage": round((act_score / act_max) * 100, 1),
        },
        "issue_management": {
            "name": "Issue Management",
            "score": iss_score,
            "max": iss_max,
            "percentage": round((iss_score / iss_max) * 100, 1),
        },
        "community": {
            "name": "Community Participation",
            "score": comm_score,
            "max": comm_max,
            "percentage": round((comm_score / comm_max) * 100, 1),
        },
        "beginner_friendly": {
            "name": "Beginner Accessibility",
            "score": beg_score,
            "max": beg_max,
            "percentage": round((beg_score / beg_max) * 100, 1),
        },
    }

    # Sort deductions by points lost (descending)
    deductions_sorted = sorted(deductions, key=lambda d: d["points_lost"], reverse=True)

    # Generate prioritized recommendations
    priority_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    recommendations = sorted(
        deductions,
        key=lambda d: (priority_order.get(d.get("priority", "Low"), 3), -d["points_lost"]),
    )

    summary_metrics = {
        "full_name": repo_data.get("full_name"),
        "description": repo_data.get("description"),
        "language": repo_data.get("language"),
        "license": repo_data.get("license") or "None",
        "stargazers_count": repo_data.get("stargazers_count", 0),
        "forks_count": repo_data.get("forks_count", 0),
        "days_since_push": days_since_push,
        "commits_sampled": len(commits_data),
        "pure_issues_sampled": total_pure,
        "prs_excluded": issues_data.get("prs_excluded_count", 0),
        "open_pure_issues": len(open_pure_issues),
        "closed_pure_issues": len(closed_pure_issues),
        "open_sample_pct": issues_data.get(
            "open_sample_pct",
            round((len(open_pure_issues) / total_pure) * 100, 1) if total_pure > 0 else 0.0,
        ),
        "closed_sample_pct": issues_data.get(
            "closed_sample_pct",
            round((len(closed_pure_issues) / total_pure) * 100, 1) if total_pure > 0 else 0.0,
        ),
        "is_sample": issues_data.get("is_sample", True),
        "sample_notice": issues_data.get("sample_notice"),
        "contributors_sampled": contributor_count,
        "contributors_estimated": total_est_contributors,
        "beginner_issues_count": len(beginner_issues),
        "releases_count": len(releases_data),
        "readme_exists": readme_exists,
        "readme_size": readme_size,
    }

    return {
        "overall_score": overall_score,
        "health_rating": health_rating,
        "rating_color": rating_color,
        "category_scores": category_scores,
        "deductions": deductions_sorted,
        "recommendations": recommendations,
        "summary": summary_metrics,
        "beginner_issues": beginner_issues,
        "data_limitations": data_limitations,
    }
