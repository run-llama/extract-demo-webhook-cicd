"""Compare extraction results against ground truth and compute accuracy."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from tabulate import tabulate

from schema import InvoiceSchema


def normalize(value):
    """Normalize a string value for comparison: lowercase and strip whitespace."""
    if value is None:
        return None
    return str(value).strip().lower()


def compare_fields(ground_truth, extracted, fields):
    """Compare fields between ground truth and extracted data.

    Returns a dict with field-level comparison results.
    """
    results = {}
    for field in fields:
        gt_value = ground_truth.get(field)
        ex_value = extracted.get(field)

        if gt_value is None:
            # Extra field in extraction — ignore
            results[field] = {
                "expected": gt_value,
                "extracted": ex_value,
                "correct": True,  # Not counted
                "status": "extra",
            }
        elif ex_value is None:
            # Missing extraction
            results[field] = {
                "expected": gt_value,
                "extracted": ex_value,
                "correct": False,
                "status": "missing",
            }
        elif normalize(gt_value) == normalize(ex_value):
            results[field] = {
                "expected": gt_value,
                "extracted": ex_value,
                "correct": True,
                "status": "correct",
            }
        else:
            results[field] = {
                "expected": gt_value,
                "extracted": ex_value,
                "correct": False,
                "status": "wrong",
            }

    return results


def main():
    """Run evaluation comparing extraction results against ground truth."""
    parser = argparse.ArgumentParser(description="Evaluate extraction accuracy")
    parser.add_argument(
        "--output-markdown",
        action="store_true",
        help="Write results as markdown to results/pr_comment.md",
    )
    args = parser.parse_args()

    gt_path = Path("ground_truth.json")
    extraction_path = Path("results/extraction_output.json")
    baseline_path = Path("metrics.json")

    if not gt_path.exists():
        print(f"Error: {gt_path} not found. Run 'python extract.py --init-ground-truth' first.")
        sys.exit(1)

    if not extraction_path.exists():
        print(f"Error: {extraction_path} not found. Run 'python extract.py' first.")
        sys.exit(1)

    try:
        with open(gt_path, encoding="utf-8") as f:
            ground_truth = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: {gt_path} contains invalid JSON: {e}")
        sys.exit(1)

    try:
        with open(extraction_path, encoding="utf-8") as f:
            extracted = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: {extraction_path} contains invalid JSON: {e}")
        sys.exit(1)

    # Load baseline if exists
    baseline = None
    if baseline_path.exists():
        try:
            with open(baseline_path, encoding="utf-8") as f:
                baseline = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: {baseline_path} contains invalid JSON, ignoring baseline.")
            baseline = None

    # Get fields from schema
    fields = list(InvoiceSchema.model_fields.keys())

    # Compare each file
    total_fields = 0
    correct_fields = 0
    missing_fields = 0
    wrong_fields = 0
    per_file = {}

    for filename in sorted(ground_truth.keys()):
        gt_data = ground_truth[filename]
        ex_data = extracted.get(filename, {})
        if ex_data is None:
            ex_data = {}

        field_results = compare_fields(gt_data, ex_data, fields)

        file_total = 0
        file_correct = 0
        for field, result in field_results.items():
            if result["status"] == "extra":
                continue
            file_total += 1
            total_fields += 1
            if result["correct"]:
                file_correct += 1
                correct_fields += 1
            elif result["status"] == "missing":
                missing_fields += 1
            else:
                wrong_fields += 1

        file_accuracy = file_correct / file_total if file_total > 0 else 0.0

        per_file[filename] = {
            "accuracy": file_accuracy,
            "fields": {
                field: {
                    "expected": result["expected"],
                    "extracted": result["extracted"],
                    "correct": result["correct"],
                }
                for field, result in field_results.items()
            },
        }

    overall_accuracy = correct_fields / total_fields if total_fields > 0 else 0.0

    # Build metrics
    metrics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_accuracy": overall_accuracy,
        "per_file": per_file,
        "total_fields": total_fields,
        "correct_fields": correct_fields,
        "missing_fields": missing_fields,
        "wrong_fields": wrong_fields,
    }

    # Save current metrics
    output_dir = Path("results")
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "current_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    # Print results table to stdout
    print("\n=== Extraction Evaluation Results ===\n")

    table_data = []
    for filename in sorted(per_file.keys()):
        file_data = per_file[filename]
        row = [filename, f"{file_data['accuracy']:.1%}"]
        for field in fields:
            field_info = file_data["fields"].get(field, {})
            if field_info.get("correct", False):
                status = "correct"
            elif field_info.get("extracted") is None and field_info.get("expected") is not None:
                status = "missing"
            else:
                status = "wrong" if field_info.get("expected") is not None else "extra"
            row.append(status)
        table_data.append(row)

    headers = ["File", "Accuracy"] + fields
    print(tabulate(table_data, headers=headers, tablefmt="grid"))

    print(f"\nOverall Accuracy: {overall_accuracy:.1%}")
    print(f"Total fields: {total_fields} | Correct: {correct_fields} | Wrong: {wrong_fields} | Missing: {missing_fields}")

    # Compute delta vs baseline
    delta_accuracy = None
    changes = []
    if baseline:
        baseline_accuracy = baseline.get("overall_accuracy", 0)
        delta_accuracy = overall_accuracy - baseline_accuracy
        print(f"Delta vs baseline: {delta_accuracy:+.1%}")

        # Track field-level changes
        baseline_per_file = baseline.get("per_file", {})
        for filename in sorted(per_file.keys()):
            if filename not in baseline_per_file:
                continue
            for field in fields:
                curr = per_file[filename]["fields"].get(field, {})
                prev = baseline_per_file.get(filename, {}).get("fields", {}).get(field, {})
                curr_correct = curr.get("correct", False)
                prev_correct = prev.get("correct", False)
                if curr_correct and not prev_correct:
                    impact = 1 / total_fields * 100 if total_fields > 0 else 0
                    changes.append(f"- {filename}: {field} changed from wrong to correct (+{impact:.1f}%)")
                elif not curr_correct and prev_correct:
                    impact = 1 / total_fields * 100 if total_fields > 0 else 0
                    changes.append(f"- {filename}: {field} changed from correct to wrong (-{impact:.1f}%)")

    # Write markdown if requested
    if args.output_markdown:
        md_lines = ["## Extraction Evaluation Results", ""]

        accuracy_str = f"**Overall Accuracy: {overall_accuracy:.1%}**"
        if delta_accuracy is not None:
            accuracy_str += f" (delta: {delta_accuracy:+.1%} vs baseline)"
        md_lines.append(accuracy_str)
        md_lines.append("")

        # Table
        md_lines.append("| File | Accuracy | " + " | ".join(fields) + " |")
        md_lines.append("|------|----------|" + "|".join(["---" for _ in fields]) + "|")

        for filename in sorted(per_file.keys()):
            file_data = per_file[filename]
            row_parts = [filename, f"{file_data['accuracy']:.1%}"]
            for field in fields:
                field_info = file_data["fields"].get(field, {})
                if field_info.get("correct", False):
                    status = "correct"
                elif field_info.get("extracted") is None and field_info.get("expected") is not None:
                    status = "missing"
                else:
                    status = "wrong" if field_info.get("expected") is not None else "extra"
                row_parts.append(status)
            md_lines.append("| " + " | ".join(row_parts) + " |")

        md_lines.append("")

        if changes:
            md_lines.append("### Changes from Baseline")
            md_lines.extend(changes)
            md_lines.append("")

        # Footer
        field_list = ", ".join(fields)
        md_lines.append(f"_Schema: InvoiceSchema with fields: {field_list}_")

        commit_sha = os.getenv("GITHUB_SHA", "local")[:7]
        md_lines.append(f"_Triggered by commit: {commit_sha}_")

        md_content = "\n".join(md_lines) + "\n"

        md_path = output_dir / "pr_comment.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"\nMarkdown written to {md_path}")


if __name__ == "__main__":
    main()
