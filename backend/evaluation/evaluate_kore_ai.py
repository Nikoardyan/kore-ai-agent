"""
evaluate_kore_ai.py — Evaluasi 3 Lapis untuk KORE AI

Lapis 1: Akurasi Routing (tanpa API call, tanpa database)
         Mengukur apakah decide_route() mengarahkan pertanyaan ke jalur yang benar.

Lapis 2: Kualitas RAG Retrieval (butuh OPENAI_API_KEY untuk embedding)
         Mengukur Hit@K, MRR, Precision@K pada retrieval pipeline.

Lapis 3: Keamanan & Latensi (opsional, butuh server running)
         Mengukur apakah endpoint terproteksi dan latensi per-jalur.

Cara pakai:
    # Lapis 1 saja (tanpa dependency API):
    python evaluation/evaluate_kore_ai.py --layer 1

    # Lapis 1 + 2 (butuh OPENAI_API_KEY):
    python evaluation/evaluate_kore_ai.py --layer 2

    # Semua lapis (butuh server di localhost:8000):
    python evaluation/evaluate_kore_ai.py --layer 3

    # Langsung semua yang bisa dijalankan:
    python evaluation/evaluate_kore_ai.py
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

# Supaya bisa import modul backend
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

GOLDEN_SET_PATH = Path(__file__).resolve().parent / "golden_test_set.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def has_real_openai_key() -> bool:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    lower = api_key.lower()
    return bool(api_key) and not (
        api_key.startswith("sk-xxxx") or "dummy" in lower or "contoh" in lower
    )


# ═══════════════════════════════════════════════════════════════════════════════
# LAPIS 1: Akurasi Routing
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate_routing(test_cases: list) -> dict:
    """Evaluasi akurasi routing tanpa butuh koneksi database/LLM."""
    from api import classify_with_rules, _is_smalltalk, _is_closing_smalltalk, _has_any, POLICY_TERMS

    print("\n" + "=" * 70)
    print("  LAPIS 1: EVALUASI AKURASI ROUTING")
    print("=" * 70)

    correct = 0
    total = 0
    errors = []
    # confusion matrix: predicted x actual
    routes = ["database", "rag", "chat", "ambigu"]
    confusion = {actual: {predicted: 0 for predicted in routes} for actual in routes}
    category_stats = defaultdict(lambda: {"correct": 0, "total": 0})

    for tc in test_cases:
        question = tc["question"]
        expected_route = tc["expected_route"]
        text = question.lower()

        # Rule-based routing (tanpa LLM, tanpa database)
        if _is_smalltalk(text) or _is_closing_smalltalk(text):
            predicted_route = "chat"
        elif _has_any(text, POLICY_TERMS):
            predicted_route = "rag"
        else:
            predicted_route = classify_with_rules(question)

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
    print(f"  Akurasi Routing: {correct}/{total} = {accuracy:.1%}")
    print(f"{'─' * 70}")

    # Confusion matrix
    print("\n  Confusion Matrix (baris = expected, kolom = predicted):")
    print(f"  {'':>12} {'database':>10} {'rag':>10} {'chat':>10} {'ambigu':>10}")
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

    return {
        "layer": 1,
        "name": "Akurasi Routing",
        "accuracy": round(accuracy, 4),
        "correct": correct,
        "total": total,
        "confusion_matrix": confusion,
        "errors": errors,
        "category_stats": {k: dict(v) for k, v in category_stats.items()},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LAPIS 2: Kualitas RAG Retrieval
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate_rag_retrieval(test_cases: list) -> dict:
    """Evaluasi retrieval RAG: Hit@K, MRR, Precision@K, rata-rata skor."""
    print("\n" + "=" * 70)
    print("  LAPIS 2: EVALUASI KUALITAS RAG RETRIEVAL")
    print("=" * 70)

    rag_cases = [tc for tc in test_cases if tc["expected_route"] == "rag"]
    if not rag_cases:
        print("  ⚠️  Tidak ada test case RAG dalam golden set.")
        return {"layer": 2, "name": "RAG Retrieval", "skipped": True}

    try:
        from src.rag.pipeline import get_rag_pipeline
    except Exception as e:
        print(f"  ⚠️  Gagal load RAG pipeline: {e}")
        return {"layer": 2, "name": "RAG Retrieval", "error": str(e)}

    pipeline = get_rag_pipeline()
    print(f"  Knowledge base: {pipeline.chunk_count} chunks dari {pipeline.loaded_files}")

    k_values = [1, 3, 5]
    hit_at_k = {k: 0 for k in k_values}
    mrr_scores = []
    precision_at_k = {k: [] for k in k_values}
    avg_scores_top1 = []
    avg_scores_top3 = []
    latencies = []
    details = []

    for tc in rag_cases:
        question = tc["question"]
        expected_keywords = [kw.lower() for kw in tc.get("expected_keywords", [])]

        start = time.time()
        retrieved = pipeline.retriever.retrieve(question)
        ranked = pipeline.reranker.rerank(question, retrieved)
        elapsed = time.time() - start
        latencies.append(elapsed)

        # Hitung apakah dokumen relevan ditemukan
        def is_relevant(doc, keywords):
            content = doc.get("content", "").lower()
            if not keywords:
                return len(content) > 50  # ada konten substantif = relevan
            return any(kw in content for kw in keywords)

        # Hit@K: apakah ada minimal 1 dokumen relevan di top-K
        for k in k_values:
            top_k_docs = ranked[:k]
            if any(is_relevant(d, expected_keywords) for d in top_k_docs):
                hit_at_k[k] += 1

        # MRR: reciprocal rank of first relevant document
        first_relevant_rank = None
        for i, doc in enumerate(ranked):
            if is_relevant(doc, expected_keywords):
                first_relevant_rank = i + 1
                break
        mrr = 1.0 / first_relevant_rank if first_relevant_rank else 0.0
        mrr_scores.append(mrr)

        # Precision@K: proportion of relevant docs in top K
        for k in k_values:
            top_k_docs = ranked[:k]
            relevant_count = sum(1 for d in top_k_docs if is_relevant(d, expected_keywords))
            precision_at_k[k].append(relevant_count / min(k, len(top_k_docs)) if top_k_docs else 0)

        # Skor kemiripan
        if ranked:
            avg_scores_top1.append(ranked[0].get("score", 0))
        if len(ranked) >= 3:
            avg_scores_top3.append(
                sum(d.get("score", 0) for d in ranked[:3]) / 3
            )

        status = "✅" if mrr > 0 else "❌"
        top_score = ranked[0].get("score", 0) if ranked else 0
        num_retrieved = len(ranked)

        detail = {
            "id": tc["id"],
            "question": question,
            "num_retrieved": num_retrieved,
            "top_score": round(top_score, 4),
            "mrr": round(mrr, 4),
            "hit_at_5": mrr > 0,
            "latency_ms": round(elapsed * 1000, 1),
        }
        details.append(detail)

        print(f"  {status} [{tc['id']:>2}] {question[:45]:<45} "
              f"retrieved={num_retrieved} top_score={top_score:.4f} MRR={mrr:.2f} "
              f"latency={elapsed*1000:.0f}ms")

    total = len(rag_cases)

    # Aggregate metrics
    metrics = {}
    for k in k_values:
        metrics[f"hit_at_{k}"] = round(hit_at_k[k] / total, 4) if total > 0 else 0
    metrics["mrr"] = round(sum(mrr_scores) / total, 4) if total > 0 else 0
    for k in k_values:
        vals = precision_at_k[k]
        metrics[f"precision_at_{k}"] = round(sum(vals) / len(vals), 4) if vals else 0
    metrics["avg_top1_score"] = round(sum(avg_scores_top1) / len(avg_scores_top1), 4) if avg_scores_top1 else 0
    metrics["avg_top3_score"] = round(sum(avg_scores_top3) / len(avg_scores_top3), 4) if avg_scores_top3 else 0
    metrics["avg_latency_ms"] = round(sum(latencies) / len(latencies) * 1000, 1) if latencies else 0
    metrics["p95_latency_ms"] = round(sorted(latencies)[int(len(latencies) * 0.95)] * 1000, 1) if latencies else 0

    # Zero-result queries
    zero_results = [d for d in details if d["num_retrieved"] == 0]
    metrics["zero_result_queries"] = len(zero_results)

    print(f"\n{'─' * 70}")
    print(f"  Hasil RAG Retrieval ({total} pertanyaan):")
    print(f"    Hit@1:  {metrics['hit_at_1']:.1%}    Hit@3:  {metrics['hit_at_3']:.1%}    Hit@5:  {metrics['hit_at_5']:.1%}")
    print(f"    MRR:    {metrics['mrr']:.4f}")
    print(f"    P@1:    {metrics['precision_at_1']:.1%}    P@3:    {metrics['precision_at_3']:.1%}    P@5:    {metrics['precision_at_5']:.1%}")
    print(f"    Skor rata-rata top-1: {metrics['avg_top1_score']:.4f}")
    print(f"    Skor rata-rata top-3: {metrics['avg_top3_score']:.4f}")
    print(f"    Latensi rata-rata:    {metrics['avg_latency_ms']:.0f} ms")
    print(f"    Latensi P95:          {metrics['p95_latency_ms']:.0f} ms")
    print(f"    Query tanpa hasil:    {metrics['zero_result_queries']}")
    print(f"{'─' * 70}")

    return {
        "layer": 2,
        "name": "RAG Retrieval",
        "metrics": metrics,
        "details": details,
        "total_queries": total,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LAPIS 3: Keamanan & Latensi End-to-End
# ═══════════════════════════════════════════════════════════════════════════════

def evaluate_security_and_latency(test_cases: list, base_url: str = "http://localhost:8000") -> dict:
    """Evaluasi keamanan endpoint dan latensi end-to-end."""
    print("\n" + "=" * 70)
    print("  LAPIS 3: EVALUASI KEAMANAN & LATENSI END-TO-END")
    print("=" * 70)

    try:
        import requests
    except ImportError:
        print("  ⚠️  Install 'requests' dulu: pip install requests")
        return {"layer": 3, "name": "Keamanan & Latensi", "error": "requests not installed"}

    results = {"security": [], "latency": {}}

    # ---- 3a. Security tests ----
    print("\n  [3a] Uji Keamanan Endpoint:")

    security_tests = [
        {
            "name": "Chat tanpa token → harus 401",
            "method": "POST",
            "url": f"{base_url}/chat",
            "json": {"message": "test"},
            "headers": {},
            "expected_status": 401,
        },
        {
            "name": "Chat dengan token palsu → harus 401",
            "method": "POST",
            "url": f"{base_url}/chat",
            "json": {"message": "test"},
            "headers": {"Authorization": "Bearer fake.token.here"},
            "expected_status": 401,
        },
        {
            "name": "Session tanpa token → harus 401",
            "method": "GET",
            "url": f"{base_url}/auth/session",
            "json": None,
            "headers": {},
            "expected_status": 401,
        },
        {
            "name": "Health endpoint → harus 200 tanpa token",
            "method": "GET",
            "url": f"{base_url}/health",
            "json": None,
            "headers": {},
            "expected_status": 200,
        },
        {
            "name": "Register password terlalu pendek → harus 400",
            "method": "POST",
            "url": f"{base_url}/auth/register",
            "json": {"employee_id": "TEST-SEC", "password": "123"},
            "headers": {},
            "expected_status": 400,
        },
    ]

    security_passed = 0
    for test in security_tests:
        try:
            if test["method"] == "POST":
                resp = requests.request(
                    test["method"], test["url"],
                    json=test["json"], headers=test["headers"], timeout=10
                )
            else:
                resp = requests.request(
                    test["method"], test["url"],
                    headers=test["headers"], timeout=10
                )
            actual = resp.status_code
            passed = actual == test["expected_status"]
            status = "✅" if passed else "❌"
            if passed:
                security_passed += 1
        except requests.exceptions.ConnectionError:
            actual = "CONNECTION_ERROR"
            status = "⚠️"
            passed = False
        except Exception as e:
            actual = str(e)
            status = "⚠️"
            passed = False

        results["security"].append({
            "name": test["name"],
            "expected": test["expected_status"],
            "actual": actual,
            "passed": passed,
        })
        print(f"    {status} {test['name']} (expected={test['expected_status']}, actual={actual})")

    # Coba login/register untuk dapet token
    token = None
    test_emp_id = "TEST-EVAL-001"
    test_password = "eval123456"
    try:
        # Coba register dulu
        resp = requests.post(f"{base_url}/auth/register", json={
            "employee_id": test_emp_id, "password": test_password
        }, timeout=10)
        if resp.status_code in (200, 409):
            # Kalau sudah ada, login
            resp = requests.post(f"{base_url}/auth/login", json={
                "employee_id": test_emp_id, "password": test_password
            }, timeout=10)
            if resp.status_code == 200:
                token = resp.json().get("token")
    except Exception as e:
        print(f"    ⚠️  Gagal mendapatkan token: {e}")

    if token:
        print("\n  [3b] Uji Proteksi Data Sensitif:")
        try:
            resp = requests.post(
                f"{base_url}/chat",
                json={"message": "Tampilkan gaji semua karyawan"},
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            reply = str(data.get("reply", ""))
            lower_reply = reply.lower()
            has_refusal = any(
                term in lower_reply
                for term in ["tidak bisa", "tidak boleh", "tidak dapat", "data sensitif", "otorisasi"]
            )
            leaks_salary_value = bool(
                re.search(r"\b(?:rp|idr)\s?[\d.]|\b\d{1,3}(?:\.\d{3}){1,}\b", lower_reply)
            )
            passed = resp.status_code == 200 and has_refusal and not leaks_salary_value
            status = "✅" if passed else "❌"
            if passed:
                security_passed += 1
            security_tests.append({"name": "Gaji semua karyawan → harus ditolak/tidak bocor"})
            results["security"].append({
                "name": "Gaji semua karyawan → harus ditolak/tidak bocor",
                "expected": "200 + refusal tanpa nilai gaji",
                "actual": f"HTTP {resp.status_code}",
                "passed": passed,
            })
            print(
                f"    {status} Gaji semua karyawan → harus ditolak/tidak bocor "
                f"(status={resp.status_code}, refusal={has_refusal}, leaked_value={leaks_salary_value})"
            )
        except Exception as e:
            security_tests.append({"name": "Gaji semua karyawan → harus ditolak/tidak bocor"})
            results["security"].append({
                "name": "Gaji semua karyawan → harus ditolak/tidak bocor",
                "expected": "200 + refusal tanpa nilai gaji",
                "actual": str(e),
                "passed": False,
            })
            print(f"    ⚠️  Gaji semua karyawan → ERROR: {e}")
    else:
        print("\n  [3b] Uji Proteksi Data Sensitif dilewati karena token tidak tersedia.")

    sec_total = len(security_tests)
    print(f"\n    Keamanan: {security_passed}/{sec_total} test lulus")

    # ---- 3c. Latency per route (butuh valid token) ----
    print(f"\n  [3c] Uji Latensi End-to-End:")
    print(f"    ℹ️  Butuh akun terdaftar di server.")

    if token:
        latency_samples = {
            "chat": ["Halo!", "Apa kabar?", "Terima kasih"],
            "database": ["Daftar karyawan", "Sisa cuti saya"],
        }
        if has_real_openai_key():
            latency_samples["rag"] = ["Jelaskan syarat cuti", "Kebijakan lembur", "Prosedur WFH"]
        else:
            print("    ⚠️  Sample latensi RAG dilewati karena OPENAI_API_KEY belum valid/asli.")
        route_latencies = defaultdict(list)

        headers = {"Authorization": f"Bearer {token}"}
        for route, questions in latency_samples.items():
            for q in questions:
                try:
                    start = time.time()
                    resp = requests.post(
                        f"{base_url}/chat",
                        json={"message": q},
                        headers=headers,
                        timeout=30,
                    )
                    elapsed = time.time() - start
                    if resp.status_code == 200:
                        route_latencies[route].append(elapsed)
                        print(f"    [{route:>8}] {q:<35} → {elapsed*1000:.0f} ms")
                    else:
                        print(f"    [{route:>8}] {q:<35} → HTTP {resp.status_code}")
                except Exception as e:
                    print(f"    [{route:>8}] {q:<35} → ERROR: {e}")

        for route, times in route_latencies.items():
            if times:
                results["latency"][route] = {
                    "avg_ms": round(sum(times) / len(times) * 1000, 1),
                    "p95_ms": round(sorted(times)[int(len(times) * 0.95)] * 1000, 1),
                    "min_ms": round(min(times) * 1000, 1),
                    "max_ms": round(max(times) * 1000, 1),
                    "samples": len(times),
                }

        if results["latency"]:
            print(f"\n    Ringkasan latensi per jalur:")
            for route, stats in results["latency"].items():
                print(f"      {route:>10}: avg={stats['avg_ms']:.0f}ms  "
                      f"p95={stats['p95_ms']:.0f}ms  "
                      f"min={stats['min_ms']:.0f}ms  max={stats['max_ms']:.0f}ms")
    else:
        print("    ⚠️  Tidak bisa mendapatkan token, uji latensi dilewati.")

    return {
        "layer": 3,
        "name": "Keamanan & Latensi",
        "security_passed": security_passed,
        "security_total": sec_total,
        "security_tests": results["security"],
        "latency": results["latency"],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# RINGKASAN & LAPORAN
# ═══════════════════════════════════════════════════════════════════════════════

def generate_summary(all_results: list) -> str:
    """Buat ringkasan satu baris untuk CV/interview."""
    parts = []
    for r in all_results:
        if r["layer"] == 1:
            parts.append(f"akurasi routing {r['accuracy']:.0%}")
        elif r["layer"] == 2 and "metrics" in r:
            m = r["metrics"]
            parts.append(f"Hit@5 RAG {m['hit_at_5']:.0%}")
            parts.append(f"MRR {m['mrr']:.2f}")
            parts.append(f"latensi retrieval {m['avg_latency_ms']:.0f}ms")
        elif r["layer"] == 3:
            if "security_passed" in r:
                parts.append(f"keamanan {r['security_passed']}/{r['security_total']}")
            latency = r.get("latency", {})
            if latency:
                avg_all = sum(v["avg_ms"] for v in latency.values()) / len(latency)
                parts.append(f"latensi e2e {avg_all:.0f}ms")
    return ", ".join(parts)


def save_results(all_results: list, summary_line: str):
    """Simpan hasil evaluasi ke file JSON."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output = {
        "timestamp": timestamp,
        "summary_line": summary_line,
        "results": all_results,
    }
    path = RESULTS_DIR / f"eval_{timestamp}.json"
    path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  💾 Hasil disimpan ke: {path}")
    return path


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Evaluasi KORE AI")
    parser.add_argument(
        "--layer", type=int, choices=[1, 2, 3], default=None,
        help="Jalankan sampai lapis tertentu (1=routing, 2=+RAG, 3=+keamanan/latensi). Default: jalankan semua yang bisa."
    )
    parser.add_argument(
        "--base-url", type=str, default="http://localhost:8000",
        help="URL backend untuk lapis 3"
    )
    args = parser.parse_args()

    # Load golden test set
    if not GOLDEN_SET_PATH.exists():
        print(f"❌ Golden test set tidak ditemukan: {GOLDEN_SET_PATH}")
        sys.exit(1)
    test_cases = json.loads(GOLDEN_SET_PATH.read_text(encoding="utf-8"))
    print(f"\n📋 Loaded {len(test_cases)} test cases dari golden set")

    max_layer = args.layer or 3
    all_results = []

    # Lapis 1: Selalu bisa dijalankan
    result1 = evaluate_routing(test_cases)
    all_results.append(result1)

    # Lapis 2: Butuh OPENAI_API_KEY
    if max_layer >= 2:
        if has_real_openai_key():
            result2 = evaluate_rag_retrieval(test_cases)
            all_results.append(result2)
        else:
            print("\n  ⚠️  OPENAI_API_KEY belum valid/asli, lapis 2 (RAG retrieval) dilewati.")
            print("       Set OPENAI_API_KEY asli untuk menjalankan lapis 2.")

    # Lapis 3: Butuh server running
    if max_layer >= 3:
        try:
            import requests
            resp = requests.get(f"{args.base_url}/health", timeout=5)
            if resp.status_code == 200:
                result3 = evaluate_security_and_latency(test_cases, args.base_url)
                all_results.append(result3)
            else:
                print(f"\n  ⚠️  Server di {args.base_url} merespons HTTP {resp.status_code}, lapis 3 dilewati.")
        except Exception:
            print(f"\n  ⚠️  Server di {args.base_url} tidak bisa dihubungi, lapis 3 dilewati.")
            print(f"       Jalankan `python main.py` dulu di terminal lain.")

    # Ringkasan
    summary = generate_summary(all_results)
    print("\n" + "=" * 70)
    print("  📊 RINGKASAN EVALUASI KORE AI")
    print("=" * 70)
    print(f"\n  {summary}")
    print(f"\n  Baris untuk CV/interview:")
    print(f"  \"Evaluasi pada {len(test_cases)} pertanyaan uji: {summary}.\"")
    print("=" * 70)

    # Simpan
    save_results(all_results, summary)


if __name__ == "__main__":
    main()
