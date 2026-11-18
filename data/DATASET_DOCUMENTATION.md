# 📊 Dataset Documentation: GitHub Issue Difficulty Classification

## 1. Dataset Origin & Purpose
This dataset (`data/issue_training_data.csv`) is curated for the **ML-Based Beginner-Friendly GitHub Issue Classifier** component of the **GitHub Repository Health & Beginner Contribution Assistant**.

In open source, issue labels like `good first issue` are applied inconsistently or often omitted entirely. The purpose of this model is to analyze issue text (titles and descriptions) to provide an automated, explainable estimate of task difficulty for newcomers.

## 2. Dataset Schema

Each row contains the following attributes:
- `title` *(string)*: The issue title as posted on GitHub.
- `body` *(string)*: Detailed issue description, error logs, or problem context.
- `difficulty` *(string, Target Class)*:
  - `Beginner-Friendly`: Approachable tasks for first-time contributors.
  - `Intermediate`: Features, API endpoints, or bug fixes requiring familiarity with the codebase.
  - `Advanced`: Concurrency, distributed systems, compiler internals, low-level memory/security.
- `category` *(string)*: Functional area (e.g., `Documentation`, `Testing`, `Backend`, `Concurrency`, `Distributed Systems`, `DevOps`).
- `rationale` *(string)*: Explains why this specific difficulty label was assigned.

## 3. Label Assignment Criteria

| Difficulty Class | Characteristics & Keywords | Example Tasks |
| :--- | :--- | :--- |
| **Beginner-Friendly** | Documentation typos, docstrings, simple test assertions, minor formatting, adding CLI argument help, renaming parameters, fixing broken markdown links. | "Fix typo in README installation guide", "Add docstring to calculate_average function" |
| **Intermediate** | Implementing REST endpoints, adding database queries/migrations, caching, input validation with business logic, writing integration tests, pagination, refactoring blueprints. | "Add pagination support to user list endpoint", "Implement rate limiting middleware", "Optimize database query" |
| **Advanced** | Memory corruption, race conditions, distributed consensus (Raft/Paxos), compiler JIT/LLVM optimization passes, zero-copy socket parsing, cryptographic proofs, eBPF kernels. | "Resolve race condition in asyncio pool", "Design distributed lock manager with Raft", "Implement zero-knowledge SNARK proof" |

## 4. Methodology & Data Hygiene
- **Duplicate Prevention:** The training pipeline deduplicates issues based on normalized text before splitting to avoid data leakage between training and testing splits.
- **Stratified Splitting:** Train/test split uses stratified sampling (`test_size=0.25`, `random_state=42`) ensuring each class is represented proportionally.
- **Honest Limitations:** This dataset serves as a curated demonstration prototype. It is small and transparent. In production environments, classification models should be trained on tens of thousands of issues with maintainer time-to-close metrics and code change size telemetry.
