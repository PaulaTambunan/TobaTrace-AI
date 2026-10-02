"""Solver validasi paket dokumen EUDR sebagai CSP (AC-3 + Backtracking MRV).

Variabel   : satu variabel per slot dokumen (lihat models.SLOTS)
Domain     : kandidat dokumen yang lolos filter unary (+ None bila slot opsional)
Batasan    : unary (per dokumen) dan biner (konsistensi antar dokumen)
Keluaran   : ValidationReport (VALID / INCOMPLETE / INVALID_DOCUMENT /
             INCONSISTENT / TIMEOUT) beserta diagnosis penyebab.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Iterable, List, Optional, Tuple

from .csp_engine import CSP, SearchStats, ac3, backtracking_search
from .models import (COFFEE_HS_PREFIX, CUTOFF_DATE, SLOT_BY_NAME, SLOTS,
                     Document, SlotSpec)

VALID = "VALID"
INCOMPLETE = "INCOMPLETE"              # slot wajib tidak punya dokumen sama sekali
INVALID_DOCUMENT = "INVALID_DOCUMENT"  # dokumen ada, tetapi semuanya cacat
INCONSISTENT = "INCONSISTENT"          # dokumen sah sendiri-sendiri, saling bertentangan
TIMEOUT = "TIMEOUT"                    # batas simpul pencarian terlampaui


# ----------------------------------------------------------------- util
def _norm_name(s: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _norm_hs(s: Optional[str]) -> str:
    return re.sub(r"\D", "", s or "")


def _hs_compatible(a: Optional[str], b: Optional[str]) -> bool:
    """DDS resmi memuat hsHeading 4 digit, faktur biasanya 6-8 digit:
    bandingkan pada panjang terpendek (minimal 4 digit)."""
    x, y = _norm_hs(a), _norm_hs(b)
    n = min(len(x), len(y))
    return n >= 4 and x[:n] == y[:n]


def _pair(fn):
    """Bungkus predikat: pasangan yang melibatkan None (slot kosong) dianggap sah."""
    def wrapped(x, y):
        if x is None or y is None:
            return True
        return fn(x, y)
    return wrapped


# ------------------------------------------------------------- laporan
@dataclass
class Issue:
    slot: str
    kind: str        # MISSING | INVALID | INCONSISTENT | WARNING
    message: str
    severity: str = "error"


@dataclass
class ValidationReport:
    status: str
    assignment: Dict[str, Optional[str]] = field(default_factory=dict)
    issues: List[Issue] = field(default_factory=list)
    completeness: float = 0.0
    score: float = 0.0
    stats: SearchStats = field(default_factory=SearchStats)

    @property
    def is_valid(self) -> bool:
        return self.status == VALID

    def summary(self) -> str:
        lines = [f"Status: {self.status} | Kelengkapan slot wajib: {self.completeness:.0%}"]
        for i in self.issues:
            lines.append(f"  [{i.severity}] {i.slot}: {i.message}")
        return "\n".join(lines)


# ------------------------------------------------- batasan unary (per dokumen)
def unary_rejections(doc: Document, slot: SlotSpec, *, as_of: date,
                     min_quality: float, lot_id: Optional[str]) -> List[str]:
    reasons: List[str] = []
    if lot_id is not None and doc.lot_id != lot_id:
        reasons.append(f"lot '{doc.lot_id}' != lot yang divalidasi '{lot_id}'")
    for f in slot.required_fields:
        v = getattr(doc, f, None)
        if v is None or (isinstance(v, str) and not v.strip()):
            reasons.append(f"field wajib kosong: {f}")
    if doc.issue_date > as_of:
        reasons.append(f"tanggal terbit {doc.issue_date.isoformat()} di masa depan "
                       f"(setelah tanggal validasi {as_of.isoformat()})")
    if slot.requires_signature and not doc.signed:
        reasons.append("belum ditandatangani")
    if doc.quality < min_quality:
        reasons.append(f"kualitas ekstraksi rendah ({doc.quality:.2f} < {min_quality:.2f})")
    if doc.valid_until is not None and doc.valid_until < as_of:
        reasons.append(f"kedaluwarsa ({doc.valid_until.isoformat()})")
    if doc.quantity_kg is not None and doc.quantity_kg <= 0:
        reasons.append("kuantitas harus > 0")
    if doc.hs_code is not None and not _norm_hs(doc.hs_code).startswith(COFFEE_HS_PREFIX):
        reasons.append(f"HS code {doc.hs_code} bukan kopi ({COFFEE_HS_PREFIX}xx)")
    if slot.name == "deforestation_evidence" and doc.reference_date is not None \
            and doc.reference_date > CUTOFF_DATE:
        reasons.append(f"tanggal baseline {doc.reference_date.isoformat()} melewati "
                       f"cut-off {CUTOFF_DATE.isoformat()}")
    if slot.name == "risk_assessment" and doc.risk_level not in (None, "negligible", "non_negligible"):
        reasons.append(f"risk_level tidak dikenal: {doc.risk_level}")
    return reasons


# ------------------------------------------------ batasan biner (antar dokumen)
def _add_binary_constraints(csp: CSP, qty_tolerance: float, check_lot: bool) -> None:
    add = lambda a, b, fn, name: csp.add_constraint(a, b, _pair(fn), name)

    if check_lot:
        for s in SLOTS[1:]:
            add("dds_statement", s.name, lambda x, y: x.lot_id == y.lot_id, "lot_sama")

    add("dds_statement", "commercial_invoice",
        lambda x, y: _hs_compatible(x.hs_code, y.hs_code), "hs_code_sama")
    for a, b in (("dds_statement", "commercial_invoice"),
                 ("dds_statement", "supplier_buyer_info"),
                 ("commercial_invoice", "supplier_buyer_info"),
                 ("certification", "supplier_buyer_info")):
        add(a, b, lambda x, y: _norm_name(x.operator_name) == _norm_name(y.operator_name),
            "operator_sama")

    add("dds_statement", "commercial_invoice",
        lambda x, y: abs(x.quantity_kg - y.quantity_kg)
        <= qty_tolerance * max(x.quantity_kg, y.quantity_kg), "kuantitas_sama")
    add("production_record", "dds_statement",
        lambda p, d: p.quantity_kg >= d.quantity_kg, "neraca_massa_produksi>=ekspor")

    for a, b in (("dds_statement", "production_record"),
                 ("dds_statement", "legality_land"),
                 ("production_record", "deforestation_evidence"),
                 ("production_record", "legality_land")):
        add(a, b, lambda x, y: _norm_name(x.country) == _norm_name(y.country),
            "negara_produksi_sama")

    # urutan tanggal & masa berlaku
    add("risk_assessment", "dds_statement", lambda r, d: r.issue_date <= d.issue_date,
        "penilaian_risiko_sebelum_dds")
    add("production_record", "risk_assessment", lambda p, r: p.issue_date <= r.issue_date,
        "produksi_sebelum_penilaian_risiko")
    add("production_record", "dds_statement", lambda p, d: p.issue_date <= d.issue_date,
        "produksi_sebelum_dds")
    add("deforestation_evidence", "dds_statement", lambda e, d: e.issue_date <= d.issue_date,
        "bukti_sebelum_dds")
    add("risk_mitigation", "dds_statement", lambda m, d: m.issue_date <= d.issue_date,
        "mitigasi_sebelum_dds")
    add("risk_assessment", "risk_mitigation", lambda r, m: r.issue_date <= m.issue_date,
        "mitigasi_setelah_penilaian_risiko")
    for s in ("legality_land", "legality_env", "legality_labour_tax", "certification"):
        add(s, "dds_statement",
            lambda x, d: x.issue_date <= d.issue_date and
            (x.valid_until is None or x.valid_until >= d.issue_date),
            "masa_berlaku_mencakup_tanggal_dds")

    # mitigasi wajib bila risiko non-negligible (melibatkan nilai None)
    csp.add_constraint(
        "risk_assessment", "risk_mitigation",
        lambda r, m: not (r is not None and r.risk_level == "non_negligible" and m is None),
        "mitigasi_wajib_jika_risiko_non_negligible")


def _score(_var: str, doc: Optional[Document]) -> float:
    return 0.0 if doc is None else doc.quality + 0.001 * doc.version


# ---------------------------------------------------------------- API utama
def validate_package(
    documents: Iterable[Document],
    *,
    lot_id: Optional[str] = None,
    as_of: Optional[date] = None,
    min_quality: float = 0.60,
    qty_tolerance: float = 0.005,
    use_ac3: bool = True,
    use_mrv: bool = True,
    use_fc: bool = True,
    optimize: bool = True,
    node_limit: Optional[int] = 200_000,
) -> ValidationReport:
    """Validasi satu paket dokumen ekspor (satu lot) terhadap katalog EUDR."""
    as_of = as_of or date.today()
    docs = list(documents)
    report = ValidationReport(status=VALID)
    csp = CSP()
    required_ok, required_total = 0, 0

    # 1. domain per slot + filter unary
    for slot in SLOTS:
        cands = [d for d in docs if d.doc_type == slot.doc_type]
        valid, rejected = [], []
        for d in cands:
            r = unary_rejections(d, slot, as_of=as_of, min_quality=min_quality, lot_id=lot_id)
            (rejected if r else valid).append((d, r))
        domain: List[Optional[Document]] = [d for d, _ in valid]
        if slot.required:
            required_total += 1
            if domain:
                required_ok += 1
            elif not cands:
                report.issues.append(Issue(slot.name, "MISSING",
                                           f"dokumen wajib tidak ditemukan ({slot.description})"))
            else:
                detail = "; ".join(f"{d.doc_id}: {', '.join(r)}" for d, r in rejected)
                report.issues.append(Issue(slot.name, "INVALID",
                                           f"semua kandidat cacat -> {detail}"))
        else:
            domain.append(None)
            for d, r in rejected:
                report.issues.append(Issue(slot.name, "WARNING",
                                           f"{d.doc_id} diabaikan: {', '.join(r)}", "warning"))
        csp.add_variable(slot.name, domain)

    report.completeness = required_ok / required_total if required_total else 1.0
    blocking = [i for i in report.issues if i.severity == "error"]
    if blocking:
        report.status = INCOMPLETE if any(i.kind == "MISSING" for i in blocking) \
            else INVALID_DOCUMENT
        return report

    # 2. batasan biner + AC-3
    _add_binary_constraints(csp, qty_tolerance, check_lot=(lot_id is None))
    doms = {k: list(v) for k, v in csp.domains.items()}
    if use_ac3 and not ac3(csp, doms, report.stats):
        var, other, cname = report.stats.wipeout
        report.status = INCONSISTENT
        report.issues.append(Issue(var, "INCONSISTENT",
                                   f"tidak ada dokumen '{var}' yang konsisten dengan "
                                   f"'{other}' (batasan: {cname})"))
        return report

    # 3. backtracking
    sol = backtracking_search(csp, doms, use_mrv=use_mrv, use_fc=use_fc, score=_score,
                              optimize=optimize, node_limit=node_limit, stats=report.stats)
    if report.stats.timed_out and sol is None:
        report.status = TIMEOUT
        report.issues.append(Issue("-", "INCONSISTENT",
                                   "batas simpul pencarian terlampaui sebelum solusi ditemukan"))
        return report
    if sol is None:
        report.status = INCONSISTENT
        report.issues.append(Issue("-", "INCONSISTENT",
                                   "tiap dokumen sah, namun tidak ada kombinasi yang konsisten "
                                   "(konflik global antar dokumen)"))
        return report

    report.assignment = {k: (v.doc_id if v else None) for k, v in sol.items()}
    report.score = sum(_score(k, v) for k, v in sol.items())
    return report


def validate_batch(docs_by_lot: Dict[str, List[Document]], **kw) -> Dict[str, ValidationReport]:
    """Validasi banyak lot; tiap lot adalah CSP independen."""
    return {lot: validate_package(docs, lot_id=lot, **kw) for lot, docs in docs_by_lot.items()}
