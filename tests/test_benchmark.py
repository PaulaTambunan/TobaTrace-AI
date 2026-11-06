from src.benchmark import compute_metrics, compute_threshold_sweep


def _row(t, score, sources, expected=""):
    return {
        "type": t, "query": "q", "expected_source": expected,
        "top1_score": score, "top3_sources": ";".join(sources),
    }


def test_hit_at_1_and_mrr():
    rows = [
        _row("sinonim", 0.8, ["A.txt", "B.txt", "C.txt"], expected="A.txt"),  # rank 1
        _row("sinonim", 0.7, ["B.txt", "A.txt", "C.txt"], expected="A.txt"),  # rank 2
    ]
    m = compute_metrics(rows, threshold=0.45)
    assert m["hit_at_1"] == 0.5
    assert m["mrr"] == round((1 + 0.5) / 2, 4)


def test_ood_rejection_counts():
    rows = [
        _row("sinonim", 0.8, ["A.txt"], expected="A.txt"),       # diterima, benar
        _row("out_of_domain", 0.2, ["X.txt"]),                    # ditolak, benar (TP)
        _row("out_of_domain", 0.6, ["X.txt"]),                    # diterima, salah (FN)
        _row("sinonim", 0.3, ["A.txt"], expected="A.txt"),       # ditolak, salah (FP)
    ]
    r = compute_metrics(rows, threshold=0.45)["ood_rejection"]
    assert (r["tp"], r["fp"], r["fn"], r["tn"]) == (1, 1, 1, 1)
    assert r["precision"] == 0.5
    assert r["recall"] == 0.5


def test_sweep_is_monotonic_in_rejections():
    rows = [
        _row("out_of_domain", 0.35, ["X"]),
        _row("out_of_domain", 0.55, ["X"]),
        _row("sinonim", 0.75, ["A"], expected="A"),
    ]
    sweep = compute_threshold_sweep(rows)
    rejected = [s["tp"] + s["fp"] for s in sweep]
    assert rejected == sorted(rejected)
