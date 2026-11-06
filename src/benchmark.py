"""Milestone 3: benchmark temu balik semantik (cosine similarity) dan evaluasi penolakan out-of-domain."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from src.ingest import COLLECTION_NAME, DEFAULT_DB_PATH, DEFAULT_MODEL

OOD_TYPE = "out_of_domain"
DEFAULT_THRESHOLD = 0.45  # ditetapkan dari sweep pada compute_threshold_sweep, lihat laporan
THRESHOLD_GRID = [round(0.30 + 0.05 * i, 2) for i in range(9)]  # 0.30 .. 0.70


def run_benchmark(
    queries_path: str = "data/queries.json",
    db_path: str = DEFAULT_DB_PATH,
    model_name: str = DEFAULT_MODEL,
    k: int = 3,
    out_csv: str = "data/benchmark_results.csv",
) -> list[dict]:
    """Jalankan semua kueri uji terhadap ChromaDB dan simpan skor top-k per kueri."""
    import chromadb
    from sentence_transformers import SentenceTransformer

    queries = json.loads(Path(queries_path).read_text(encoding="utf-8"))
    model = SentenceTransformer(model_name)
    collection = chromadb.PersistentClient(path=db_path).get_collection(COLLECTION_NAME)

    rows = []
    for q in queries:
        emb = model.encode([q["query"]], normalize_embeddings=True).tolist()
        res = collection.query(query_embeddings=emb, n_results=k)
        scores = [round(1 - d, 4) for d in res["distances"][0]]  # cosine similarity = 1 - jarak
        sources = [m["source"] for m in res["metadatas"][0]]
        rows.append(
            {
                "type": q["type"],
                "query": q["query"],
                "expected_source": q.get("expected_source", ""),
                "top1_source": sources[0] if sources else "",
                "top1_score": scores[0] if scores else 0.0,
                "top3_scores": ";".join(f"{s:.4f}" for s in scores),
                "top3_sources": ";".join(sources),
            }
        )
    _write_csv(rows, out_csv)
    return rows


def _write_csv(rows: list[dict], out_csv: str) -> None:
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _rank_of(expected: str, sources: list[str]) -> int | None:
    """Posisi (1-based) dokumen target dalam daftar top-k, atau None bila tidak ada."""
    for i, s in enumerate(sources, start=1):
        if s == expected:
            return i
    return None


def compute_metrics(rows: list[dict], threshold: float = DEFAULT_THRESHOLD) -> dict:
    """Ringkasan metrik dari baris hasil benchmark.

    - hit@1 dan MRR untuk kueri in-domain (sinonim & ambigu) yang memiliki dokumen target.
    - rata-rata skor top-1 per jenis kueri.
    - Penolakan out-of-domain sebagai klasifikasi biner (positif = ditolak):
      precision, recall, F1, dan akurasi pada ambang `threshold`.
    """
    in_domain = [r for r in rows if r["type"] != OOD_TYPE and r["expected_source"]]
    hits, rr = 0, 0.0
    for r in in_domain:
        sources = r["top3_sources"].split(";")
        rank = _rank_of(r["expected_source"], sources)
        if rank == 1 and r["top1_score"] >= threshold:
            hits += 1
        if rank is not None:
            rr += 1.0 / rank
    n_in = len(in_domain)

    by_type: dict[str, list[float]] = {}
    for r in rows:
        by_type.setdefault(r["type"], []).append(float(r["top1_score"]))
    mean_top1 = {t: round(sum(v) / len(v), 4) for t, v in by_type.items()}

    tp = fp = fn = tn = 0
    for r in rows:
        is_ood = r["type"] == OOD_TYPE
        rejected = float(r["top1_score"]) < threshold
        if is_ood and rejected:
            tp += 1
        elif is_ood and not rejected:
            fn += 1
        elif not is_ood and rejected:
            fp += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / len(rows) if rows else 0.0

    return {
        "threshold": threshold,
        "hit_at_1": round(hits / n_in, 4) if n_in else 0.0,
        "mrr": round(rr / n_in, 4) if n_in else 0.0,
        "mean_top1_score_per_type": mean_top1,
        "ood_rejection": {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "accuracy": round(accuracy, 4),
        },
    }


def compute_threshold_sweep(rows: list[dict], grid: list[float] = THRESHOLD_GRID) -> list[dict]:
    """Metrik penolakan untuk setiap ambang di grid, untuk memilih dan menjustifikasi ambang."""
    out = []
    for t in grid:
        m = compute_metrics(rows, t)
        out.append({"threshold": t, **m["ood_rejection"], "hit_at_1": m["hit_at_1"]})
    return out


if __name__ == "__main__":
    rows = run_benchmark()
    metrics = compute_metrics(rows)
    sweep = compute_threshold_sweep(rows)
    Path("data/benchmark_metrics.json").write_text(
        json.dumps({"metrics": metrics, "sweep": sweep}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
