"""Model data & katalog persyaratan dokumen EUDR (TobaTrace AI - Milestone 2).

Ruang lingkup: HANYA validasi kelengkapan & konsistensi dokumen.
Komputasi lokasi/geolokasi sengaja dikeluarkan dari modul ini.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple

# Cut-off date EUDR: komoditas tidak boleh berasal dari lahan yang
# terdeforestasi setelah tanggal ini (Reg. (EU) 2023/1115).
CUTOFF_DATE = date(2020, 12, 31)
COFFEE_HS_PREFIX = "0901"  # HS Chapter 09.01 = kopi


@dataclass(frozen=True)
class Document:
    """Satu dokumen hasil ekstraksi (metadata) yang diajukan staf ekspor."""

    doc_id: str
    doc_type: str
    lot_id: str
    issue_date: date
    operator_name: str = ""
    hs_code: Optional[str] = None
    country: Optional[str] = None
    quantity_kg: Optional[float] = None
    valid_until: Optional[date] = None
    signed: bool = False
    quality: float = 1.0          # skor kepercayaan ekstraksi/OCR, 0..1
    version: int = 1
    risk_level: Optional[str] = None      # "negligible" | "non_negligible"
    reference_date: Optional[date] = None  # tanggal baseline bukti bebas-deforestasi


@dataclass(frozen=True)
class SlotSpec:
    """Satu 'slot' dokumen wajib/opsional = satu variabel keputusan CSP."""

    name: str
    doc_type: str
    required: bool
    requires_signature: bool
    required_fields: Tuple[str, ...]
    description: str
    legal_basis: str
    conditional: bool = False  # wajib hanya jika kondisi tertentu terpenuhi


SLOTS: Tuple[SlotSpec, ...] = (
    SlotSpec("dds_statement", "dds_statement", True, True,
             ("operator_name", "hs_code", "country", "quantity_kg", "issue_date"),
             "Due Diligence Statement (pernyataan uji kelayakan) per lot",
             "Pasal 4 & Annex II"),
    SlotSpec("commercial_invoice", "commercial_invoice", True, False,
             ("operator_name", "hs_code", "quantity_kg"),
             "Faktur komersial (deskripsi produk, HS code, kuantitas)",
             "Pasal 9 ayat (1)"),
    SlotSpec("supplier_buyer_info", "supplier_buyer_info", True, False,
             ("operator_name",),
             "Identitas pemasok & pembeli (nama, alamat, email)",
             "Pasal 9 ayat (1)"),
    SlotSpec("production_record", "production_record", True, False,
             ("country", "quantity_kg"),
             "Catatan produksi/panen (negara, tanggal, volume)",
             "Pasal 9 ayat (1)"),
    SlotSpec("deforestation_evidence", "deforestation_evidence", True, False,
             ("country", "reference_date"),
             "Bukti bebas-deforestasi (baseline <= 31 Des 2020)",
             "Pasal 3, 9 ayat (1)"),
    SlotSpec("legality_land", "legality_land", True, False,
             ("country", "valid_until"),
             "Bukti hak penggunaan lahan (mis. STDB/sertifikat lahan)",
             "Pasal 2 (definisi 'relevant legislation'), Pasal 9"),
    SlotSpec("legality_env", "legality_env", True, False,
             ("valid_until",),
             "Bukti kepatuhan perlindungan lingkungan (mis. SPPL/izin lingkungan)",
             "Pasal 2, Pasal 9"),
    SlotSpec("legality_labour_tax", "legality_labour_tax", True, False,
             ("valid_until",),
             "Bukti ketenagakerjaan/pajak/kepabeanan (mis. NIB, NPWP)",
             "Pasal 2, Pasal 9"),
    SlotSpec("risk_assessment", "risk_assessment", True, False,
             ("risk_level",),
             "Dokumen penilaian risiko",
             "Pasal 10"),
    SlotSpec("risk_mitigation", "risk_mitigation", False, False,
             (),
             "Dokumen mitigasi risiko (wajib jika risiko non-negligible)",
             "Pasal 11", conditional=True),
    SlotSpec("certification", "certification", False, False,
             ("valid_until",),
             "Sertifikasi sukarela pendukung (Rainforest Alliance/Organik)",
             "Pendukung (bukan pengganti uji kelayakan)"),
)

SLOT_BY_NAME = {s.name: s for s in SLOTS}
