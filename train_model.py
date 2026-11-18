"""
train_model.py
==============
CLI script to train and evaluate the ML Issue Difficulty Classifier.
"""

import sys
from pathlib import Path
from issue_classifier import IssueClassifier, train_issue_classifier, CLASSES

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main():
    print("=========================================================")
    print("🤖 Training ML-Based GitHub Issue Difficulty Classifier")
    print("=========================================================\n")

    data_path = Path("data/issue_training_data.csv")
    model_path = Path("models/issue_classifier_pipeline.joblib")
    meta_path = Path("models/model_metadata.json")

    print(f"Loading dataset from: {data_path}")
    metrics = train_issue_classifier(
        data_path=data_path,
        model_path=model_path,
        metadata_path=meta_path,
        test_size=0.25,
        random_state=42,
    )

    print("\n--- Training & Dataset Summary ---")
    print(f"Total Unique Samples: {metrics['total_samples']}")
    print(f"Training Set Size:   {metrics['train_samples']}")
    print(f"Test Set Size:       {metrics['test_samples']}")
    print(f"TF-IDF Vocabulary:   {metrics['vectorizer_vocab_size']} n-grams")
    print(f"Class Distribution:  {metrics['class_distribution']}")

    print("\n--- Test Set Evaluation Results ---")
    print(f"Overall Accuracy: {metrics['accuracy'] * 100:.2f}%")
    print(f"Macro Precision:  {metrics['macro_precision'] * 100:.2f}%")
    print(f"Macro Recall:     {metrics['macro_recall'] * 100:.2f}%")
    print(f"Macro F1-Score:   {metrics['macro_f1'] * 100:.2f}%")

    print("\n--- Per-Class Performance ---")
    print(f"{'Class':<22} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10} | {'Support':<8}")
    print("-" * 72)
    for cls_name, vals in metrics["per_class_metrics"].items():
        print(
            f"{cls_name:<22} | "
            f"{vals['precision'] * 100:>8.1f}% | "
            f"{vals['recall'] * 100:>8.1f}% | "
            f"{vals['f1-score'] * 100:>8.1f}% | "
            f"{vals['support']:>8}"
        )

    print("\n--- Confusion Matrix ---")
    cm = metrics["confusion_matrix"]
    print(f"{'Actual \\ Predicted':<22} | " + " | ".join(f"{c[:10]:<10}" for c in CLASSES))
    print("-" * 60)
    for i, actual_class in enumerate(CLASSES):
        row_str = " | ".join(f"{cm[i][j]:<10}" for j in range(len(CLASSES)))
        print(f"{actual_class:<22} | {row_str}")

    print("\n=========================================================")
    print("🔍 Testing Live Predictions on Example Issues")
    print("=========================================================\n")

    classifier = IssueClassifier(model_path=model_path, metadata_path=meta_path)

    examples = [
        {
            "title": "Fix typo in getting started README code example",
            "body": "In the installation section, 'import flask' is misspelled as 'impor flask'.",
            "labels": ["documentation", "good first issue"],
        },
        {
            "title": "Add pagination support and offset query params to search API",
            "body": "Users are requesting limit and offset query parameters on GET /api/v2/items to paginate results.",
            "labels": ["enhancement"],
        },
        {
            "title": "Resolve threadpool deadlock and memory leak in asyncio connection pool",
            "body": "Under high load, worker threads deadlock waiting on acquired mutexes causing orphaned socket descriptors.",
            "labels": ["core", "concurrency"],
        },
    ]

    for idx, ex in enumerate(examples, 1):
        res = classifier.predict_issue(ex["title"], ex["body"], ex["labels"])
        print(f"Example #{idx}:")
        print(f"  Title:      {ex['title']}")
        print(f"  Labels:     {ex['labels']}")
        print(f"  Predicted:  {res['difficulty']} (Confidence: {res['confidence'] * 100:.1f}%)")
        print(f"  Keywords:   {res['top_keywords']}")
        print(f"  Alignment:  {res['signal_alignment']}")
        print(f"  Probabilities: {res['probabilities']}\n")

    print(f"✅ Model saved to: {model_path}")
    print(f"✅ Evaluation metadata saved to: {meta_path}")


if __name__ == "__main__":
    main()
