"""Analisis sensitivitas: ukuran masalah vs waktu & konvergensi solver.

Jalankan:  python -m benchmarks.run_sensitivity
Keluaran:  docs/sensitivity_results.json, docs/fig_*.png
"""
from __future__ import annotations

import json
import statistics as st
import time
from dataclasses import replace
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.generator import AS_OF, add_distractors, make_valid_package
from src.solver import validate_package

OUT = Path(__file__).resolve().parent.parent / "docs"
SEEDS = (1, 2, 3)
NODE_LIMIT = 300_000
SIZES = (0, 2, 5, 10, 20, 40, 80)
CONFIGS = {
    "BT murni":         dict(use_ac3=False, use_mrv=False, use_fc=False),
    "BT + MRV":         dict(use_ac3=False, use_mrv=True,  use_fc=False),
    "AC-3 + BT":        dict(use_ac3=True,  use_mrv=False, use_fc=False),
    "AC-3 + MRV + FC":  dict(use_ac3=True,  use_mrv=True,  use_fc=True),
}


def infeasible(docs):
    """Semua penilaian risiko terbit setelah DDS -> tidak ada solusi."""
    return [replace(d, issue_date=date(2026, 11, 22)) if d.doc_type == "risk_assessment" else d
            for d in docs]


def run_case(docs, cfg, optimize=False):
    t0 = time.perf_counter()
    r = validate_package(docs, as_of=AS_OF, optimize=optimize, node_limit=NODE_LIMIT, **cfg)
    ms = (time.perf_counter() - t0) * 1000
    return dict(status=r.status, ms=ms, nodes=r.stats.nodes, backtracks=r.stats.backtracks,
                revisions=r.stats.ac3_revisions, removed=r.stats.ac3_removed)


def sweep(scenario):
    rows = []
    for d in SIZES:
        for name, cfg in CONFIGS.items():
            runs = []
            for seed in SEEDS:
                docs = add_distractors(make_valid_package(), d, seed=seed, valid_dup_ratio=0.5)
                if scenario == "infeasible":
                    docs = infeasible(docs)
                runs.append(run_case(docs, cfg))
            rows.append(dict(scenario=scenario, distractors=d, domain=d + 1, config=name,
                             status=("TIMEOUT" if sum(r["status"] == "TIMEOUT" for r in runs) >= 2
                                     else runs[0]["status"]),
                             ms=st.median(r["ms"] for r in runs),
                             nodes=int(st.median(r["nodes"] for r in runs)),
                             backtracks=int(st.median(r["backtracks"] for r in runs)),
                             revisions=int(st.median(r["revisions"] for r in runs)),
                             timeouts=sum(r["status"] == "TIMEOUT" for r in runs)))
    return rows


def batch_scale():
    rows = []
    for n_lots in (1, 10, 50, 100, 500):
        lots = {f"L{i}": add_distractors(make_valid_package(f"L{i}"), 10, seed=i)
                for i in range(n_lots)}
        t0 = time.perf_counter()
        ok = sum(validate_package(docs, lot_id=lot, as_of=AS_OF).is_valid
                 for lot, docs in lots.items())
        total = (time.perf_counter() - t0) * 1000
        rows.append(dict(lots=n_lots, variables=11 * n_lots, valid=ok,
                         total_ms=total, per_lot_ms=total / n_lots))
    return rows


def optimality_gap():
    """Bandingkan solusi pertama (greedy) vs branch&bound optimal pada duplikat berkualitas beda."""
    rows = []
    for d in (5, 20, 80):
        docs = add_distractors(make_valid_package(), d, seed=9, valid_dup_ratio=1.0)
        a = validate_package(docs, as_of=AS_OF, optimize=False)
        b = validate_package(docs, as_of=AS_OF, optimize=True)
        rows.append(dict(distractors=d, first_solution_score=round(a.score, 3),
                         optimal_score=round(b.score, 3),
                         first_ms=a.stats.search_time * 1000, opt_ms=b.stats.search_time * 1000,
                         opt_nodes=b.stats.nodes))
    return rows


def plot(rows, scenario, fname, title):
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    for name in CONFIGS:
        sub = [r for r in rows if r["config"] == name and r["scenario"] == scenario]
        x = [r["domain"] for r in sub]
        ax[0].plot(x, [max(r["ms"], 0.01) for r in sub], marker="o", label=name)
        ax[1].plot(x, [max(r["nodes"], 1) for r in sub], marker="o", label=name)
    for a, yl in zip(ax, ("Waktu median (ms)", "Simpul pencarian (median)")):
        a.set_xscale("log"); a.set_yscale("log")
        a.set_xlabel("Ukuran domain per slot"); a.set_ylabel(yl); a.grid(alpha=.3)
    ax[1].axhline(NODE_LIMIT, color="red", ls="--", lw=1)
    ax[1].text(1.1, NODE_LIMIT * 1.2, "batas simpul (TIMEOUT)", color="red", fontsize=8)
    ax[0].legend(fontsize=8)
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / fname, dpi=160)
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    feas = sweep("feasible")
    infe = sweep("infeasible")
    batch = batch_scale()
    gap = optimality_gap()
    (OUT / "sensitivity_results.json").write_text(json.dumps(
        dict(feasible=feas, infeasible=infe, batch=batch, optimality=gap), indent=1))
    plot(feas + infe, "feasible", "fig_feasible.png", "Paket dokumen valid: waktu & simpul vs ukuran domain")
    plot(feas + infe, "infeasible", "fig_infeasible.png", "Paket tidak layak (bukti inkonsistensi): waktu & simpul")
    for name, rows in (("FEASIBLE", feas), ("INFEASIBLE", infe)):
        print(f"\n== {name} ==")
        for r in rows:
            print(f"d={r['distractors']:>3} {r['config']:<16} {r['status']:<12} "
                  f"{r['ms']:9.2f} ms nodes={r['nodes']:>7} rev={r['revisions']:>5} to={r['timeouts']}")
    print("\n== BATCH =="); [print(r) for r in batch]
    print("\n== OPTIMALITY =="); [print(r) for r in gap]


if __name__ == "__main__":
    main()
