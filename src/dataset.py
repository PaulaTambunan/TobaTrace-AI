"""Pemuat dataset CSV ternormalisasi + pemeriksa integritas + evaluasi terhadap label."""
from __future__ import annotations

import csv
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from .models import SLOT_BY_NAME, Document
from .solver import ValidationReport, validate_package

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

HEADERS = {
    "operators.csv": ["operator_id", "operator_name"],
    "lots.csv": ["lot_id", "as_of"],
    "labels.csv": ["lot_id", "expected_status", "defect"],
    "documents.csv": ["doc_id", "lot_id", "doc_type", "version", "operator_id", "issue_date",
                      "valid_until", "signed", "quality", "hs_code", "country", "quantity_kg",
                      "risk_level", "reference_date"],
}
STATUSES = {"VALID", "INCOMPLETE", "INVALID_DOCUMENT", "INCONSISTENT"}


def _read(path: Path) -> List[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _date(s: str) -> Optional[date]:
    return date.fromisoformat(s) if s else None


@dataclass
class Dataset:
    operators: Dict[str, str]
    as_of: Dict[str, date]
    docs_by_lot: Dict[str, List[Document]]
    labels: Dict[str, str]
    defects: Dict[str, str]


def load_dataset(data_dir: Path = DATA_DIR) -> Dataset:
    """Muat semua tabel; dokumen diindeks per lot sehingga akses per lot O(1)."""
    data_dir = Path(data_dir)
    operators = {r["operator_id"]: r["operator_name"] for r in _read(data_dir / "operators.csv")}
    as_of = {r["lot_id"]: date.fromisoformat(r["as_of"]) for r in _read(data_dir / "lots.csv")}
    labels, defects = {}, {}
    if (data_dir / "labels.csv").exists():   # label opsional (data riil tidak berlabel)
        for r in _read(data_dir / "labels.csv"):
            labels[r["lot_id"]], defects[r["lot_id"]] = r["expected_status"], r["defect"]
    by_lot: Dict[str, List[Document]] = {lot: [] for lot in as_of}
    for r in _read(data_dir / "documents.csv"):
        by_lot[r["lot_id"]].append(Document(
            doc_id=r["doc_id"], doc_type=r["doc_type"], lot_id=r["lot_id"],
            issue_date=date.fromisoformat(r["issue_date"]),
            operator_name=operators.get(r["operator_id"], ""),
            hs_code=r["hs_code"] or None, country=r["country"] or None,
            quantity_kg=float(r["quantity_kg"]) if r["quantity_kg"] else None,
            valid_until=_date(r["valid_until"]), signed=r["signed"] == "1",
            quality=float(r["quality"]), version=int(r["version"]),
            risk_level=r["risk_level"] or None, reference_date=_date(r["reference_date"])))
    return Dataset(operators, as_of, by_lot, labels, defects)


def check_integrity(data_dir: Path = DATA_DIR) -> List[str]:
    """Kembalikan daftar pelanggaran integritas (kosong = bersih)."""
    data_dir = Path(data_dir)
    problems: List[str] = []
    tables = {}
    for name, header in HEADERS.items():
        if name == "labels.csv" and not (data_dir / name).exists():
            tables[name] = []
            continue
        with open(data_dir / name, newline="", encoding="utf-8") as f:
            rd = csv.reader(f)
            if next(rd) != header:
                problems.append(f"{name}: header tidak sesuai skema")
        tables[name] = _read(data_dir / name)

    ops, lots, labs, docs = (tables[k] for k in ("operators.csv", "lots.csv", "labels.csv", "documents.csv"))
    dup = lambda rows, key: [k for k, c in Counter(key(r) for r in rows).items() if c > 1]
    for k in dup(ops, lambda r: r["operator_id"]): problems.append(f"operator_id duplikat: {k}")
    for k in dup(ops, lambda r: r["operator_name"]): problems.append(f"operator_name duplikat: {k}")
    for k in dup(lots, lambda r: r["lot_id"]): problems.append(f"lot_id duplikat: {k}")
    for k in dup(labs, lambda r: r["lot_id"]): problems.append(f"label duplikat: {k}")
    for k in dup(docs, lambda r: r["doc_id"]): problems.append(f"doc_id duplikat: {k}")
    for k in dup(docs, lambda r: (r["lot_id"], r["doc_type"], r["version"])):
        problems.append(f"(lot,tipe,versi) duplikat: {k}")
    for k in dup(docs, lambda r: tuple(v for c, v in r.items() if c != "doc_id")):
        problems.append(f"baris dokumen identik (selain doc_id): {k[0]}")

    op_ids, lot_ids = {r["operator_id"] for r in ops}, {r["lot_id"] for r in lots}
    if labs and lot_ids != {r["lot_id"] for r in labs}:
        problems.append("lots.csv dan labels.csv tidak memuat lot yang sama")
    doc_types = set(SLOT_BY_NAME)
    for r in docs:
        i = r["doc_id"]
        if r["lot_id"] not in lot_ids: problems.append(f"{i}: lot_id tidak ada di lots.csv")
        if r["operator_id"] and r["operator_id"] not in op_ids: problems.append(f"{i}: operator_id tidak ada")
        if r["doc_type"] not in doc_types: problems.append(f"{i}: doc_type tidak dikenal {r['doc_type']}")
        if r["signed"] not in ("0", "1"): problems.append(f"{i}: signed harus 0/1")
        if not r["version"].isdigit() or int(r["version"]) < 1: problems.append(f"{i}: version tidak valid")
        try:
            if not 0 <= float(r["quality"]) <= 1: problems.append(f"{i}: quality di luar 0..1")
        except ValueError:
            problems.append(f"{i}: quality bukan angka")
        for c in ("issue_date", "valid_until", "reference_date"):
            try: _date(r[c])
            except ValueError: problems.append(f"{i}: {c} bukan tanggal ISO")
        if not r["issue_date"]: problems.append(f"{i}: issue_date kosong")
        if r["hs_code"] and not re.fullmatch(r"\d{4}(\.\d{2})?", r["hs_code"]): problems.append(f"{i}: format hs_code")
        if r["country"] and not re.fullmatch(r"[A-Z]{2}", r["country"]): problems.append(f"{i}: format country")
        if r["quantity_kg"] and not r["quantity_kg"].isdigit(): problems.append(f"{i}: quantity_kg bukan bilangan bulat")
        if r["risk_level"] not in ("", "negligible", "non_negligible"): problems.append(f"{i}: risk_level")
    for r in labs:
        if r["expected_status"] not in STATUSES: problems.append(f"{r['lot_id']}: status label tidak dikenal")
    for r in lots:
        try: date.fromisoformat(r["as_of"])
        except ValueError: problems.append(f"{r['lot_id']}: as_of bukan tanggal ISO")
    return problems


def evaluate(ds: Dataset, **solver_kw):
    """Jalankan solver per lot; kembalikan {lot: (laporan, ms)}."""
    out: Dict[str, tuple] = {}
    for lot, docs in ds.docs_by_lot.items():
        t0 = time.perf_counter()
        rep = validate_package(docs, lot_id=lot, as_of=ds.as_of[lot], **solver_kw)
        out[lot] = (rep, (time.perf_counter() - t0) * 1000)
    return out


if __name__ == "__main__":  # python -m src.dataset [folder_data]
    import sys
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_DIR
    issues = check_integrity(folder)
    print(f"Integritas: {'BERSIH' if not issues else str(len(issues)) + ' masalah'}")
    for i in issues[:20]:
        print("  -", i)
    if not issues:
        ds = load_dataset(folder)
        res = evaluate(ds)
        print(Counter(r.status for r, _ in res.values()))
