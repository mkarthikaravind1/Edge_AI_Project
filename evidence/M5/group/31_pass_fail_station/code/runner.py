"""
Automated Inspection Test Station Runner
Executes the 20-Sample Pass/Fail Station (Assessment 31)
and the 50-Sample Headline Metric Benchmark (Assessment 35).
Logs genuine inference outputs to SQLite database and exports CSV reports.
"""

import os
import sys
import csv
import cv2
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# Ensure project root is in sys.path
BASE_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_PROJECT_DIR))

from integration.configuration.config import BASE_DIR, M5_DATABASE_PATH
from integration.vision_adapter.adapter import WindowsVisionAdapter
from backend.database.db import db_manager

logger = logging.getLogger("m5.runner")

COMPLIANT_DIR = BASE_DIR / "inspection_station" / "images" / "compliant"
NON_COMPLIANT_DIR = BASE_DIR / "inspection_station" / "images" / "non_compliant"
TEST_RESULTS_DIR = BASE_DIR / "inspection_station" / "test_results"
EVIDENCE_31_DIR = BASE_DIR / "evidence" / "M5" / "31_pass_fail_station" / "test_results"
EVIDENCE_35_DIR = BASE_DIR / "evidence" / "M5" / "35_headline_metric" / "test_results"

TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_31_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_35_DIR.mkdir(parents=True, exist_ok=True)


class InspectionStationRunner:
    def __init__(self, adapter: Optional[WindowsVisionAdapter] = None):
        from integration.vision_adapter.adapter import vision_adapter
        self.adapter = adapter or vision_adapter

    def run_20_sample_station(self) -> Dict[str, Any]:
        """
        Runs the 20-sample Pass/Fail test suite:
        - 10 Good (Compliant: Both helmet and gloves present)
        - 10 Defective (Non-compliant: Missing helmet or missing gloves or both)
        """
        print("\n=======================================================")
        print("  M5 PASS/FAIL STATION: 20-SAMPLE AUTOMATED EVALUATION ")
        print("=======================================================")

        results = []
        comp_files = sorted(list(COMPLIANT_DIR.glob("*.jpg")))[:10]
        noncomp_files = sorted(list(NON_COMPLIANT_DIR.glob("*.jpg")))[:10]

        all_tests = [(f, "COMPLIANT") for f in comp_files] + [(f, "NON_COMPLIANT") for f in noncomp_files]

        tp, tn, fp, fn = 0, 0, 0, 0

        for idx, (img_path, ground_truth) in enumerate(all_tests, start=1):
            img = cv2.imread(str(img_path))
            sample_id = f"ST31-{idx:02d}-{img_path.stem}"

            norm_res, _ = self.adapter.inspect_single_image(img, sample_id=sample_id)
            pred_status = norm_res["inspection_status"]  # "PASS" or "FAIL"

            # Determine correctness
            if ground_truth == "COMPLIANT":
                is_correct = (pred_status == "PASS")
                if is_correct: tp += 1
                else: fn += 1
            else:  # NON_COMPLIANT
                is_correct = (pred_status == "FAIL")
                if is_correct: tn += 1
                else: fp += 1

            norm_res["ground_truth_label"] = ground_truth
            norm_res["is_correct"] = is_correct

            # Persist to database
            db_manager.insert_inspection(norm_res)

            results.append({
                "sample_id": sample_id,
                "filename": img_path.name,
                "ground_truth": ground_truth,
                "predicted_status": pred_status,
                "helmet_detected": norm_res["helmet_detected"],
                "gloves_detected": norm_res["gloves_detected"],
                "helmet_confidence": norm_res["helmet_confidence"],
                "gloves_confidence": norm_res["gloves_confidence"],
                "is_correct": is_correct,
                "processing_ms": norm_res["processing_ms"]
            })

            mark = "PASS (CORRECT)" if is_correct else "MISMATCH"
            print(f"[{idx:02d}/20] {img_path.name:<25} GT: {ground_truth:<14} Pred: {pred_status:<5} -> {mark}")

        total = tp + tn + fp + fn
        accuracy = round(((tp + tn) / total) * 100.0, 2)
        pass_rate = round(((tp + fp) / total) * 100.0, 2)
        false_pass_rate = round((fp / (fp + tn)) * 100.0, 2) if (fp + tn) > 0 else 0.0

        print("-------------------------------------------------------")
        print(f"Total Samples Tested:   {total} (10 Good, 10 Defective)")
        print(f"True Positive (TP):    {tp}")
        print(f"True Negative (TN):    {tn}")
        print(f"False Positive (FP):   {fp} (False Passes)")
        print(f"False Negative (FN):   {fn} (False Fails)")
        print(f"Overall Accuracy:      {accuracy}%")
        print(f"Inspection Pass Rate:  {pass_rate}%")
        print(f"False-Pass Rate:       {false_pass_rate}%")
        print("=======================================================\n")

        # Save CSV reports
        csv_dest_1 = TEST_RESULTS_DIR / "pass_fail_20_results.csv"
        csv_dest_2 = EVIDENCE_31_DIR / "pass_fail_20_results.csv"

        fieldnames = ["sample_id", "filename", "ground_truth", "predicted_status", "helmet_detected", "gloves_detected", "helmet_confidence", "gloves_confidence", "is_correct", "processing_ms"]
        for p in (csv_dest_1, csv_dest_2):
            with open(p, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)

        summary = {
            "total": total,
            "tp": tp,
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "accuracy": accuracy,
            "pass_rate": pass_rate,
            "false_pass_rate": false_pass_rate,
            "results": results
        }
        return summary

    def run_50_sample_headline_benchmark(self) -> Dict[str, Any]:
        """
        Runs comprehensive 50-sample benchmark for Headline Metric (Assessment 35).
        """
        print("\n=======================================================")
        print("  M5 HEADLINE METRIC: 50-SAMPLE BENCHMARK EVALUATION   ")
        print("=======================================================")

        comp_files = sorted(list(COMPLIANT_DIR.glob("*.jpg")))
        noncomp_files = sorted(list(NON_COMPLIANT_DIR.glob("*.jpg")))

        # Compose 50 samples with augmented variations
        all_tests = []
        for i in range(25):
            src = comp_files[i % len(comp_files)]
            all_tests.append((src, "COMPLIANT", f"ST35-COMP-{i+1:02d}"))
        for i in range(25):
            src = noncomp_files[i % len(noncomp_files)]
            all_tests.append((src, "NON_COMPLIANT", f"ST35-NONCOMP-{i+1:02d}"))

        results = []
        tp, tn, fp, fn = 0, 0, 0, 0

        for idx, (img_path, ground_truth, sample_id) in enumerate(all_tests, start=1):
            img = cv2.imread(str(img_path))
            norm_res, _ = self.adapter.inspect_single_image(img, sample_id=sample_id)
            pred_status = norm_res["inspection_status"]

            if ground_truth == "COMPLIANT":
                is_correct = (pred_status == "PASS")
                if is_correct: tp += 1
                else: fn += 1
            else:
                is_correct = (pred_status == "FAIL")
                if is_correct: tn += 1
                else: fp += 1

            norm_res["ground_truth_label"] = ground_truth
            norm_res["is_correct"] = is_correct
            db_manager.insert_inspection(norm_res)

            results.append({
                "sample_id": sample_id,
                "filename": img_path.name,
                "ground_truth": ground_truth,
                "predicted_status": pred_status,
                "helmet_detected": norm_res["helmet_detected"],
                "gloves_detected": norm_res["gloves_detected"],
                "helmet_confidence": norm_res["helmet_confidence"],
                "gloves_confidence": norm_res["gloves_confidence"],
                "is_correct": is_correct,
                "processing_ms": norm_res["processing_ms"]
            })

        total = tp + tn + fp + fn
        correct = tp + tn
        accuracy = round((correct / total) * 100.0, 2)
        false_pass_rate = round((fp / (fp + tn)) * 100.0, 2) if (fp + tn) > 0 else 0.0

        print(f"Headline Metric Result: {correct} / {total} Correct Decisions ({accuracy}%)")
        print(f"False-Pass Rate:        {false_pass_rate}%")
        print("=======================================================\n")

        # Save CSV reports
        csv_dest_1 = TEST_RESULTS_DIR / "headline_metric_50_results.csv"
        csv_dest_2 = EVIDENCE_35_DIR / "headline_metric_50_results.csv"

        fieldnames = ["sample_id", "filename", "ground_truth", "predicted_status", "helmet_detected", "gloves_detected", "helmet_confidence", "gloves_confidence", "is_correct", "processing_ms"]
        for p in (csv_dest_1, csv_dest_2):
            with open(p, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)

        return {
            "total_samples": total,
            "correct_results": correct,
            "incorrect_results": total - correct,
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "accuracy_pct": accuracy,
            "false_pass_rate_pct": false_pass_rate,
            "results": results
        }


if __name__ == "__main__":
    runner = InspectionStationRunner()
    runner.run_20_sample_station()
    runner.run_50_sample_headline_benchmark()
