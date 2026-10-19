"""
evaluate_routing_full.py — Evaluasi routing KORE AI menggunakan decide_route()

Ini menguji decide_route() secara penuh (termasuk detect_db_topic, find_identifier,
dan smalltalk detection), tapi TANPA koneksi database dan LLM.

Ini memberikan gambaran lebih akurat dari rule-based routing di production.
"""

import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

GOLDEN_SET_PATH = Path(__file__).resolve().parent / "golden_test_set.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Load dotenv jika ada
try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env", override=True)
except ImportError:
    pass


def evaluate_full_routing(test_cases: list) -> dict:
    """Evaluasi decide_route() secara penuh."""
    from api import (
        decide_route, _is_smalltalk, _is_closing_smalltalk,
        _has_any, POLICY_TERMS, detect_db_topic, find_identifier,
        get_name_memory_reply, classify_with_rules
    )

    print("\n" + "=" * 70)
    print("  EVALUASI ROUTING PENUH (decide_route)")
    print("=" * 70)

    correct = 0
    total = 0
    errors = []
    routes = ["database", "rag", "chat"]
    confusion = {a: {p: 0 for p in routes} for a in routes}
    category_stats = defaultdict(lambda: {"correct": 0, "total": 0})

    for tc in test_cases:
        question = tc["question"]
        expected_route = tc["expected_route"]
        text = question.lower()

        # Gunakan decide_route() — simulasi tanpa employee_id login
        # employee_id dipassing hanya kalau test case butuh self-reference
        emp_id = "EMP-001" if tc.get("needs_employee_id") else None

        # Name memory handling (ini di production ditangani sebelum routing)
        memory = get_name_memory_reply(question, None)
        if memory:
            predicted_route = "chat"
        else:
            decision = decide_route(question, [], employee_id=emp_id)
            predicted_route = decision["route"]

        total += 1
        is_correct = predicted_route == expected_route

        if is_correct:
            correct += 1
            status = "✅"
        else:
            status = "❌"
            errors.append({
                "id": tc["id"],
                "question": question,
                "expected": expected_route,
                "predicted": predicted_route,
                "category": tc["category"],
            })

        category = tc["category"]
        category_stats[category]["total"] += 1
        if is_correct:
            category_stats[category]["correct"] += 1

        if expected_route in routes and predicted_route in routes:
            confusion[expected_route][predicted_route] += 1

        print(f"  {status} [{tc['id']:>2}] {question[:50]:<50} "
              f"expected={expected_route:<10} predicted={predicted_route:<10}")

    accuracy = correct / total if total > 0 else 0

    print(f"\n{'─' * 70}")
    print(f"  Akurasi Routing (decide_route): {correct}/{total} = {accuracy:.1%}")
    print(f"{'─' * 70}")

    # Confusion matrix
    print("\n  Confusion Matrix (baris = expected, kolom = predicted):")
    print(f"  {'':>12} {'database':>10} {'rag':>10} {'chat':>10}")
    for actual in routes:
        row = "  " + f"{actual:>12}"
        for predicted in routes:
            count = confusion[actual][predicted]
            row += f" {count:>10}"
        print(row)

    # Per-category breakdown
    print(f"\n  Akurasi per kategori:")
    for cat, stats in sorted(category_stats.items()):
        cat_acc = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
        print(f"    {cat:<25} {stats['correct']}/{stats['total']} = {cat_acc:.0%}")

    if errors:
        print(f"\n  ❌ {len(errors)} pertanyaan salah route:")
        for e in errors:
            print(f"    [{e['id']}] \"{e['question'][:60]}\"")
            print(f"         expected={e['expected']}, predicted={e['predicted']} ({e['category']})")

    # Simpan
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output = {
        "timestamp": timestamp,
        "evaluator": "decide_route (full routing)",
        "accuracy": round(accuracy, 4),
        "correct": correct,
        "total": total,
        "confusion_matrix": confusion,
        "errors": errors,
        "category_stats": {k: dict(v) for k, v in category_stats.items()},
    }
    path = RESULTS_DIR / f"eval_routing_full_{timestamp}.json"
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  💾 Hasil disimpan ke: {path}")

    return output


if __name__ == "__main__":
    if not GOLDEN_SET_PATH.exists():
        print(f"❌ Golden test set tidak ditemukan: {GOLDEN_SET_PATH}")
        sys.exit(1)
    test_cases = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    print(f"\n📋 Loaded {len(test_cases)} test cases")
    evaluate_full_routing(test_cases)
