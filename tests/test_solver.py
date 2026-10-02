"""Pengujian validator dokumen EUDR: kasus normal & kasus ekstrem (edge cases)."""
from dataclasses import replace
from datetime import date, timedelta

import pytest

from src.generator import (AS_OF, add_distractors, break_slot, make_valid_package)
from src.solver import (INCOMPLETE, INCONSISTENT, INVALID_DOCUMENT, TIMEOUT, VALID,
                        validate_batch, validate_package)


def run(docs, **kw):
    kw.setdefault("as_of", AS_OF)
    return validate_package(docs, **kw)


def swap(docs, doc_type, **changes):
    return [replace(d, **changes) if d.doc_type == doc_type else d for d in docs]


# ------------------------------------------------------------ kasus normal
def test_complete_package_is_valid():
    r = run(make_valid_package())
    assert r.status == VALID and r.completeness == 1.0
    assert r.assignment["risk_mitigation"] is None
    assert r.assignment["dds_statement"] == "LOT-001-DDS"


def test_deterministic_result():
    docs = add_distractors(make_valid_package(), 5, seed=1)
    assert run(docs).assignment == run(docs).assignment


def test_optimal_choice_prefers_highest_quality_duplicate():
    docs = add_distractors(make_valid_package(), 8, seed=3, valid_dup_ratio=1.0)
    r = run(docs)
    assert r.status == VALID
    assert all(v is None or "-x" not in v for v in r.assignment.values())


# ---------------------------------------------------- dokumen hilang / cacat
def test_empty_input_reports_all_required_missing():
    r = run([])
    assert r.status == INCOMPLETE and r.completeness == 0.0
    assert len([i for i in r.issues if i.kind == "MISSING"]) == 9


@pytest.mark.parametrize("slot_type", ["dds_statement", "commercial_invoice",
                                       "legality_land", "risk_assessment"])
def test_each_missing_required_document_detected(slot_type):
    r = run(break_slot(make_valid_package(), slot_type))
    assert r.status == INCOMPLETE
    assert any(i.slot == slot_type and i.kind == "MISSING" for i in r.issues)


def test_unsigned_dds_rejected():
    r = run(swap(make_valid_package(), "dds_statement", signed=False))
    assert r.status == INVALID_DOCUMENT and "belum ditandatangani" in r.issues[0].message


def test_expired_legality_document_rejected():
    r = run(swap(make_valid_package(), "legality_env", valid_until=AS_OF - timedelta(1)))
    assert r.status == INVALID_DOCUMENT


def test_legality_expiring_exactly_today_is_still_valid():
    r = run(swap(make_valid_package(), "legality_labour_tax", valid_until=AS_OF))
    # valid_until == as_of lolos unary, tetapi harus >= tanggal DDS (2026-11-20) -> lolos
    assert r.status == VALID


def test_low_quality_extraction_rejected_and_threshold_boundary():
    assert run(swap(make_valid_package(), "commercial_invoice", quality=0.59)).status == INVALID_DOCUMENT
    assert run(swap(make_valid_package(), "commercial_invoice", quality=0.60)).status == VALID


def test_non_coffee_hs_code_rejected():
    r = run(swap(make_valid_package(), "commercial_invoice", hs_code="1801.00"))
    assert r.status == INVALID_DOCUMENT and "bukan kopi" in r.issues[0].message


def test_missing_required_field_rejected():
    r = run(swap(make_valid_package(), "dds_statement", operator_name=""))
    assert r.status == INVALID_DOCUMENT and "operator_name" in r.issues[0].message


def test_zero_or_negative_quantity_rejected():
    assert run(swap(make_valid_package(), "production_record", quantity_kg=0)).status == INVALID_DOCUMENT
    assert run(swap(make_valid_package(), "production_record", quantity_kg=-5)).status == INVALID_DOCUMENT


def test_future_dated_document_rejected():
    r = run(swap(make_valid_package(), "commercial_invoice", issue_date=AS_OF + timedelta(1)))
    assert r.status == INVALID_DOCUMENT and "masa depan" in r.issues[0].message


# ---------------------------------------------------- cut-off deforestasi
def test_baseline_exactly_on_cutoff_is_valid():
    assert run(swap(make_valid_package(), "deforestation_evidence",
                    reference_date=date(2020, 12, 31))).status == VALID


def test_baseline_one_day_after_cutoff_rejected():
    r = run(swap(make_valid_package(), "deforestation_evidence", reference_date=date(2021, 1, 1)))
    assert r.status == INVALID_DOCUMENT and "cut-off" in r.issues[0].message


# ---------------------------------------------------- inkonsistensi antar dokumen
def test_quantity_tolerance_boundary():
    docs = make_valid_package(quantity=20000.0)
    ok = swap(docs, "commercial_invoice", quantity_kg=20000.0 * 0.995)  # selisih tepat 0.5%
    bad = swap(docs, "commercial_invoice", quantity_kg=20000.0 * 0.99)
    assert run(ok).status == VALID
    r = run(bad)
    assert r.status == INCONSISTENT and "kuantitas_sama" in r.issues[-1].message


def test_operator_name_normalization():
    r = run(swap(make_valid_package(), "commercial_invoice",
                 operator_name="  koperasi kopi  TOBA lestari. "))
    assert r.status == VALID


def test_operator_mismatch_inconsistent():
    r = run(swap(make_valid_package(), "supplier_buyer_info", operator_name="PT Lain"))
    assert r.status == INCONSISTENT and "operator_sama" in r.issues[-1].message


def test_production_volume_below_export_violates_mass_balance():
    r = run(swap(make_valid_package(), "production_record", quantity_kg=10000.0))
    assert r.status == INCONSISTENT and "neraca_massa" in r.issues[-1].message


def test_production_volume_equal_to_export_is_valid():
    assert run(swap(make_valid_package(), "production_record", quantity_kg=18000.0)).status == VALID


def test_risk_assessment_after_dds_date_inconsistent():
    r = run(swap(make_valid_package(), "risk_assessment", issue_date=date(2026, 11, 21)))
    assert r.status == INCONSISTENT and "penilaian_risiko_sebelum_dds" in r.issues[-1].message


def test_legality_expires_before_dds_date_inconsistent():
    r = run(swap(make_valid_package(), "legality_land", valid_until=date(2026, 11, 22),
                 ), as_of=date(2026, 11, 21))
    assert r.status == VALID  # masih berlaku pada tanggal DDS 20 Nov
    r2 = run(swap(make_valid_package(), "legality_land", valid_until=date(2026, 11, 22)),
             as_of=date(2026, 11, 25))
    assert r2.status == INVALID_DOCUMENT  # sudah kedaluwarsa per as_of


def test_country_mismatch_inconsistent():
    r = run(swap(make_valid_package(), "production_record", country="VN"))
    assert r.status == INCONSISTENT and "negara_produksi_sama" in r.issues[-1].message


# ---------------------------------------------------- mitigasi risiko bersyarat
def _non_negligible(docs):
    return swap(docs, "risk_assessment", risk_level="non_negligible")


def test_non_negligible_risk_without_mitigation_inconsistent():
    r = run(_non_negligible(make_valid_package()))
    assert r.status == INCONSISTENT
    assert "mitigasi_wajib_jika_risiko_non_negligible" in r.issues[-1].message


def test_non_negligible_risk_with_mitigation_valid():
    base = _non_negligible(make_valid_package())
    mit = replace(base[0], doc_id="LOT-001-MIT", doc_type="risk_mitigation",
                  issue_date=date(2026, 11, 15), signed=False)
    r = run(base + [mit])
    assert r.status == VALID and r.assignment["risk_mitigation"] == "LOT-001-MIT"


def test_mitigation_before_risk_assessment_inconsistent():
    base = _non_negligible(make_valid_package())
    mit = replace(base[0], doc_id="M", doc_type="risk_mitigation", issue_date=date(2026, 11, 1))
    assert run(base + [mit]).status == INCONSISTENT


# ---------------------------------------------------- dokumen opsional
def test_expired_optional_certification_is_warning_not_error():
    r = run(swap(make_valid_package(), "certification", valid_until=date(2025, 1, 1)))
    assert r.status == VALID and r.assignment["certification"] is None
    assert any(i.severity == "warning" for i in r.issues)


def test_missing_optional_certification_is_valid():
    assert run(break_slot(make_valid_package(), "certification")).status == VALID


# ---------------------------------------------------- lot & batch
def test_lot_filter_ignores_other_lots_documents():
    docs = make_valid_package("LOT-001") + make_valid_package("LOT-002")
    r = run(docs, lot_id="LOT-002")
    assert r.status == VALID and r.assignment["dds_statement"] == "LOT-002-DDS"


def test_mixed_lots_without_filter_detected_as_inconsistent():
    docs = make_valid_package("LOT-001")
    docs = [replace(d, lot_id="LOT-999") if d.doc_type == "commercial_invoice" else d for d in docs]
    r = run(docs)
    assert r.status == INCONSISTENT and "lot_sama" in r.issues[-1].message


def test_batch_validation_reports_per_lot():
    by_lot = {"L1": make_valid_package("L1"),
              "L2": break_slot(make_valid_package("L2"), "dds_statement")}
    res = validate_batch(by_lot, as_of=AS_OF)
    assert res["L1"].status == VALID and res["L2"].status == INCOMPLETE


# ---------------------------------------------------- skala & konfigurasi solver
@pytest.mark.parametrize("cfg", [dict(use_ac3=True, use_mrv=True, use_fc=True),
                                 dict(use_ac3=False, use_mrv=True, use_fc=True),
                                 dict(use_ac3=True, use_mrv=False, use_fc=False),
                                 dict(use_ac3=False, use_mrv=False, use_fc=False)])
def test_all_solver_configs_agree_on_status(cfg):
    docs = add_distractors(make_valid_package(), 3, seed=5)
    assert run(docs, **cfg).status == VALID
    infeasible = [replace(d, issue_date=date(2026, 11, 22)) if d.doc_type == "risk_assessment" else d
                  for d in docs]
    assert run(infeasible, **cfg).status == INCONSISTENT


def test_large_candidate_pool_still_valid():
    r = run(add_distractors(make_valid_package(), 100, seed=7))
    assert r.status == VALID


def test_timeout_reported_when_node_limit_too_small():
    docs = add_distractors(make_valid_package(), 20, seed=2, valid_dup_ratio=1.0)
    r = run(docs, use_ac3=False, use_mrv=False, use_fc=False, optimize=False, node_limit=3)
    assert r.status == TIMEOUT


def test_input_documents_not_mutated():
    docs = make_valid_package()
    snapshot = list(docs)
    run(docs)
    assert docs == snapshot
