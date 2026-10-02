"""Evaluasi solver pada dataset CSV: akurasi vs label, matriks konfusi, latensi.

Jalankan: python -m benchmarks.eval_dataset
"""
import json
import statistics as st
import time
from collections import Counter
from pathlib import Path

from src.dataset import DATA_DIR, check_integrity, evaluate, load_dataset

OUT = Path(__file__).resolve().parent.parent / "docs" / "dataset_eval.json"


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def main():
    problems = check_integrity()
    t0 = time.perf_counter()
    ds = load_dataset()
    load_ms = (time.perf_counter() - t0) * 1000
    n_docs = sum(len(v) for v in ds.docs_by_lot.values())

    res = evaluate(ds)
    ms = [t for _, t in res.values()]
    conf = Counter((ds.labels[l], r.status) for l, (r, _) in res.items())
    correct = sum(v for (a, b), v in conf.items() if a == b)
    wrong = [(l, ds.labels[l], r.status, ds.defects[l]) for l, (r, _) in res.items()
             if r.status != ds.labels[l]]
    by_defect = {}
    for l, (r, _) in res.items():
        d = by_defect.setdefault(ds.defects[l], [0, 0])
        d[1] += 1
        d[0] += r.status == ds.labels[l]
    summary = dict(
        integrity_problems=len(problems), lots=len(ds.docs_by_lot), documents=n_docs,
        load_ms=round(load_ms, 1), total_validate_ms=round(sum(ms), 1),
        per_lot_ms_p50=round(pct(ms, 50), 2), per_lot_ms_p95=round(pct(ms, 95), 2),
        per_lot_ms_max=round(max(ms), 2), accuracy=correct / len(res),
        confusion={f"{a}->{b}": v for (a, b), v in sorted(conf.items())},
        by_defect={k: f"{a}/{b}" for k, (a, b) in sorted(by_defect.items())},
        mismatches=wrong)
    OUT.write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
