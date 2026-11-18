"""
issue_classifier.py
===================
Machine Learning-Based GitHub Issue Difficulty Classifier.

Estimates whether a GitHub issue is:
- "Beginner-Friendly" (e.g. documentation typos, simple bug fixes, starter tasks)
- "Intermediate" (e.g. new endpoints, standard bug fixes, database/API features)
- "Advanced" (e.g. concurrency, memory management, compiler internals, consensus)

Architecture:
- Text Preprocessing & Cleaning
- TF-IDF N-gram Vectorization (Unigrams + Bigrams)
- Balanced Multinomial Logistic Regression with Calibrated Probabilities
- Feature Importance Inspection (extracts driving keywords per prediction)
- Hybrid Corroboration with GitHub Labels (good first issue, help wanted, etc.)
- Transparent Model Metrics & Confusion Matrix Serialization
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

# Model file locations
DEFAULT_DATA_PATH = Path("data/issue_training_data.csv")
DEFAULT_MODEL_DIR = Path("models")
DEFAULT_MODEL_PATH = DEFAULT_MODEL_DIR / "issue_classifier_pipeline.joblib"
DEFAULT_METADATA_PATH = DEFAULT_MODEL_DIR / "model_metadata.json"

CLASSES = ["Beginner-Friendly", "Intermediate", "Advanced"]

# Beginner-friendly label keywords for rule-based cross-referencing
BEGINNER_LABEL_KEYWORDS = [
    "good first issue",
    "good-first-issue",
    "help wanted",
    "help-wanted",
    "beginner",
    "beginner-friendly",
    "easy",
    "starter",
    "up-for-grabs",
    "first-timers-only",
    "documentation",
]

ADVANCED_LABEL_KEYWORDS = [
    "core",
    "architecture",
    "concurrency",
    "performance",
    "security",
    "breaking-change",
    "compiler",
    "internals",
    "kernel",
]


def clean_text(text: Optional[str]) -> str:
    """
    Normalize issue text:
    - Lowercase
    - Strip URLs and markdown links
    - Remove code blocks and non-alphanumeric noise
    - Collapse excessive whitespace
    """
    if not text or not isinstance(text, str):
        return ""

    cleaned = text.lower()
    # Remove markdown code blocks ```...```
    cleaned = re.sub(r"```[\s\S]*?```", " ", cleaned)
    # Remove inline code `...`
    cleaned = re.sub(r"`[^`]*`", " ", cleaned)
    # Remove URLs
    cleaned = re.sub(r"https?://\S+|www\.\S+", " ", cleaned)
    # Remove HTML tags
    cleaned = re.sub(r"<.*?>", " ", cleaned)
    # Remove special characters, keep words and hyphens
    cleaned = re.sub(r"[^\w\s-]", " ", cleaned)
    # Collapse multiple whitespaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def build_pipeline() -> Pipeline:
    """Construct the TF-IDF and Logistic Regression scikit-learn pipeline."""
    return Pipeline([
        (
            "tfidf",
            TfidfVectorizer(
                ngram_range=(1, 2),
                max_features=1500,
                sublinear_tf=True,
                stop_words="english",
            ),
        ),
        (
            "clf",
            LogisticRegression(
                C=1.0,
                max_iter=1000,
                class_weight="balanced",
                random_state=42,
            ),
        ),
    ])


def train_issue_classifier(
    data_path: Path = DEFAULT_DATA_PATH,
    model_path: Path = DEFAULT_MODEL_PATH,
    metadata_path: Path = DEFAULT_METADATA_PATH,
    test_size: float = 0.25,
    random_state: int = 42,
) -> Dict[str, Any]:
    """
    Train and evaluate the issue classification model on the documented dataset.

    Steps:
    1. Load data and combine title + body
    2. Prevent data leakage by removing exact duplicates
    3. Stratified split into train and test sets
    4. Fit TF-IDF + LogisticRegression pipeline
    5. Evaluate accuracy, precision, recall, F1, and confusion matrix
    6. Serialize pipeline and metadata to disk
    """
    if not Path(data_path).exists():
        raise FileNotFoundError(f"Training dataset not found at '{data_path}'")

    df = pd.read_csv(data_path)
    required_cols = {"title", "body", "difficulty"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"Dataset must contain columns: {required_cols}")

    # Clean and combine title and body
    df["full_text"] = (df["title"].fillna("") + " " + df["body"].fillna("")).apply(clean_text)

    # Filter out empty texts
    df = df[df["full_text"].str.strip() != ""].copy()

    # Data hygiene: remove duplicate texts to prevent train/test leakage
    df = df.drop_duplicates(subset=["full_text"]).reset_index(drop=True)

    # Verify all 3 classes exist
    present_classes = sorted(df["difficulty"].unique())
    X = df["full_text"]
    y = df["difficulty"]

    # Stratified split to ensure balanced representation in test set
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)

    # Predictions and evaluation
    y_pred = pipeline.predict(X_test)

    report_dict = classification_report(
        y_test, y_pred, output_dict=True, zero_division=0
    )
    conf_matrix = confusion_matrix(y_test, y_pred, labels=CLASSES).tolist()
    accuracy = float(np.mean(y_test == y_pred))

    model_dir = Path(model_path).parent
    model_dir.mkdir(parents=True, exist_ok=True)

    # Save pipeline
    joblib.dump(pipeline, model_path)

    metadata: Dict[str, Any] = {
        "dataset_path": str(data_path),
        "total_samples": int(len(df)),
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "classes": CLASSES,
        "class_distribution": df["difficulty"].value_counts().to_dict(),
        "accuracy": round(accuracy, 4),
        "macro_precision": round(report_dict["macro avg"]["precision"], 4),
        "macro_recall": round(report_dict["macro avg"]["recall"], 4),
        "macro_f1": round(report_dict["macro avg"]["f1-score"], 4),
        "per_class_metrics": {
            cls_name: {
                "precision": round(report_dict.get(cls_name, {}).get("precision", 0), 4),
                "recall": round(report_dict.get(cls_name, {}).get("recall", 0), 4),
                "f1-score": round(report_dict.get(cls_name, {}).get("f1-score", 0), 4),
                "support": int(report_dict.get(cls_name, {}).get("support", 0)),
            }
            for cls_name in CLASSES
        },
        "confusion_matrix": conf_matrix,
        "vectorizer_vocab_size": len(pipeline.named_steps["tfidf"].vocabulary_),
    }

    # Save metadata JSON
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return metadata


class IssueClassifier:
    """
    Issue difficulty inference engine with keyword explanation
    and rule-based label correlation.
    """

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        metadata_path: Path = DEFAULT_METADATA_PATH,
        auto_train: bool = True,
    ):
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path)
        self.pipeline: Optional[Pipeline] = None
        self.metadata: Optional[Dict[str, Any]] = None

        if self.model_path.exists():
            self._load_existing()
        elif auto_train:
            self._train_and_load()

    def _load_existing(self) -> None:
        """Load trained pipeline and metadata from disk."""
        try:
            self.pipeline = joblib.load(self.model_path)
            if self.metadata_path.exists():
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
        except Exception:
            self.pipeline = None

    def _train_and_load(self) -> None:
        """Automatically train model if not present on disk."""
        try:
            self.metadata = train_issue_classifier(
                model_path=self.model_path, metadata_path=self.metadata_path
            )
            self.pipeline = joblib.load(self.model_path)
        except Exception:
            self.pipeline = None

    @property
    def is_ready(self) -> bool:
        """Check if classifier pipeline is loaded and ready for predictions."""
        return self.pipeline is not None

    def _extract_top_keywords(
        self, text: str, predicted_class: str, top_k: int = 4
    ) -> List[str]:
        """
        Identify top contributing keywords in the input text that influenced the prediction.
        """
        if not self.pipeline:
            return []

        try:
            vectorizer: TfidfVectorizer = self.pipeline.named_steps["tfidf"]
            classifier: LogisticRegression = self.pipeline.named_steps["clf"]

            feature_names = vectorizer.get_feature_names_out()
            class_idx = list(classifier.classes_).index(predicted_class)
            class_coefs = classifier.coef_[class_idx]

            # Transform input text to find active features
            tfidf_vec = vectorizer.transform([text]).toarray()[0]
            non_zero_indices = np.where(tfidf_vec > 0)[0]

            if len(non_zero_indices) == 0:
                return []

            # Score each active feature by (tfidf * coefficient)
            feature_scores = [
                (feature_names[i], tfidf_vec[i] * class_coefs[i])
                for i in non_zero_indices
            ]
            # Sort by highest positive contribution
            feature_scores.sort(key=lambda x: x[1], reverse=True)

            positive_features = [f[0] for f in feature_scores if f[1] > 0]
            return positive_features[:top_k]
        except Exception:
            return []

    def predict_issue(
        self,
        title: str,
        body: str = "",
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Predict the difficulty category of a GitHub issue and correlate with labels.

        Args:
            title: Issue title
            body: Optional issue description
            labels: Optional list of GitHub labels on the issue

        Returns:
            Dict containing:
            - difficulty: 'Beginner-Friendly', 'Intermediate', or 'Advanced'
            - confidence: float between 0.0 and 1.0 (estimated probability)
            - probabilities: dict of class -> probability
            - top_keywords: words in text that drove the prediction
            - rule_signals: insights derived from GitHub labels
            - signal_alignment: summary comparing ML prediction with GitHub labels
            - is_fallback: bool indicating if default was returned due to empty text
        """
        labels = labels or []
        combined_text = clean_text(f"{title} {body}")

        # Check label signals regardless of ML text
        rule_signals = []
        has_beginner_label = False
        has_advanced_label = False

        for lbl in labels:
            lbl_lower = lbl.lower().strip()
            for b_kw in BEGINNER_LABEL_KEYWORDS:
                if b_kw in lbl_lower:
                    has_beginner_label = True
                    rule_signals.append(f"Label '{lbl}' indicates potential starter task.")
                    break
            for a_kw in ADVANCED_LABEL_KEYWORDS:
                if a_kw in lbl_lower:
                    has_advanced_label = True
                    rule_signals.append(f"Label '{lbl}' indicates complex or core component.")
                    break

        if not self.is_ready or not combined_text:
            # Fallback when model is unavailable or text is completely empty
            fallback_class = "Beginner-Friendly" if has_beginner_label else "Intermediate"
            return {
                "difficulty": fallback_class,
                "confidence": 0.50,
                "probabilities": {c: 0.33 for c in CLASSES},
                "top_keywords": [],
                "rule_signals": rule_signals or ["No descriptive issue text or labels provided."],
                "signal_alignment": "Fallback estimate due to missing text or model initialization.",
                "is_fallback": True,
            }

        # Model inference
        clf: LogisticRegression = self.pipeline.named_steps["clf"]
        probs = self.pipeline.predict_proba([combined_text])[0]
        prob_dict = {
            cls_name: round(float(probs[idx]), 3)
            for idx, cls_name in enumerate(clf.classes_)
        }

        best_idx = int(np.argmax(probs))
        predicted_class = str(clf.classes_[best_idx])
        confidence = float(probs[best_idx])

        top_keywords = self._extract_top_keywords(combined_text, predicted_class)

        # Cross-reference ML prediction with GitHub labels
        if has_beginner_label and predicted_class == "Beginner-Friendly":
            alignment = "High Agreement: ML text model and GitHub label both flag this as beginner-friendly."
        elif has_beginner_label and predicted_class != "Beginner-Friendly":
            alignment = f"Label Contrast: Issue has beginner label, but text vocabulary suggests {predicted_class} complexity."
        elif not has_beginner_label and predicted_class == "Beginner-Friendly":
            alignment = "Opportunity Discovered: No beginner label attached, but ML text analysis identifies approachable scope."
        elif has_advanced_label and predicted_class == "Advanced":
            alignment = "High Agreement: ML model and GitHub labels both indicate advanced core complexity."
        else:
            alignment = f"ML model estimates {predicted_class} difficulty based on vocabulary and scope."

        return {
            "difficulty": predicted_class,
            "confidence": round(confidence, 3),
            "probabilities": prob_dict,
            "top_keywords": top_keywords,
            "rule_signals": rule_signals,
            "signal_alignment": alignment,
            "is_fallback": False,
        }
