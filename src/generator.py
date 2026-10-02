"""Pembangkit data sintetis: paket valid, near-miss distraktor, dan kasus rusak."""
from __future__ import annotations

import random
from dataclasses import replace
from datetime import date, timedelta
from typing import List

from .models import SLOTS, Document

OPERATOR = "Koperasi Kopi Toba Lestari"
DDS_DATE = date(2026, 11, 20)
AS_OF = date(2026, 11, 25)


def make_valid_package(lot_id: str = "LOT-001", *, quantity: float = 18000.0) -> List[Document]:
    d = DDS_DATE
    mk = lambda **k: Document(lot_id=lot_id, operator_name=OPERATOR, **k)
    return [
        mk(doc_id=f"{lot_id}-DDS", doc_type="dds_statement", issue_date=d, hs_code="0901.11",
           country="ID", quantity_kg=quantity, signed=True),
        mk(doc_id=f"{lot_id}-INV", doc_type="commercial_invoice", issue_date=d - timedelta(5),
           hs_code="090111", quantity_kg=quantity),
        mk(doc_id=f"{lot_id}-SBI", doc_type="supplier_buyer_info", issue_date=d - timedelta(10)),
        mk(doc_id=f"{lot_id}-PRD", doc_type="production_record", issue_date=d - timedelta(21),
           country="ID", quantity_kg=quantity + 500),
        mk(doc_id=f"{lot_id}-DEF", doc_type="deforestation_evidence", issue_date=d - timedelta(15),
           country="ID", reference_date=date(2020, 11, 30)),
        mk(doc_id=f"{lot_id}-LND", doc_type="legality_land", issue_date=date(2024, 3, 1),
           country="ID", valid_until=date(2029, 12, 31)),
        mk(doc_id=f"{lot_id}-ENV", doc_type="legality_env", issue_date=date(2024, 6, 1),
           valid_until=date(2028, 6, 30)),
        mk(doc_id=f"{lot_id}-LTX", doc_type="legality_labour_tax", issue_date=date(2025, 1, 15),
           valid_until=date(2027, 12, 31)),
        mk(doc_id=f"{lot_id}-RSK", doc_type="risk_assessment", issue_date=d - timedelta(12),
           risk_level="negligible"),
        mk(doc_id=f"{lot_id}-CRT", doc_type="certification", issue_date=date(2025, 5, 1),
           valid_until=date(2027, 5, 1)),
    ]


_MUTATIONS = ["unsigned", "expired", "low_quality", "wrong_operator", "qty_off",
              "late_date", "wrong_country", "wrong_hs", "dup_lower_quality"]


def _mutate(doc: Document, kind: str, tag: str) -> Document:
    new_id = f"{doc.doc_id}-x{tag}"
    if kind == "unsigned":
        return replace(doc, doc_id=new_id, signed=False)
    if kind == "expired":
        return replace(doc, doc_id=new_id, valid_until=date(2025, 1, 1))
    if kind == "low_quality":
        return replace(doc, doc_id=new_id, quality=0.30)
    if kind == "wrong_operator":
        return replace(doc, doc_id=new_id, operator_name="PT Kopi Lain")
    if kind == "qty_off":
        q = doc.quantity_kg
        return replace(doc, doc_id=new_id, quantity_kg=None if q is None else q * 1.2)
    if kind == "late_date":
        return replace(doc, doc_id=new_id, issue_date=doc.issue_date + timedelta(400))
    if kind == "wrong_country":
        return replace(doc, doc_id=new_id, country=None if doc.country is None else "VN")
    if kind == "wrong_hs":
        return replace(doc, doc_id=new_id, hs_code=None if doc.hs_code is None else "1801.00")
    return replace(doc, doc_id=new_id, quality=0.75, version=0)  # duplikat sah, mutu lebih rendah


def add_distractors(docs: List[Document], per_slot: int, seed: int = 0,
                    valid_dup_ratio: float = 0.3) -> List[Document]:
    """Tambah `per_slot` kandidat near-miss per slot; sebagian duplikat sah bermutu rendah."""
    rng = random.Random(seed)
    out = list(docs)
    for i, doc in enumerate(docs):
        for j in range(per_slot):
            kind = "dup_lower_quality" if rng.random() < valid_dup_ratio else rng.choice(_MUTATIONS)
            out.append(_mutate(doc, kind, f"{j}"))
    return out


def break_slot(docs: List[Document], slot_type: str, how: str = "remove") -> List[Document]:
    """Kasus rusak: hapus / ubah dokumen bertipe tertentu."""
    if how == "remove":
        return [d for d in docs if d.doc_type != slot_type]
    return [_mutate(d, how, "b") if d.doc_type == slot_type else d for d in docs]
