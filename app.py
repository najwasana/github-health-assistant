"""
app.py
======
Streamlit Dashboard for GitHub Repository Health & Beginner Contribution Assistant.

Features:
- Live GitHub REST API analysis (public repos, no token strictly required)
- Optional Personal Access Token for extended 5,000 req/hr rate limits
- 100-point transparent health score breakdown across 5 categories
- Strict separation of Pull Requests from Issues
- Interactive Plotly visualizations (commit activity, issue breakdown, labels)
- Beginner-friendly issue discovery with direct links and caveats
- Prioritized, evidence-backed repository improvement suggestions
- Complete methodology documentation and transparency notes
- Interactive student feedback mechanism
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analyzer import analyze_repository
from github_api import (
    AuthenticationError,
    EmptyRepoError,
    GitHubAPIError,
    GitHubClient,
    RateLimitExceededError,
    RepoNotFoundError,
    parse_repo_url,
)
from issue_classifier import IssueClassifier

# Page configuration
st.set_page_config(
    page_title="GitHub Health & Beginner Contribution Assistant",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for polished, competition-ready UI
st.markdown(
    """
    <style>
    /* Google Font Import */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* Global Typography & Base */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    /* Backgrounds: Lavender tint */
    .stApp {
        background: linear-gradient(180deg, #F9F8FE 0%, #F4F1FD 100%);
    }

    /* Headings */
    h1, h2, h3, h4, h5, h6 {
        color: #2D1B69 !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em;
    }

    /* Deep Purple Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1E1242 0%, #150C33 100%) !important;
        border-right: 1px solid rgba(139, 92, 246, 0.2);
    }
    [data-testid="stSidebar"] * {
        color: #EDE9FE !important;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] .stCaption,
    [data-testid="stSidebar"] small {
        color: #C4B5FD !important;
    }
    [data-testid="stSidebar"] input {
        background-color: #271954 !important;
        color: #FFFFFF !important;
        border: 1px solid #4C1D95 !important;
        border-radius: 10px !important;
    }
    [data-testid="stSidebar"] div[data-baseweb="select"] > div {
        background-color: #271954 !important;
        color: #FFFFFF !important;
        border: 1px solid #4C1D95 !important;
        border-radius: 10px !important;
    }
    [data-testid="stSidebar"] div[data-baseweb="select"] span {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] [data-testid="stMetric"] {
        background: rgba(139, 92, 246, 0.15);
        border: 1px solid rgba(196, 181, 253, 0.25);
        border-radius: 12px;
        padding: 12px 16px;
    }
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #A78BFA !important;
        font-weight: 800;
    }
    [data-testid="stSidebar"] [data-testid="stMetricLabel"] {
        color: #DDD6FE !important;
    }

    /* Sidebar Brand Card */
    .sidebar-brand-card {
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.25) 0%, rgba(109, 40, 217, 0.35) 100%);
        border: 1px solid rgba(196, 181, 253, 0.3);
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        gap: 12px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
    }
    .sidebar-brand-icon {
        width: 44px;
        height: 44px;
        border-radius: 12px;
        background: linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 10px rgba(109, 40, 217, 0.4);
        flex-shrink: 0;
    }
    .sidebar-brand-title {
        font-size: 1.15rem;
        font-weight: 800;
        color: #FFFFFF !important;
        line-height: 1.2;
    }
    .sidebar-brand-sub {
        font-size: 0.72rem;
        color: #C4B5FD !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600;
    }

    /* Main Header Hero */
    .hero-banner {
        background: linear-gradient(135deg, #FFFFFF 0%, #F5F3FF 100%);
        border: 1px solid #E9D5FF;
        border-radius: 20px;
        padding: 24px 28px;
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(139, 92, 246, 0.08);
        position: relative;
        overflow: hidden;
    }
    .hero-banner::after {
        content: '';
        position: absolute;
        top: -60px;
        right: -60px;
        width: 180px;
        height: 180px;
        background: radial-gradient(circle, rgba(167, 139, 250, 0.25) 0%, rgba(255, 255, 255, 0) 70%);
        border-radius: 50%;
        pointer-events: none;
    }
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #2D1B69;
        margin-bottom: 6px;
        letter-spacing: -0.02em;
    }
    .hero-subtitle {
        font-size: 1.02rem;
        color: #6B5B95;
        line-height: 1.5;
        max-width: 850px;
    }
    .hero-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #EDE9FE;
        color: #6D28D9;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        margin-bottom: 12px;
        border: 1px solid #DDD6FE;
    }

    /* Input & Button Refinement */
    div[data-testid="stTextInput"] input {
        border: 1.5px solid #DDD6FE !important;
        background-color: #FFFFFF !important;
        color: #1E1B4B !important;
        border-radius: 12px !important;
        padding: 12px 16px !important;
        font-size: 0.95rem !important;
        box-shadow: 0 2px 6px rgba(139, 92, 246, 0.04) !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color: #8B5CF6 !important;
        box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.18) !important;
    }

    /* Primary Purple Button */
    div.stButton > button[kind="primary"],
    div.stButton > button {
        background: linear-gradient(135deg, #7C3AED 0%, #6D28D9 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        box-shadow: 0 4px 14px rgba(124, 58, 237, 0.3) !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button:hover {
        background: linear-gradient(135deg, #6D28D9 0%, #5B21B6 100%) !important;
        box-shadow: 0 6px 20px rgba(124, 58, 237, 0.4) !important;
        transform: translateY(-1px);
    }

    /* Clean White SaaS Content Cards */
    .metric-card, .saas-card {
        background-color: #FFFFFF;
        border: 1px solid #E9D5FF;
        border-radius: 16px;
        padding: 20px 22px;
        margin-bottom: 16px;
        box-shadow: 0 4px 16px -2px rgba(139, 92, 246, 0.06);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .metric-card:hover, .saas-card:hover {
        box-shadow: 0 8px 24px -4px rgba(139, 92, 246, 0.12);
        border-color: #D8B4FE;
    }

    /* Stat Cards */
    .stat-card {
        background: #FFFFFF;
        border: 1px solid #E9D5FF;
        border-radius: 16px;
        padding: 18px 20px;
        box-shadow: 0 4px 12px rgba(139, 92, 246, 0.05);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        height: 100%;
        transition: all 0.2s ease;
    }
    .stat-card:hover {
        transform: translateY(-2px);
        border-color: #C4B5FD;
        box-shadow: 0 8px 20px rgba(139, 92, 246, 0.1);
    }
    .stat-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 10px;
    }
    .stat-icon {
        width: 36px;
        height: 36px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.15rem;
        background: #F3E8FF;
        color: #7C3AED;
    }
    .stat-title {
        font-size: 0.8rem;
        font-weight: 700;
        color: #6B5B95;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .stat-value {
        font-size: 1.75rem;
        font-weight: 800;
        color: #2D1B69;
        line-height: 1.1;
    }
    .stat-sub {
        font-size: 0.78rem;
        color: #8B7FA9;
        margin-top: 6px;
    }

    /* Overall Health Score Card */
    .health-score-card {
        background: linear-gradient(135deg, #FFFFFF 0%, #FAF5FF 100%);
        border: 2px solid #D8B4FE;
        border-radius: 20px;
        padding: 28px 24px;
        text-align: center;
        box-shadow: 0 10px 30px -5px rgba(139, 92, 246, 0.15);
        position: relative;
        overflow: hidden;
    }
    .health-score-label {
        font-size: 0.85rem;
        font-weight: 700;
        color: #6D28D9;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 4px;
    }
    .health-score-val {
        font-size: 4.2rem;
        font-weight: 900;
        line-height: 1;
        letter-spacing: -0.04em;
        margin: 8px 0;
    }
    .health-score-denom {
        font-size: 1.6rem;
        font-weight: 600;
        color: #9CA3AF;
    }
    .health-badge-pill {
        display: inline-block;
        font-weight: 700;
        padding: 6px 18px;
        border-radius: 9999px;
        font-size: 0.95rem;
        letter-spacing: 0.02em;
        margin-top: 10px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    }

    /* Category Cards & Progress */
    .category-card {
        background: #FFFFFF;
        border: 1px solid #E9D5FF;
        border-radius: 14px;
        padding: 16px 18px;
        margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(139, 92, 246, 0.04);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .category-name {
        font-size: 0.95rem;
        font-weight: 700;
        color: #2D1B69;
    }
    .category-points {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.88rem;
        font-weight: 600;
        color: #6D28D9;
        background: #F3E8FF;
        padding: 4px 10px;
        border-radius: 8px;
    }

    /* Formula Banner */
    .formula-container {
        background: linear-gradient(135deg, #F5F3FF 0%, #EDE9FE 100%);
        border: 1px solid #DDD6FE;
        border-left: 5px solid #7C3AED;
        border-radius: 14px;
        padding: 18px 22px;
        margin: 20px 0;
        box-shadow: 0 4px 12px rgba(124, 58, 237, 0.05);
    }
    .formula-title {
        font-weight: 700;
        color: #4C1D95;
        font-size: 1.05rem;
        margin-bottom: 8px;
    }

    /* Badge Pills */
    .badge-pill {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 4px 10px;
        border-radius: 8px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-right: 6px;
        margin-bottom: 6px;
        border: 1px solid transparent;
    }

    /* Recommendation Cards */
    .rec-card {
        background: #FFFFFF;
        border: 1px solid #E9D5FF;
        border-left: 5px solid #8B5CF6;
        padding: 18px 22px;
        border-radius: 14px;
        margin-bottom: 14px;
        box-shadow: 0 4px 14px rgba(139, 92, 246, 0.05);
        transition: transform 0.15s ease;
    }
    .rec-card:hover {
        transform: translateX(3px);
    }
    .rec-card.Critical { border-left-color: #EF4444; }
    .rec-card.High { border-left-color: #F97316; }
    .rec-card.Medium { border-left-color: #F59E0B; }
    .rec-card.Low { border-left-color: #8B5CF6; }

    /* Streamlit Tabs Styling */
    div[data-baseweb="tab-list"] {
        gap: 8px !important;
        background: #F3E8FF !important;
        padding: 6px !important;
        border-radius: 16px !important;
        border: 1px solid #E9D5FF !important;
        margin-bottom: 20px !important;
    }
    div[data-baseweb="tab"] {
        border-radius: 12px !important;
        color: #5B21B6 !important;
        font-weight: 600 !important;
        padding: 10px 18px !important;
        font-size: 0.92rem !important;
        border: none !important;
        background: transparent !important;
        transition: all 0.2s ease !important;
    }
    div[data-baseweb="tab"]:hover {
        background: rgba(255, 255, 255, 0.6) !important;
        color: #4C1D95 !important;
    }
    div[data-baseweb="tab"][aria-selected="true"] {
        background: #FFFFFF !important;
        color: #6D28D9 !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 12px rgba(109, 40, 217, 0.12) !important;
    }
    div[data-baseweb="tab-border"] {
        display: none !important;
    }

    /* Expanders */
    div[data-testid="stExpander"] {
        background: #FFFFFF !important;
        border: 1px solid #E9D5FF !important;
        border-radius: 14px !important;
        box-shadow: 0 2px 8px rgba(139, 92, 246, 0.04) !important;
        margin-bottom: 12px !important;
    }
    div[data-testid="stExpander"] summary {
        font-weight: 600 !important;
        color: #372554 !important;
    }

    /* Progress bars: lavender fill */
    div[data-testid="stProgress"] > div > div > div > div {
        background: linear-gradient(90deg, #A78BFA 0%, #7C3AED 100%) !important;
        border-radius: 9999px !important;
    }
    div[data-testid="stProgress"] > div > div {
        background-color: #EDE9FE !important;
        border-radius: 9999px !important;
    }

    /* Code styling */
    code {
        font-family: 'JetBrains Mono', monospace !important;
        background-color: #F3E8FF !important;
        color: #6D28D9 !important;
        padding: 2px 6px !important;
        border-radius: 6px !important;
        font-size: 0.85em !important;
    }

    /* Alerts / Notices */
    div[data-testid="stAlert"] {
        border-radius: 14px !important;
        border: 1px solid #E9D5FF !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

FEEDBACK_FILE = Path("feedback_store.json")


def load_feedback_store() -> List[Dict[str, Any]]:
    """Load persisted student feedback from local JSON storage."""
    if FEEDBACK_FILE.exists():
        try:
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_feedback_entry(entry: Dict[str, Any]) -> None:
    """Save feedback entry to local JSON storage and session state."""
    feedbacks = load_feedback_store()
    feedbacks.append(entry)
    try:
        with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
            json.dump(feedbacks, f, indent=2)
    except Exception:
        pass


# Sidebar Configuration
with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand-card">
            <div class="sidebar-brand-icon">
                <svg height="28" viewBox="0 0 16 16" version="1.1" width="28" fill="#FFFFFF" aria-hidden="true">
                    <path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"></path>
                </svg>
            </div>
            <div>
                <div class="sidebar-brand-title">GitHub Health</div>
                <div class="sidebar-brand-sub">Assistant • SaaS Audit</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### ⚙️ Settings & Authentication")

    st.markdown(
        """
        <div style="background: rgba(139, 92, 246, 0.12); border: 1px solid rgba(196, 181, 253, 0.2); border-radius: 12px; padding: 12px 14px; margin-bottom: 14px; font-size: 0.85rem; color: #EDE9FE;">
            <strong style="color: #FFFFFF;">GitHub REST API Access:</strong><br/>
            • Public repos: <strong>60 req/hr</strong><br/>
            • With Personal Token: <strong>5,000 req/hr</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )

    token_input = st.text_input(
        "GitHub Token (Optional)",
        type="password",
        help="Personal access token with public_repo scope. Never stored or logged.",
        value=os.environ.get("GITHUB_TOKEN", ""),
    )

    client = GitHubClient(token=token_input.strip() if token_input else None)

    # Display API rate limit status
    rate_info = client.get_rate_limit()
    if rate_info.get("limit"):
        remaining = rate_info.get("remaining", 0)
        limit = rate_info.get("limit", 60)
        reset_dt = rate_info.get("reset_datetime")
        reset_label = reset_dt.strftime("%H:%M:%S UTC") if reset_dt else "N/A"

        st.metric(
            label="API Requests Remaining",
            value=f"{remaining} / {limit}",
            help=f"Limit resets at {reset_label}",
        )
        if remaining < 10:
            st.warning("⚠️ Low API quota remaining. Consider supplying a GitHub Token.")

    st.markdown("<hr style='border: none; border-top: 1px solid rgba(196, 181, 253, 0.2); margin: 18px 0;'/>", unsafe_allow_html=True)
    st.markdown("### 🚀 Competition Presets")
    st.caption("Quickly test representative public repositories:")
    demo_repos = [
        "Select a demo preset...",
        "pallets/flask",
        "psf/requests",
        "tiangolo/fastapi",
        "streamlit/streamlit",
    ]
    selected_preset = st.selectbox("Preset Repositories", demo_repos)

    st.markdown("<hr style='border: none; border-top: 1px solid rgba(196, 181, 253, 0.2); margin: 18px 0;'/>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style="font-size: 0.78rem; color: #C4B5FD; text-align: center; padding: 6px;">
            🎓 <strong>College Project Presentation Edition</strong><br/>
            Streamlit • Plotly • Machine Learning
        </div>
        """,
        unsafe_allow_html=True,
    )

# Main Header Hero Banner
st.markdown(
    """
    <div class="hero-banner">
        <div class="hero-pill">✨ College Project Presentation Edition • Transparent Audit</div>
        <div class="hero-title">🧭 GitHub Repository Health & Beginner Assistant</div>
        <div class="hero-subtitle">
            Comprehensive open-source repository health auditing, real commit & issue profiling,
            and machine-learning powered beginner contribution discovery.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Repository Input Section
col_input, col_btn = st.columns([4, 1])

with col_input:
    default_val = selected_preset if selected_preset and selected_preset != "Select a demo preset..." else "psf/requests"
    repo_input = st.text_input(
        "Enter GitHub Repository URL or 'owner/repo'",
        value=default_val,
        placeholder="e.g., https://github.com/psf/requests or pallets/flask",
        help="Accepts GitHub URLs, shorthand 'owner/repo', or .git links.",
    )

with col_btn:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    analyze_btn = st.button("🔍 Analyze Repository", type="primary", width="stretch")

# Analysis execution
if analyze_btn or "analysis_data" in st.session_state:
    if analyze_btn:
        st.session_state.pop("analysis_data", None)

        try:
            owner, repo = parse_repo_url(repo_input)
        except ValueError as e:
            st.error(f"❌ Input Validation Error: {e}")
            st.stop()

        with st.status("Analyzing repository...", expanded=True) as status:
            try:
                status.update(label=f"Fetching metadata for '{owner}/{repo}'...")
                repo_meta = client.get_repo(owner, repo)

                status.update(label="Inspecting README and documentation size...")
                readme_info = client.get_readme(owner, repo)

                status.update(label="Querying community standards profile...")
                comm_profile = client.get_community_profile(owner, repo)

                status.update(label="Retrieving default branch commit cadence...")
                commits = client.get_commits(owner, repo, per_page=100)

                status.update(label="Analyzing issues (fetching open and closed separately, excluding pull requests)...")
                issues = client.get_issues_separate_states(owner, repo, per_page=50, max_pages=1)

                status.update(label="Finding beginner-friendly labeled issues...")
                beginner_issues = client.get_beginner_friendly_issues(owner, repo, max_count=20)

                status.update(label="Gathering contributor metrics & pagination info...")
                contributors = client.get_contributors(owner, repo, per_page=100)

                status.update(label="Checking latest releases & versions...")
                releases = client.get_releases(owner, repo, per_page=10)

                status.update(label="Computing transparent 100-point health score...")
                analysis_results = analyze_repository(
                    repo_data=repo_meta,
                    readme_data=readme_info,
                    community_profile=comm_profile,
                    commits_data=commits,
                    issues_data=issues,
                    beginner_issues=beginner_issues,
                    contributors_data=contributors,
                    releases_data=releases,
                )

                st.session_state["analysis_data"] = {
                    "results": analysis_results,
                    "repo_meta": repo_meta,
                    "readme_info": readme_info,
                    "commits": commits,
                    "issues": issues,
                    "contributors": contributors,
                    "releases": releases,
                }
                status.update(label="✅ Analysis complete!", state="complete", expanded=False)

            except RepoNotFoundError:
                status.update(label="❌ Repository not found", state="error")
                st.error(f"Repository '{owner}/{repo}' was not found. Please verify that the repository exists and is public.")
                st.stop()
            except RateLimitExceededError as e:
                status.update(label="⚠️ GitHub API Rate Limit Reached", state="error")
                st.error(str(e))
                st.info("💡 You can provide a free GitHub Personal Access Token in the left sidebar to obtain 5,000 requests/hour.")
                st.stop()
            except AuthenticationError as e:
                status.update(label="❌ Authentication Failed", state="error")
                st.error(str(e))
                st.stop()
            except EmptyRepoError:
                status.update(label="⚠️ Repository is empty", state="error")
                st.warning(f"Repository '{owner}/{repo}' is empty or has no commits on its default branch.")
                st.stop()
            except GitHubAPIError as e:
                status.update(label="❌ API Error", state="error")
                st.error(f"An error occurred while contacting the GitHub API: {e}")
                st.stop()

    # Load stored analysis from session state
    data_bundle = st.session_state.get("analysis_data")
    if not data_bundle:
        st.stop()

    res = data_bundle["results"]
    summary = res["summary"]
    repo_meta = data_bundle["repo_meta"]
    commits = data_bundle["commits"]
    issues = data_bundle["issues"]
    contributors = data_bundle["contributors"]

    # Transparency alerts for data limitations
    if res["data_limitations"]:
        with st.expander("ℹ️ Measurement & API Limitations (Transparency Notice)", expanded=False):
            for notice in res["data_limitations"]:
                st.markdown(f"- {notice}")
            st.caption("Note: Metrics are calculated from real API queries within safe rate-limit thresholds.")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Score Overview Banner & Category Score Cards
    col_score_l, col_score_r = st.columns([1, 2])

    with col_score_l:
        st.markdown(
            f"""
            <div class="health-score-card">
                <div class="health-score-label">Overall Health Score</div>
                <div class="health-score-val" style="color: {res['rating_color']};">
                    {res['overall_score']}<span class="health-score-denom">/100</span>
                </div>
                <div>
                    <span class="health-badge-pill" style="background-color: {res['rating_color']}18; color: {res['rating_color']}; border: 1.5px solid {res['rating_color']}40;">
                        ● {res['health_rating']}
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_score_r:
        st.markdown("#### 🎯 Category Score Breakdown")
        for cat_key, cat in res["category_scores"].items():
            pct = int((cat["score"] / cat["max"]) * 100) if cat["max"] > 0 else 0
            st.markdown(
                f"""
                <div style="background: #FFFFFF; border: 1px solid #E9D5FF; border-radius: 12px; padding: 10px 14px; margin-bottom: 8px; box-shadow: 0 2px 6px rgba(139, 92, 246, 0.03);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-weight: 700; color: #2D1B69; font-size: 0.92rem;">{cat['name']}</span>
                        <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #7C3AED; font-size: 0.85rem; background: #F3E8FF; padding: 2px 8px; border-radius: 6px;">
                            {cat['score']} / {cat['max']} pts ({pct}%)
                        </span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.progress(cat["score"] / cat["max"])

    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

    # Key Statistics Row inside Modern Stat Cards
    st.subheader(f"📊 Repository Snapshot: {summary['full_name']}")
    if summary["description"]:
        st.caption(f"_{summary['description']}_")

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-title">Stars</span>
                    <span class="stat-icon">⭐</span>
                </div>
                <div class="stat-value">{summary['stargazers_count']:,}</div>
                <div class="stat-sub">Stargazers total</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-title">Forks</span>
                    <span class="stat-icon">🍴</span>
                </div>
                <div class="stat-value">{summary['forks_count']:,}</div>
                <div class="stat-sub">Community forks</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-title">Pure Issues</span>
                    <span class="stat-icon">📋</span>
                </div>
                <div class="stat-value" style="font-size: 1.35rem;">{summary['open_pure_issues']} / {summary['closed_pure_issues']}</div>
                <div class="stat-sub">Open / Closed ({summary['prs_excluded']} PRs ignored)</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m4:
        contrib_val = f"~{summary['contributors_estimated']:,}" if summary["contributors_estimated"] else "N/A"
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-title">Contributors</span>
                    <span class="stat-icon">👥</span>
                </div>
                <div class="stat-value">{contrib_val}</div>
                <div class="stat-sub">Developer pool</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m5:
        lang_val = summary["language"] or "Unknown"
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-title">Language</span>
                    <span class="stat-icon">💻</span>
                </div>
                <div class="stat-value" style="font-size: 1.35rem;">{lang_val}</div>
                <div class="stat-sub">Primary language</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with m6:
        lic_val = summary["license"] or "None"
        st.markdown(
            f"""
            <div class="stat-card">
                <div class="stat-header">
                    <span class="stat-title">License</span>
                    <span class="stat-icon">⚖️</span>
                </div>
                <div class="stat-value" style="font-size: 1.35rem;">{lic_val}</div>
                <div class="stat-sub">Open-source license</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Tabbed Deep-Dive Sections
    tab_overview, tab_charts, tab_beginner, tab_ml, tab_recommendations, tab_methodology, tab_feedback = st.tabs([
        "🔍 Health Details",
        "📈 Activity & Charts",
        "🌱 Beginner Issues",
        "🤖 AI/ML Issue Finder",
        "💡 Recommendations",
        "📖 Methodology & Formula",
        "💬 Student Feedback",
    ])

    # ---------------- TAB 1: HEALTH DETAILS ----------------
    with tab_overview:
        st.subheader("Component-Level Health Audit")
        st.caption("Each category is evaluated against transparent rules and thresholds:")

        c1, c2 = st.columns(2)

        with c1:
            readme_label = "✅ Present" if summary["readme_exists"] else "❌ Missing"
            lic_label = "✅ Recognized" if summary["license"] != "None" else "❌ Missing"
            guide_label = "✅ Present" if data_bundle["readme_info"].get("exists") and res["category_scores"]["documentation"]["score"] > 15 else "⚠️ Review needed"
            days_push = summary["days_since_push"]
            push_txt = f"{days_push} days ago" if days_push is not None else "Unknown"

            st.markdown(
                f"""
                <div class="saas-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <h4 style="margin: 0; color: #2D1B69;">📄 Documentation Analysis</h4>
                        <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #7C3AED; background: #F3E8FF; padding: 2px 8px; border-radius: 6px; font-size: 0.85rem;">
                            {res['category_scores']['documentation']['score']} / {res['category_scores']['documentation']['max']} pts
                        </span>
                    </div>
                    <div style="font-size: 0.9rem; color: #372554; line-height: 1.8;">
                        • <strong>README Status:</strong> {readme_label} ({summary['readme_size']} bytes)<br/>
                        • <strong>Open-Source License:</strong> {lic_label}<br/>
                        • <strong>Contributing Guide:</strong> {guide_label}
                    </div>
                </div>

                <div class="saas-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <h4 style="margin: 0; color: #2D1B69;">⚡ Activity & Maintenance</h4>
                        <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #7C3AED; background: #F3E8FF; padding: 2px 8px; border-radius: 6px; font-size: 0.85rem;">
                            {res['category_scores']['activity']['score']} / {res['category_scores']['activity']['max']} pts
                        </span>
                    </div>
                    <div style="font-size: 0.9rem; color: #372554; line-height: 1.8;">
                        • <strong>Last Push:</strong> {push_txt}<br/>
                        • <strong>Commits Analyzed:</strong> {summary['commits_sampled']} on default branch<br/>
                        • <strong>Tagged Releases:</strong> {summary['releases_count']} found
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with c2:
            st.markdown(
                f"""
                <div class="saas-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <h4 style="margin: 0; color: #2D1B69;">🐞 Issue Management</h4>
                        <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #7C3AED; background: #F3E8FF; padding: 2px 8px; border-radius: 6px; font-size: 0.85rem;">
                            {res['category_scores']['issue_management']['score']} / {res['category_scores']['issue_management']['max']} pts
                        </span>
                    </div>
                    <div style="font-size: 0.9rem; color: #372554; line-height: 1.8;">
                        • <strong>Sampled Pure Issues:</strong> {summary['pure_issues_sampled']} ({summary['open_pure_issues']} open, {summary['closed_pure_issues']} closed)<br/>
                        • <strong>Pull Requests Filtered Out:</strong> {summary['prs_excluded']} PRs ignored<br/>
                        • <strong>Sample Resolution:</strong> {summary.get('open_sample_pct', 0)}% open / {summary.get('closed_sample_pct', 0)}% closed <em>(Sample only)</em>
                    </div>
                </div>

                <div class="saas-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <h4 style="margin: 0; color: #2D1B69;">🌐 Community & Accessibility</h4>
                        <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #7C3AED; background: #F3E8FF; padding: 2px 8px; border-radius: 6px; font-size: 0.85rem;">
                            {res['category_scores']['community']['score'] + res['category_scores']['beginner_friendly']['score']} / {res['category_scores']['community']['max'] + res['category_scores']['beginner_friendly']['max']} pts
                        </span>
                    </div>
                    <div style="font-size: 0.9rem; color: #372554; line-height: 1.8;">
                        • <strong>Contributor Pool:</strong> {summary['contributors_sampled']} sampled (~{summary['contributors_estimated']} total)<br/>
                        • <strong>Beginner-Friendly Issues:</strong> {summary['beginner_issues_count']} open tasks flagged<br/>
                        • <strong>Fork Engagement:</strong> {summary['forks_count']} community forks created
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ---------------- TAB 2: ACTIVITY & CHARTS ----------------
    with tab_charts:
        st.subheader("Visual Activity Profiling")

        ch_col1, ch_col2 = st.columns(2)

        with ch_col1:
            # Commit Timeline
            if commits:
                commit_dates = [c["date"] for c in commits if c.get("date")]
                if commit_dates:
                    df_commits = pd.DataFrame({"date": commit_dates})
                    df_commits["month_year"] = df_commits["date"].dt.to_period("M").astype(str)
                    counts = df_commits["month_year"].value_counts().sort_index().reset_index()
                    counts.columns = ["Month", "Commits"]

                    fig_commits = px.line(
                        counts,
                        x="Month",
                        y="Commits",
                        title=f"Commit Activity Trend ({len(commits)} commits sampled)",
                        markers=True,
                    )
                    fig_commits.update_traces(
                        line_color="#7C3AED",
                        line_width=3,
                        marker=dict(size=8, color="#A78BFA", line=dict(width=2, color="#5B21B6")),
                        fill="tozeroy",
                        fillcolor="rgba(196, 181, 253, 0.25)",
                    )
                    fig_commits.update_layout(
                        template="plotly_white",
                        font=dict(family="Plus Jakarta Sans", color="#2D1B69"),
                        plot_bgcolor="#FFFFFF",
                        paper_bgcolor="#FFFFFF",
                        margin=dict(l=20, r=20, t=45, b=20),
                        xaxis=dict(gridcolor="#F3E8FF", title_font=dict(size=12, color="#6B5B95")),
                        yaxis=dict(gridcolor="#F3E8FF", title_font=dict(size=12, color="#6B5B95")),
                    )
                    st.markdown("<div class='saas-card'>", unsafe_allow_html=True)
                    st.plotly_chart(fig_commits, width="stretch")
                    st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.info("Commit dates unavailable for timeline.")
            else:
                st.info("No commits available in recent sample.")

        with ch_col2:
            # Issue State Breakdown (Excluding PRs, Separate Open & Closed Queries)
            total_retrieved = issues.get("total_sample_count", len(issues.get("issues", [])))
            open_cnt = issues.get("open_count", 0)
            closed_cnt = issues.get("closed_count", 0)
            open_pct = issues.get("open_sample_pct", 0.0)
            closed_pct = issues.get("closed_sample_pct", 0.0)
            prs_excluded = issues.get("prs_excluded_count", 0)

            if total_retrieved > 0:
                fig_issues = px.pie(
                    names=[
                        f"Open ({open_cnt} • {open_pct}%)",
                        f"Closed ({closed_cnt} • {closed_pct}%)",
                    ],
                    values=[open_cnt, closed_cnt],
                    title=f"Pure Issue Resolution Ratio (N = {total_retrieved} Analyzed)",
                    color_discrete_sequence=["#A78BFA", "#10B981"],
                    hole=0.60,
                )
                fig_issues.update_traces(
                    textinfo="percent+value",
                    textfont=dict(family="Plus Jakarta Sans", size=12),
                    hovertemplate="%{label}<br>Count: %{value}<br>Sample Share: %{percent}<extra></extra>",
                    marker=dict(line=dict(color="#FFFFFF", width=3)),
                )
                fig_issues.update_layout(
                    template="plotly_white",
                    font=dict(family="Plus Jakarta Sans", color="#2D1B69"),
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FFFFFF",
                    legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
                    margin=dict(l=20, r=20, t=45, b=20),
                )
                st.markdown("<div class='saas-card'>", unsafe_allow_html=True)
                st.plotly_chart(fig_issues, width="stretch")

                st.warning(
                    f"⚠️ **Sample Limitation Notice:** Calculated from **{total_retrieved} pure issues** "
                    f"({open_cnt} open, {closed_cnt} closed) via separate GitHub REST queries "
                    f"(**{prs_excluded} pull requests excluded**). Represents retrieved sample only."
                )

                # Show pagination scale context if Link headers returned page counts
                open_pages = issues.get("open_last_page")
                closed_pages = issues.get("closed_last_page")
                if open_pages or closed_pages:
                    st.caption(
                        f"ℹ️ **Scale Context:** GitHub reports ~{open_pages or 1} page(s) of open items vs. "
                        f"~{closed_pages or 1} page(s) of closed items available on the repository."
                    )
                st.markdown("</div>", unsafe_allow_html=True)

                if issues.get("rate_limit_warning"):
                    st.info(f"⚡ {issues['rate_limit_warning']}")
            else:
                st.info("No issues found in sample (or GitHub issues are disabled).")

        # Top Issue Labels Distribution
        pure_issues = issues.get("issues", [])
        if pure_issues:
            label_list = []
            for i in pure_issues:
                label_list.extend(i.get("labels", []))
            if label_list:
                df_labels = pd.Series(label_list).value_counts().head(10).reset_index()
                df_labels.columns = ["Label", "Occurrences"]
                fig_labels = px.bar(
                    df_labels,
                    x="Occurrences",
                    y="Label",
                    orientation="h",
                    title="🏷️ Top 10 Issue Labels in Analyzed Sample",
                    color="Occurrences",
                    color_continuous_scale=["#C4B5FD", "#7C3AED"],
                )
                fig_labels.update_layout(
                    template="plotly_white",
                    font=dict(family="Plus Jakarta Sans", color="#2D1B69"),
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FFFFFF",
                    yaxis=dict(autorange="reversed", gridcolor="#F3E8FF"),
                    xaxis=dict(gridcolor="#F3E8FF"),
                    coloraxis_showscale=False,
                    margin=dict(l=20, r=20, t=40, b=20),
                )
                st.markdown("<div class='saas-card'>", unsafe_allow_html=True)
                st.plotly_chart(fig_labels, width="stretch")
                st.markdown("</div>", unsafe_allow_html=True)

    # ---------------- TAB 3: BEGINNER ISSUES ----------------
    with tab_beginner:
        st.subheader("🌱 Beginner-Friendly Contribution Opportunities")
        st.markdown(
            """
            > **⚠️ Important Contributor Guidance:**
            > Labels like `good first issue` or `help wanted` reflect maintainer intentions, but they **do not guarantee** that an issue is easy or suitable for every beginner.
            > Always read the discussion thread, check whether someone is already working on it, and ask polite questions in the issue before submitting code.
            """
        )

        beginner_list = res["beginner_issues"]
        if beginner_list:
            st.success(f"Discovered **{len(beginner_list)}** beginner-oriented open issues:")
            for issue in beginner_list:
                age_txt = f"{issue['age_days']} days ago" if issue.get("age_days") is not None else "Unknown"
                labels_html = " ".join([
                    f"<span class='badge-pill' style='background-color:#F3E8FF; color:#6D28D9; border-color:#DDD6FE;'>🏷️ {lbl}</span>"
                    for lbl in issue.get("labels", [])
                ])

                st.markdown(
                    f"""
                    <div class="saas-card" style="margin-bottom: 14px;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;">
                            <div>
                                <div style="font-weight: 700; font-size: 1.08rem; color: #2D1B69; margin-bottom: 4px;">
                                    #{issue['number']}: {issue['title']}
                                </div>
                                <div style="font-size: 0.85rem; color: #6B5B95; margin-bottom: 8px;">
                                    Opened by <strong>@{issue.get('author', 'unknown')}</strong> • {age_txt} • 💬 {issue.get('comments', 0)} comments
                                </div>
                                <div>{labels_html}</div>
                            </div>
                            <div style="flex-shrink: 0;">
                                <a href="{issue['html_url']}" target="_blank" style="text-decoration: none; display: inline-block; background: linear-gradient(135deg, #7C3AED 0%, #6D28D9 100%); color: #FFFFFF; font-weight: 600; font-size: 0.85rem; padding: 8px 16px; border-radius: 10px; box-shadow: 0 4px 10px rgba(124, 58, 237, 0.25);">
                                    View Issue ↗
                                </a>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.warning("No open issues labeled with 'good first issue' or 'help wanted' were detected.")
            st.info(
                "💡 **Tip for Maintainers:** You can attract new contributors by adding the `good first issue` label "
                "to small bug fixes, documentation typos, or test case additions."
            )

    # ---------------- TAB 4: AI/ML ISSUE FINDER ----------------
    with tab_ml:
        st.subheader("🤖 AI/ML Beginner Issue Finder")
        st.markdown(
            """
            This tab uses a **Machine Learning text classifier** (TF-IDF + Logistic Regression)
            to estimate the difficulty level of open issues from the repository.

            > **⚠️ Disclaimer:** ML predictions are **estimates** based on text vocabulary patterns
            > learned from a small curated training dataset. They are **not guarantees** of actual difficulty.
            > Always read the issue discussion and check maintainer expectations before contributing.
            """
        )

        # Load classifier (cached so it does not reload on every rerun)
        @st.cache_resource
        def load_classifier():
            """Load the trained ML classifier once and reuse across reruns."""
            from pathlib import Path as _P
            model_p = _P("models/issue_classifier_pipeline.joblib")
            meta_p = _P("models/model_metadata.json")
            return IssueClassifier(model_path=model_p, metadata_path=meta_p, auto_train=True)

        classifier = load_classifier()

        if not classifier.is_ready:
            st.error(
                "ML model could not be loaded or trained. "
                "Run `python train_model.py` from the project root to generate the model files."
            )
        else:
            # Show model info in an expander
            with st.expander("📊 Model Information & Training Metrics", expanded=False):
                meta = classifier.metadata or {}
                mc1, mc2, mc3, mc4 = st.columns(4)
                with mc1:
                    st.metric("Accuracy", f"{meta.get('accuracy', 0) * 100:.1f}%")
                with mc2:
                    st.metric("Macro F1", f"{meta.get('macro_f1', 0) * 100:.1f}%")
                with mc3:
                    st.metric("Training Samples", meta.get("train_samples", "N/A"))
                with mc4:
                    st.metric("Test Samples", meta.get("test_samples", "N/A"))

                st.markdown("**Per-Class Performance:**")
                pcm = meta.get("per_class_metrics", {})
                if pcm:
                    pcm_rows = []
                    for cls_name, vals in pcm.items():
                        pcm_rows.append({
                            "Class": cls_name,
                            "Precision": f"{vals.get('precision', 0) * 100:.1f}%",
                            "Recall": f"{vals.get('recall', 0) * 100:.1f}%",
                            "F1-Score": f"{vals.get('f1-score', 0) * 100:.1f}%",
                            "Support": vals.get("support", 0),
                        })
                    st.dataframe(pd.DataFrame(pcm_rows), width="stretch", hide_index=True)

                st.caption(
                    f"Model: TF-IDF ({meta.get('vectorizer_vocab_size', '?')} n-grams) + "
                    f"Logistic Regression | Dataset: {meta.get('total_samples', '?')} curated examples"
                )

            # Classify open issues from the repository
            open_issues_list = [
                iss for iss in issues.get("issues", [])
                if iss.get("state") == "open"
            ]

            if not open_issues_list:
                st.info("No open issues available from the analyzed sample to classify.")
            else:
                # Difficulty filter
                filter_choice = st.selectbox(
                    "Filter by Predicted Difficulty",
                    ["All Issues", "Beginner-Friendly Only", "Intermediate Only", "Advanced Only"],
                )
                filter_map = {
                    "All Issues": None,
                    "Beginner-Friendly Only": "Beginner-Friendly",
                    "Intermediate Only": "Intermediate",
                    "Advanced Only": "Advanced",
                }
                selected_filter = filter_map[filter_choice]

                # Run predictions on each open issue
                predictions = []
                for iss in open_issues_list:
                    title = iss.get("title", "")
                    body = iss.get("body", "") or ""
                    labels = iss.get("labels", [])
                    pred = classifier.predict_issue(title, body, labels)
                    pred["issue"] = iss
                    predictions.append(pred)

                # Apply filter
                if selected_filter:
                    predictions = [p for p in predictions if p["difficulty"] == selected_filter]

                if not predictions:
                    st.warning(f"No issues match the filter: **{filter_choice}**.")
                else:
                    st.success(f"Classified **{len(predictions)}** open issues:")

                    # Color mapping for difficulty badges
                    diff_colors = {
                        "Beginner-Friendly": ("#059669", "#D1FAE5", "#A7F3D0"),
                        "Intermediate": ("#D97706", "#FEF3C7", "#FDE68A"),
                        "Advanced": ("#DC2626", "#FEE2E2", "#FECACA"),
                    }

                    for pred in predictions:
                        iss = pred["issue"]
                        diff = pred["difficulty"]
                        conf = pred["confidence"]
                        bg_color, badge_bg, border_c = diff_colors.get(diff, ("#7C3AED", "#F3E8FF", "#DDD6FE"))

                        # Labels HTML
                        labels_html = " ".join([
                            f"<span class='badge-pill' style='background-color:#F5F3FF; color:#6D28D9; border-color:#DDD6FE;'>🏷️ {lbl}</span>"
                            for lbl in iss.get("labels", [])
                        ])

                        # Keywords HTML
                        keywords = pred.get("top_keywords", [])
                        kw_html = ", ".join([f"<code style='background:#F3E8FF; color:#6D28D9;'>{kw}</code>" for kw in keywords]) if keywords else "<em>none detected</em>"

                        # Confidence bar width
                        conf_pct = int(conf * 100)

                        st.markdown(
                            f"""
                            <div class="saas-card" style="margin-bottom: 14px;">
                                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;">
                                    <div style="flex: 1;">
                                        <div style="font-weight: 700; font-size: 1.08rem; color: #2D1B69; margin-bottom: 6px;">
                                            #{iss.get('number', '?')}: {iss.get('title', 'Untitled')}
                                        </div>
                                        <div style="margin-bottom: 8px;">{labels_html}</div>
                                        <div style="font-size: 0.86rem; color: #4C1D95; margin-bottom: 6px; display: flex; align-items: center; gap: 8px;">
                                            <strong>ML Confidence:</strong> {conf_pct}%
                                            <span style="display: inline-block; width: 140px; height: 8px; background-color: #EDE9FE; border-radius: 9999px; overflow: hidden;">
                                                <span style="display: block; width: {conf_pct}%; height: 100%; background: linear-gradient(90deg, #A78BFA 0%, {bg_color} 100%); border-radius: 9999px;"></span>
                                            </span>
                                        </div>
                                        <div style="font-size: 0.85rem; color: #6B5B95; margin-bottom: 4px;">
                                            <strong>Driving Keywords:</strong> {kw_html}
                                        </div>
                                        <div style="font-size: 0.84rem; color: #5B21B6; background: #FAF5FF; border-left: 3px solid #8B5CF6; padding: 4px 10px; border-radius: 0 6px 6px 0; margin-top: 6px;">
                                            <strong>Signal Alignment:</strong> {pred.get('signal_alignment', '')}
                                        </div>
                                    </div>
                                    <div style="text-align: right; flex-shrink: 0; display: flex; flex-direction: column; align-items: flex-end; gap: 10px;">
                                        <span class="badge-pill" style="background-color:{badge_bg}; color:{bg_color}; border: 1px solid {border_c}; font-size: 0.85rem; padding: 6px 14px; font-weight: 700;">
                                            ● {diff}
                                        </span>
                                        <a href="{iss.get('html_url', '#')}" target="_blank" style="text-decoration: none; display: inline-block; background: linear-gradient(135deg, #7C3AED 0%, #6D28D9 100%); color: #FFFFFF; font-weight: 600; font-size: 0.85rem; padding: 8px 16px; border-radius: 10px; box-shadow: 0 4px 10px rgba(124, 58, 237, 0.25);">
                                            View Issue ↗
                                        </a>
                                    </div>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    # Fallback notice
                    fallback_count = sum(1 for p in predictions if p.get("is_fallback"))
                    if fallback_count:
                        st.caption(
                            f"ℹ️ {fallback_count} issue(s) used a rule-based fallback estimate "
                            f"because their text was too short for reliable ML classification."
                        )

    # ---------------- TAB 5: RECOMMENDATIONS ----------------
    with tab_recommendations:
        st.subheader("💡 Prioritized Improvement Roadmap")
        st.caption("Actionable recommendations generated dynamically based on deductions in your audit:")

        if res["recommendations"]:
            for rec in res["recommendations"]:
                priority = rec.get("priority", "Low")
                p_colors = {
                    "Critical": ("#DC2626", "#FEE2E2", "#FECACA"),
                    "High": ("#EA580C", "#FFEDD5", "#FED7AA"),
                    "Medium": ("#D97706", "#FEF3C7", "#FDE68A"),
                    "Low": ("#7C3AED", "#F3E8FF", "#DDD6FE"),
                }
                fg, bg, bd = p_colors.get(priority, ("#6D28D9", "#F3E8FF", "#DDD6FE"))

                st.markdown(
                    f"""
                    <div class="rec-card {priority}">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-weight: 700; font-size: 1.05rem; color: #2D1B69;">{rec['title']}</span>
                            <span class="badge-pill" style="background-color: {bg}; color: {fg}; border-color: {bd}; font-weight: 700;">
                                ● {priority} Priority • -{rec['points_lost']} pts
                            </span>
                        </div>
                        <div style="margin-top: 8px; font-size: 0.9rem; color: #4C1D95;">
                            <strong>Evidence:</strong> {rec['evidence']}
                        </div>
                        <div style="margin-top: 6px; font-size: 0.95rem; color: #2D1B69; background: #FAF5FF; padding: 8px 12px; border-radius: 8px; border-left: 3px solid #7C3AED;">
                            <strong>Action:</strong> {rec['recommendation']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.success("🎉 Outstanding! No deductions were triggered. This repository meets all health criteria.")

    # ---------------- TAB 6: METHODOLOGY & LIMITATIONS ----------------
    with tab_methodology:
        st.subheader("📖 Health Scoring Methodology & Formula")

        st.markdown(
            """
            <div class="formula-container">
                <div class="formula-title">📐 Transparent Health Score Formula (100 Points Total)</div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.95rem; color: #2D1B69; line-height: 1.6;">
                    <strong>Overall Score = Documentation (25) + Activity (25) + Issue Management (20) + Community (15) + Beginner Accessibility (15)</strong>
                </div>
                <div style="font-size: 0.85rem; color: #6B5B95; margin-top: 6px;">
                    Each component is audited dynamically using deterministic evaluation rules and verified against strict GitHub API bounds.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            | Category | Maximum Points | Core Indicators Evaluated |
            | :--- | :---: | :--- |
            | **Documentation** | **25 pts** | README existence & size, OSI-approved License, Contributing Guide, Code of Conduct, Templates |
            | **Activity & Maintenance** | **25 pts** | Days since last push, commit sample volume, tagged releases frequency |
            | **Issue Management** | **20 pts** | Issue closure ratio, categorization label hygiene, median open issue age (*Strictly excludes PRs*) |
            | **Community Participation** | **15 pts** | Contributor diversity, fork engagement, star awareness (*Stars alone do not denote quality*) |
            | **Beginner Accessibility** | **15 pts** | Tagged beginner issues (`good first issue`), onboarding guidelines, open task availability |

            ---

            #### 🔍 Missing Data & Measurement Limitations Policy:
            1. **Strict Issue Filtering:** GitHub's `/repos/{owner}/{repo}/issues` REST API endpoint returns both issues and pull requests together. Our implementation explicitly inspects each item and ignores records containing the `'pull_request'` key.
            2. **Separate Open & Closed Issue Sampling:** Open and closed issues are queried via separate API requests to prevent recently-updated items from skewing the sample. Percentages are calculated strictly from the retrieved sample and clearly labeled as a sample breakdown, never as the lifetime repository ratio.
            3. **API Pagination & Rate Limits:** To maintain responsiveness and comply with GitHub's rate limits (60 unauth / 5,000 auth per hour), commit and issue metrics are computed on sample batches. Contributor and issue scale contexts estimate total pages via the HTTP `Link` header where available.
            4. **Documentation Assessment:** We verify file existence, naming, and byte size. We do not claim to evaluate prose eloquence or grammatical perfection.
            5. **Stars vs. Quality:** Star count is treated strictly as an indicator of community visibility, not as proof of software correctness or security.
            """
        )

    # ---------------- TAB 7: STUDENT FEEDBACK ----------------
    with tab_feedback:
        st.subheader("💬 Student & Evaluator Feedback Form")
        st.caption(
            "Feedback submitted here is retained in the Streamlit session state and appended to a local `feedback_store.json` on disk."
        )

        with st.form("feedback_form"):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                name_input = st.text_input("Your Name / Evaluator Name", placeholder="e.g., Alex Johnson")
                role_input = st.selectbox("Role", ["Student", "Professor / Evaluator", "Open-Source Contributor", "Developer"])
            with col_f2:
                rating = st.slider("Project Usability & Clarity Rating (1 = Poor, 5 = Excellent)", 1, 5, 5)
                useful_feature = st.selectbox(
                    "Most Valuable Feature",
                    [
                        "Transparent Health Score Formula",
                        "Strict PR vs Issue Filtering",
                        "Beginner Issue Discovery",
                        "Prioritized Actionable Roadmap",
                        "Interactive Plotly Charts",
                    ],
                )

            comment_input = st.text_area("Observations, Feedback or Suggestions", placeholder="Write your comments here...")
            submitted = st.form_submit_button("Submit Feedback")

            if submitted:
                entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "name": name_input.strip() or "Anonymous",
                    "role": role_input,
                    "rating": rating,
                    "favorite_feature": useful_feature,
                    "comment": comment_input.strip(),
                    "repo_evaluated": summary["full_name"],
                }
                save_feedback_entry(entry)
                st.success("✅ Thank you! Your feedback has been recorded.")

        # Show existing feedback entries
        feedbacks = load_feedback_store()
        if feedbacks:
            st.markdown("##### 📝 Recorded Feedback")
            for fb in reversed(feedbacks[-5:]):
                st.markdown(
                    f"""
                    <div class="saas-card" style="margin-bottom: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <strong style="color: #2D1B69; font-size: 1.02rem;">{fb.get('name')}</strong>
                            <span class="badge-pill" style="background:#F3E8FF; color:#6D28D9; border-color:#DDD6FE;">{fb.get('role')}</span>
                        </div>
                        <div style="font-size: 0.95rem; margin-top: 4px;">{'⭐' * fb.get('rating', 5)}</div>
                        <div style="font-size:0.85rem; color:#6B5B95; margin-top: 4px;">
                            Evaluated <code style="background:#F3E8FF; color:#6D28D9;">{fb.get('repo_evaluated', 'N/A')}</code> • Favorite: <em>{fb.get('favorite_feature')}</em>
                        </div>
                        <p style="margin-top:8px; font-size:0.95rem; color:#372554; background:#FAF5FF; padding: 10px 14px; border-radius: 8px; border-left: 3px solid #8B5CF6;">
                            {fb.get('comment') or 'No comment provided.'}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
else:
    # Initial landing guide
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #F5F3FF 0%, #EDE9FE 100%); border: 1.5px solid #DDD6FE; border-radius: 16px; padding: 18px 24px; margin-bottom: 24px; display: flex; align-items: center; gap: 14px;">
            <div style="font-size: 1.8rem;">👆</div>
            <div style="color: #4C1D95; font-size: 1.02rem; font-weight: 600;">
                Enter a GitHub repository URL or choose a preset in the sidebar, then click <strong>Analyze Repository</strong> to begin the audit.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.markdown(
            """
            <div class="saas-card" style="height: 100%;">
                <div style="width: 42px; height: 42px; border-radius: 12px; background: #F3E8FF; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; margin-bottom: 12px;">
                    🎯
                </div>
                <h3 style="margin: 0 0 8px 0; font-size: 1.2rem; color: #2D1B69;">Real GitHub API Analysis</h3>
                <p style="color: #6B5B95; font-size: 0.92rem; line-height: 1.6; margin: 0;">
                    Connects directly to the live GitHub REST API. Inspects commit cadence, repository metadata, documentation volume, and strictly excludes Pull Requests from issue calculations.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_info2:
        st.markdown(
            """
            <div class="saas-card" style="height: 100%;">
                <div style="width: 42px; height: 42px; border-radius: 12px; background: #F3E8FF; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; margin-bottom: 12px;">
                    💯
                </div>
                <h3 style="margin: 0 0 8px 0; font-size: 1.2rem; color: #2D1B69;">100-Point Formula</h3>
                <p style="color: #6B5B95; font-size: 0.92rem; line-height: 1.6; margin: 0;">
                    Completely transparent scoring across Documentation (25), Activity (25), Issue Management (20), Community Participation (15), and Beginner Accessibility (15).
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_info3:
        st.markdown(
            """
            <div class="saas-card" style="height: 100%;">
                <div style="width: 42px; height: 42px; border-radius: 12px; background: #F3E8FF; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; margin-bottom: 12px;">
                    🌱
                </div>
                <h3 style="margin: 0 0 8px 0; font-size: 1.2rem; color: #2D1B69;">AI/ML Starter Gateway</h3>
                <p style="color: #6B5B95; font-size: 0.92rem; line-height: 1.6; margin: 0;">
                    Identifies labeled starter tasks and runs a TF-IDF + Logistic Regression NLP classifier on open issue text to discover accessible contribution opportunities.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
