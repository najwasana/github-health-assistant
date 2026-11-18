"""
tests/test_issue_classifier.py
==============================
Automated tests for the ML Issue Difficulty Classifier.
"""

from pathlib import Path

import pytest

from issue_classifier import (
    CLASSES,
    IssueClassifier,
    build_pipeline,
    clean_text,
    train_issue_classifier,
)

# Paths relative to project root (tests run from project root)
DATA_PATH = Path("data/issue_training_data.csv")
MODEL_PATH = Path("models/issue_classifier_pipeline.joblib")
META_PATH = Path("models/model_metadata.json")


# ----------------------------------------------------------------
# Tests for clean_text()
# ----------------------------------------------------------------

class TestCleanText:
    """Tests for the text preprocessing function."""

    def test_none_input(self):
        assert clean_text(None) == ""

    def test_empty_string(self):
        assert clean_text("") == ""

    def test_non_string_input(self):
        assert clean_text(12345) == ""
        assert clean_text([]) == ""

    def test_basic_lowering(self):
        result = clean_text("Fix TYPO in README")
        assert result == "fix typo in readme"

    def test_url_removal(self):
        result = clean_text("See https://github.com/example for details")
        assert "https" not in result
        assert "github.com" not in result

    def test_code_block_removal(self):
        text = "Issue with ```python\nprint('hello')\n``` code block"
        result = clean_text(text)
        assert "print" not in result

    def test_inline_code_removal(self):
        result = clean_text("The function `get_data()` crashes")
        assert "get_data" not in result

    def test_html_tag_removal(self):
        result = clean_text("Fix the <b>bold</b> text issue")
        assert "<b>" not in result

    def test_whitespace_collapsing(self):
        result = clean_text("too   many     spaces   here")
        assert "  " not in result

    def test_preserves_hyphens(self):
        result = clean_text("good-first-issue label")
        assert "good-first-issue" in result


# ----------------------------------------------------------------
# Tests for build_pipeline()
# ----------------------------------------------------------------

class TestBuildPipeline:
    """Tests for the scikit-learn pipeline constructor."""

    def test_pipeline_has_two_steps(self):
        pipe = build_pipeline()
        assert len(pipe.steps) == 2

    def test_pipeline_step_names(self):
        pipe = build_pipeline()
        step_names = [name for name, _ in pipe.steps]
        assert step_names == ["tfidf", "clf"]


# ----------------------------------------------------------------
# Tests for train_issue_classifier()
# ----------------------------------------------------------------

class TestTrainIssueClassifier:
    """Tests for model training (uses real dataset file)."""

    @pytest.fixture(autouse=True)
    def _check_dataset(self):
        if not DATA_PATH.exists():
            pytest.skip("Training dataset not available")

    def test_training_returns_metrics_dict(self, tmp_path):
        model_p = tmp_path / "test_pipeline.joblib"
        meta_p = tmp_path / "test_metadata.json"
        metrics = train_issue_classifier(
            data_path=DATA_PATH,
            model_path=model_p,
            metadata_path=meta_p,
            test_size=0.25,
            random_state=42,
        )
        assert isinstance(metrics, dict)
        assert model_p.exists()
        assert meta_p.exists()

    def test_metrics_keys_present(self, tmp_path):
        model_p = tmp_path / "test_pipeline.joblib"
        meta_p = tmp_path / "test_metadata.json"
        metrics = train_issue_classifier(
            data_path=DATA_PATH,
            model_path=model_p,
            metadata_path=meta_p,
        )
        required_keys = [
            "accuracy", "macro_precision", "macro_recall", "macro_f1",
            "total_samples", "train_samples", "test_samples",
            "per_class_metrics", "confusion_matrix", "vectorizer_vocab_size",
        ]
        for key in required_keys:
            assert key in metrics, f"Missing metric key: {key}"

    def test_accuracy_is_reasonable(self, tmp_path):
        model_p = tmp_path / "test_pipeline.joblib"
        meta_p = tmp_path / "test_metadata.json"
        metrics = train_issue_classifier(
            data_path=DATA_PATH,
            model_path=model_p,
            metadata_path=meta_p,
        )
        # With 85 curated samples, accuracy should be above random (33%)
        assert metrics["accuracy"] > 0.5, f"Accuracy too low: {metrics['accuracy']}"

    def test_all_classes_in_per_class_metrics(self, tmp_path):
        model_p = tmp_path / "test_pipeline.joblib"
        meta_p = tmp_path / "test_metadata.json"
        metrics = train_issue_classifier(
            data_path=DATA_PATH,
            model_path=model_p,
            metadata_path=meta_p,
        )
        for cls in CLASSES:
            assert cls in metrics["per_class_metrics"]

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            train_issue_classifier(data_path=Path("nonexistent.csv"))


# ----------------------------------------------------------------
# Tests for IssueClassifier predictions
# ----------------------------------------------------------------

class TestIssueClassifierPredict:
    """Tests for the IssueClassifier inference class."""

    @pytest.fixture(autouse=True)
    def _check_model(self):
        if not MODEL_PATH.exists():
            pytest.skip("Trained model not available")

    @pytest.fixture
    def classifier(self):
        return IssueClassifier(
            model_path=MODEL_PATH,
            metadata_path=META_PATH,
            auto_train=False,
        )

    def test_classifier_is_ready(self, classifier):
        assert classifier.is_ready

    def test_prediction_returns_expected_keys(self, classifier):
        result = classifier.predict_issue(
            title="Fix typo in README",
            body="There is a spelling mistake in the introduction."
        )
        expected_keys = [
            "difficulty", "confidence", "probabilities",
            "top_keywords", "rule_signals", "signal_alignment", "is_fallback",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_prediction_difficulty_is_valid_class(self, classifier):
        result = classifier.predict_issue(
            title="Add pagination to REST API",
            body="Users need limit and offset parameters."
        )
        assert result["difficulty"] in CLASSES

    def test_confidence_in_range(self, classifier):
        result = classifier.predict_issue(
            title="Resolve memory leak in connection pool",
            body="Worker threads cause orphaned socket descriptors."
        )
        assert 0.0 <= result["confidence"] <= 1.0

    def test_probabilities_sum_roughly_to_one(self, classifier):
        result = classifier.predict_issue(
            title="Update dependencies",
            body="Bump numpy from 1.21 to 1.24."
        )
        total = sum(result["probabilities"].values())
        assert abs(total - 1.0) < 0.01, f"Probabilities sum to {total}, expected ~1.0"

    def test_is_not_fallback_with_text(self, classifier):
        result = classifier.predict_issue(
            title="Fix typo in documentation",
            body="Small change needed."
        )
        assert result["is_fallback"] is False

    def test_beginner_label_produces_rule_signal(self, classifier):
        result = classifier.predict_issue(
            title="Update logo",
            body="Change the logo image.",
            labels=["good first issue"],
        )
        assert len(result["rule_signals"]) > 0

    def test_beginner_friendly_prediction_on_easy_issue(self, classifier):
        result = classifier.predict_issue(
            title="Fix typo in getting started README code example",
            body="In the installation section, 'import flask' is misspelled.",
            labels=["documentation", "good first issue"],
        )
        assert result["difficulty"] == "Beginner-Friendly"

    def test_advanced_prediction_on_complex_issue(self, classifier):
        result = classifier.predict_issue(
            title="Resolve threadpool deadlock and memory leak in asyncio connection pool",
            body="Under high load, worker threads deadlock waiting on acquired mutexes.",
            labels=["core", "concurrency"],
        )
        assert result["difficulty"] != "Beginner-Friendly"

    def test_top_keywords_are_strings(self, classifier):
        result = classifier.predict_issue(
            title="Add error handling for network timeouts",
            body="When the server is unreachable, the client should retry."
        )
        for kw in result["top_keywords"]:
            assert isinstance(kw, str)


# ----------------------------------------------------------------
# Tests for fallback behavior
# ----------------------------------------------------------------

class TestIssueClassifierFallback:
    """Tests for graceful fallback when model is missing or text is empty."""

    def test_fallback_with_missing_model(self, tmp_path):
        clf = IssueClassifier(
            model_path=tmp_path / "nonexistent.joblib",
            metadata_path=tmp_path / "nonexistent.json",
            auto_train=False,
        )
        assert not clf.is_ready
        result = clf.predict_issue("Some title", "Some body")
        assert result["is_fallback"] is True
        assert result["difficulty"] in CLASSES

    def test_fallback_with_empty_title(self):
        if not MODEL_PATH.exists():
            pytest.skip("Trained model not available")
        clf = IssueClassifier(
            model_path=MODEL_PATH,
            metadata_path=META_PATH,
            auto_train=False,
        )
        result = clf.predict_issue("", "")
        assert result["is_fallback"] is True

    def test_fallback_defaults_to_beginner_with_label(self, tmp_path):
        clf = IssueClassifier(
            model_path=tmp_path / "nonexistent.joblib",
            metadata_path=tmp_path / "nonexistent.json",
            auto_train=False,
        )
        result = clf.predict_issue("", "", labels=["good first issue"])
        assert result["difficulty"] == "Beginner-Friendly"
        assert result["is_fallback"] is True

    def test_fallback_defaults_to_intermediate_without_label(self, tmp_path):
        clf = IssueClassifier(
            model_path=tmp_path / "nonexistent.joblib",
            metadata_path=tmp_path / "nonexistent.json",
            auto_train=False,
        )
        result = clf.predict_issue("Some issue", "Some body")
        assert result["difficulty"] == "Intermediate"
        assert result["is_fallback"] is True
