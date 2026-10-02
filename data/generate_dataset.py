"""Pembangkit dataset dummy TobaTrace AI (deterministik, seed tetap).

Menghasilkan 4 tabel CSV ternormalisasi (3NF) di folder data/:
  operators.csv  lots.csv  documents.csv  labels.csv
Jalankan:  python data/generate_dataset.py
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
OUT = Path(__file__).resolve().parent

OPERATORS = [  # seluruhnya fiktif
    ("OP01", "Koperasi Kopi Toba Lestari"),
    ("OP02", "Koperasi Arabika Samosir Jaya"),
    ("OP03", "Koperasi Tani Humbang Mandiri"),
    ("OP04", "CV Sumatera Arabika Ekspor"),
    ("OP05", "Koperasi Lintong Sejahtera"),
    ("OP06", "Koperasi Sipahutar Kopi Makmur"),
    ("OP07", "PT Danau Toba Coffee Trading"),
    ("OP08", "Koperasi Dolok Berkah Bersama"),
]

DOC_COLS = ["doc_id", "lot_id", "doc_type", "version", "operator_id", "issue_date",
            "valid_until", "signed", "quality", "hs_code", "country", "quantity_kg",
            "risk_level", "reference_date"]

REQUIRED = ["dds_statement", "commercial_invoice", "supplier_buyer_info", "production_record",
            "deforestation_evidence", "legality_land", "legality_env", "legality_labour_tax",
            "risk_assessment"]

# (defect, jumlah lot, status yang diharapkan)
PLAN = [
    ("none", 163, "VALID"),
    ("valid_non_negligible_with_mitigation", 20, "VALID"),
    ("valid_resubmitted", 30, "VALID"),
    ("valid_boundary", 10, "VALID"),
    ("missing_doc", 15, "INCOMPLETE"),
    ("unsigned_dds", 8, "INVALID_DOCUMENT"),
    ("expired_legality", 8, "INVALID_DOCUMENT"),
    ("low_quality", 5, "INVALID_DOCUMENT"),
    ("wrong_hs_code", 5, "INVALID_DOCUMENT"),
    ("cutoff_violation", 5, "INVALID_DOCUMENT"),
    ("quantity_mismatch", 8, "INCONSISTENT"),
    ("operator_mismatch", 5, "INCONSISTENT"),
    ("mass_balance", 5, "INCONSISTENT"),
    ("date_order", 5, "INCONSISTENT"),
    ("non_negligible_no_mitigation", 5, "INCONSISTENT"),
    ("country_mismatch", 3, "INCONSISTENT"),
]


def d_between(rng, a: date, b: date) -> date:
    return a + timedelta(days=rng.randint(0, (b - a).days))


def base_lot(rng, lot_id):
    op = rng.choice(OPERATORS)[0]
    as_of = date(2026, 8, 15) + timedelta(days=rng.randint(0, 44))
    dds = as_of - timedelta(days=rng.randint(1, 7))
    qty = 60 * rng.randint(100, 320)              # karung 60 kg; maks 19.200 kg (1 kontainer 20 ft)
    prod_d = dds - timedelta(days=rng.randint(30, 60))
    risk_d = dds - timedelta(days=rng.randint(6, 20))
    q = lambda: round(rng.uniform(0.85, 0.99), 2)

    def row(dtype, **kw):
        r = {c: "" for c in DOC_COLS}
        r.update(lot_id=lot_id, doc_type=dtype, version=1, quality=q(), signed=0)
        r.update(kw)
        return r

    docs = {
        "dds_statement": row("dds_statement", operator_id=op, issue_date=dds, signed=1,
                             hs_code="0901", country="ID", quantity_kg=qty),
        "commercial_invoice": row("commercial_invoice", operator_id=op,
                                  issue_date=dds - timedelta(days=rng.randint(2, 9)),
                                  hs_code="0901.11", quantity_kg=qty),
        "supplier_buyer_info": row("supplier_buyer_info", operator_id=op,
                                   issue_date=dds - timedelta(days=rng.randint(7, 20))),
        "production_record": row("production_record", issue_date=prod_d, country="ID",
                                 quantity_kg=qty + 60 * rng.randint(0, 10)),
        "deforestation_evidence": row("deforestation_evidence",
                                      issue_date=dds - timedelta(days=rng.randint(10, 28)),
                                      country="ID",
                                      reference_date=d_between(rng, date(2020, 1, 1), date(2020, 12, 30))),
        "legality_land": row("legality_land", issue_date=d_between(rng, date(2023, 1, 1), date(2025, 6, 30)),
                             country="ID", valid_until=d_between(rng, date(2028, 1, 1), date(2031, 12, 31))),
        "legality_env": row("legality_env", issue_date=d_between(rng, date(2023, 1, 1), date(2025, 6, 30)),
                            valid_until=d_between(rng, date(2027, 6, 1), date(2029, 12, 31))),
        "legality_labour_tax": row("legality_labour_tax",
                                   issue_date=d_between(rng, date(2024, 1, 1), date(2025, 9, 30)),
                                   valid_until=d_between(rng, date(2027, 3, 1), date(2028, 12, 31))),
        "risk_assessment": row("risk_assessment", issue_date=risk_d, risk_level="negligible"),
    }
    if rng.random() < 0.6:
        docs["certification"] = row("certification", operator_id=op,
                                    issue_date=d_between(rng, date(2024, 1, 1), date(2025, 9, 30)),
                                    valid_until=d_between(rng, date(2027, 1, 1), date(2028, 12, 31)))
    return docs, dict(op=op, as_of=as_of, dds=dds, qty=qty, risk_d=risk_d)


def apply_defect(kind, rng, docs, m):
    extra = []
    other_op = lambda: rng.choice([o for o, _ in OPERATORS if o != m["op"]])
    if kind == "missing_doc":
        del docs[rng.choice(REQUIRED)]
    elif kind == "unsigned_dds":
        docs["dds_statement"]["signed"] = 0
    elif kind == "expired_legality":
        d = docs[rng.choice(["legality_land", "legality_env", "legality_labour_tax"])]
        d["valid_until"] = m["as_of"] - timedelta(days=rng.randint(5, 200))
    elif kind == "low_quality":
        docs[rng.choice(REQUIRED)]["quality"] = round(rng.uniform(0.35, 0.55), 2)
    elif kind == "wrong_hs_code":
        docs["commercial_invoice"]["hs_code"] = "1801.00"
    elif kind == "cutoff_violation":
        docs["deforestation_evidence"]["reference_date"] = d_between(rng, date(2021, 2, 1), date(2022, 6, 30))
    elif kind == "quantity_mismatch":
        docs["commercial_invoice"]["quantity_kg"] = m["qty"] + 60 * rng.randint(5, 30)
    elif kind == "operator_mismatch":
        docs["supplier_buyer_info"]["operator_id"] = other_op()
    elif kind == "mass_balance":
        docs["production_record"]["quantity_kg"] = m["qty"] - 60 * rng.randint(1, 20)
    elif kind == "date_order":
        docs["risk_assessment"]["issue_date"] = m["dds"] + timedelta(days=1)
    elif kind == "non_negligible_no_mitigation":
        docs["risk_assessment"]["risk_level"] = "non_negligible"
    elif kind == "country_mismatch":
        docs["production_record"]["country"] = "VN"
    elif kind == "valid_non_negligible_with_mitigation":
        docs["risk_assessment"]["risk_level"] = "non_negligible"
        r = {c: "" for c in DOC_COLS}
        r.update(lot_id=docs["risk_assessment"]["lot_id"], doc_type="risk_mitigation", version=1,
                 signed=0, quality=round(rng.uniform(0.85, 0.99), 2),
                 issue_date=m["risk_d"] + timedelta(days=rng.randint(1, 4)))
        docs["risk_mitigation"] = r
    elif kind == "valid_boundary":
        docs["deforestation_evidence"]["reference_date"] = date(2020, 12, 31)
        docs["production_record"]["quantity_kg"] = m["qty"]
    elif kind == "valid_resubmitted":
        t = rng.choice(["dds_statement", "commercial_invoice", "supplier_buyer_info", "production_record"])
        cur = docs[t]
        v1 = dict(cur)
        v1["version"] = 1
        v1["quality"] = 0.72
        v1["issue_date"] = cur["issue_date"] - timedelta(days=rng.randint(2, 10))
        if t in ("dds_statement", "commercial_invoice"):
            v1["quantity_kg"] = m["qty"] + 60 * rng.randint(5, 20)
        elif t == "supplier_buyer_info":
            v1["operator_id"] = other_op()
        else:
            v1["quantity_kg"] = m["qty"] - 60 * rng.randint(1, 20)
        cur["version"] = 2
        extra.append(v1)
    return extra


def main():
    rng = random.Random(SEED)
    plan = [(k, s) for k, n, s in PLAN for _ in range(n)]
    rng.shuffle(plan)
    lots, docs_out, labels = [], [], []
    seq = 0
    for i, (kind, status) in enumerate(plan, 1):
        lot_id = f"LOT-2026-{i:04d}"
        docs, meta = base_lot(rng, lot_id)
        extra = apply_defect(kind, rng, docs, meta)
        lots.append((lot_id, meta["as_of"].isoformat()))
        labels.append((lot_id, status, kind))
        for r in list(docs.values()) + extra:
            seq += 1
            r["doc_id"] = f"DOC-{seq:05d}"
            docs_out.append(r)

    def write(name, header, rows):
        with open(OUT / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(header)
            w.writerows(rows)

    write("operators.csv", ["operator_id", "operator_name"], OPERATORS)
    write("lots.csv", ["lot_id", "as_of"], lots)
    write("labels.csv", ["lot_id", "expected_status", "defect"], labels)
    write("documents.csv", DOC_COLS,
          [[(v.isoformat() if isinstance(v, date) else v) for v in (r[c] for c in DOC_COLS)] for r in docs_out])
    print(f"lots={len(lots)} documents={len(docs_out)} operators={len(OPERATORS)}")


if __name__ == "__main__":
    main()
