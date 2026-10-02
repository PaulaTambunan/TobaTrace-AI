"""Pengujian dataset CSV: integritas, tanpa redundansi, akurasi vs label, latensi."""
import csv
import shutil
import time
from collections import Counter

import pytest

from src.dataset import DATA_DIR, check_integrity, evaluate, load_dataset
from src.generator import make_valid_package, AS_OF
from src.solver import VALID, validate_package


def test_dataset_integrity_clean():
    assert check_integrity() == []


def test_no_redundant_rows():
    with open(DATA_DIR / "documents.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len({r["doc_id"] for r in rows}) == len(rows)
    assert len({(r["lot_id"], r["doc_type"], r["version"]) for r in rows}) == len(rows)
    with open(DATA_DIR / "operators.csv", newline="", encoding="utf-8") as f:
        names = [r["operator_name"] for r in csv.DictReader(f)]
    assert len(set(names)) == len(names)


def test_solver_matches_all_labels():
    ds = load_dataset()
    res = evaluate(ds)
    wrong = [l for l, (r, _) in res.items() if r.status != ds.labels[l]]
    assert wrong == []


def test_every_defect_category_is_present():
    ds = load_dataset()
    assert len(set(ds.defects.values())) >= 16
    assert Counter(ds.labels.values()).keys() == {"VALID", "INCOMPLETE", "INVALID_DOCUMENT", "INCONSISTENT"}


def test_latency_budget():
    t0 = time.perf_counter()
    ds = load_dataset()
    load_s = time.perf_counter() - t0
    res = evaluate(ds)
    assert load_s < 1.0                                  # muat < 1 dtk
    assert max(ms for _, ms in res.values()) < 50        # tiap lot < 50 ms


def test_integrity_check_catches_corruption(tmp_path):
    for f in DATA_DIR.glob("*.csv"):
        shutil.copy(f, tmp_path / f.name)
    with open(tmp_path / "documents.csv", "a", encoding="utf-8") as f:
        f.write("DOC-99999,LOT-NOPE,dds_statement,1,OP99,2026-01-01,,1,1.5,0901,ID,100,,\n")
    issues = check_integrity(tmp_path)
    assert any("lot_id tidak ada" in i for i in issues)
    assert any("operator_id tidak ada" in i for i in issues)
    assert any("quality di luar" in i for i in issues)


def test_labels_are_optional_for_real_data(tmp_path):
    for n in ("operators.csv", "lots.csv", "documents.csv"):
        shutil.copy(DATA_DIR / n, tmp_path / n)
    assert check_integrity(tmp_path) == []
    assert load_dataset(tmp_path).labels == {}


def test_hs_heading_4_digit_on_dds_matches_6_digit_invoice():
    docs = make_valid_package()
    docs = [d.__class__(**{**d.__dict__, "hs_code": "0901"}) if d.doc_type == "dds_statement" else d
            for d in docs]
    assert validate_package(docs, as_of=AS_OF).status == VALID
