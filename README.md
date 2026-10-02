# TobaTrace — EUDR Compliance Copilot

> Proyek PjBL mata kuliah **10S3001 Kecerdasan Buatan**, Program Studi Sarjana Sistem Informasi, Institut Teknologi Del — Semester Gasal 2026/2027.

TobaTrace adalah purwarupa copilot untuk membantu koperasi dan eksportir kopi
arabika Sumatera menyiapkan kepatuhan ekspor terhadap EU Deforestation
Regulation (EUDR). Repositori saat ini memuat baseline pencarian rute dari
Milestone 1 dan validasi paket dokumen ekspor per lot dari Milestone 2.

## Status Milestone

| Milestone | Status | Cakupan |
|---|---|---|
| M1 (W02) | Selesai | Problem framing, PEAS, dan baseline pencarian rute UCS/A*. |
| M2 (W04) | Selesai | Solver kendala dokumen EUDR berbasis CSP, dataset sintetis, tes, dan benchmark. |
| M3 (W07) | Belum dikerjakan | Knowledge base dan vector search (ChromaDB). |
| M4 (W11) | Belum dikerjakan | Pipeline AI agent (LLM, RAG, dan MCP). |
| M5 (W13) | Belum dikerjakan | Antarmuka web interaktif (Gradio). |

## Cakupan validasi dokumen

Solver memodelkan satu variabel untuk setiap slot dokumen EUDR dan memilih
kandidat dokumen yang memenuhi validasi individual serta konsistensi antar
dokumen. Mesin CSP menyediakan AC-3, backtracking, MRV, forward checking, dan
branch and bound.

Pemeriksaan meliputi kelengkapan slot, tanda tangan DDS, mutu ekstraksi,
masa berlaku, format dan kecocokan HS code, negara, kuantitas, urutan tanggal,
operator, neraca massa, serta mitigasi risiko bersyarat. Hasil validasi
mencakup `VALID`, `INCOMPLETE`, `INVALID_DOCUMENT`, `INCONSISTENT`, dan
`TIMEOUT`.

Ruang lingkup Milestone 2 **hanya validasi dokumen**. Komputasi dan validasi
geolokasi tidak diimplementasikan. Katalog aturan di
`data/reference/eudr_official_dds_validation_rules.csv` mencatat aturan yang
dimodelkan, dimodelkan sebagian, dan di luar cakupan; solver bukan implementasi
lengkap seluruh validasi sistem EUDR.

## Struktur repositori

```text
src/
  search_baseline.py   # baseline UCS dan A* (M1)
  models.py            # dataclass dokumen dan katalog slot EUDR
  csp_engine.py        # mesin CSP generik: AC-3 dan pencarian
  solver.py            # validasi paket dokumen EUDR
  generator.py         # paket sintetis untuk uji solver
  dataset.py           # pemuat, pemeriksa integritas, dan evaluasi dataset
data/
  operators.csv        # operator fiktif
  lots.csv             # lot dan tanggal validasi
  documents.csv        # dokumen sintetis
  labels.csv           # label kebenaran untuk evaluasi
  template_data_riil/  # template header untuk data mitra
  reference/           # katalog aturan validasi resmi EU
tests/                 # tes baseline, mesin CSP, solver, dan dataset
benchmarks/            # benchmark sensitivitas dan evaluasi dataset
docs/                  # log, grafik, dan hasil evaluasi benchmark
```

## Menyiapkan environment

Repositori memakai Python 3.11 atau lebih baru dan `uv`:

```bash
git clone https://github.com/PaulaTambunan/TobaTrace-AI.git
cd TobaTrace-AI
uv sync
```

Alternatif menggunakan `pip`:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Menjalankan dan menguji

Jalankan semua tes:

```bash
uv run pytest -q
```

Periksa integritas dan distribusi status dataset:

```bash
uv run python -m src.dataset
```

Pada dataset sintetis yang disertakan, hasil yang diharapkan adalah integritas
`BERSIH` dengan 300 lot: 223 `VALID`, 31 `INVALID_DOCUMENT`, 31
`INCONSISTENT`, dan 15 `INCOMPLETE`.

Evaluasi dataset terhadap label:

```bash
uv run --with matplotlib python -m benchmarks.eval_dataset
```

Jalankan benchmark sensitivitas solver dan hasilkan grafik, JSON, serta log di
`docs/`:

```bash
uv run --with matplotlib python -m benchmarks.run_sensitivity
```

Jumlah simpul dan revisi AC-3 dapat dibandingkan antarmesin; waktu benchmark
bervariasi menurut perangkat.

Contoh menjalankan solver pada satu paket sintetis:

```python
from src.generator import AS_OF, make_valid_package
from src.solver import validate_package

report = validate_package(make_valid_package(), as_of=AS_OF)
print(report.summary())
```

## Dataset dan privasi

CSV dalam `data/` adalah **data sintetis deterministik** (seed 42), bukan data
transaksi eksportir nyata. Operator dan nilai lot bersifat fiktif. Label pada
`labels.csv` digunakan untuk mengukur hasil solver. Untuk data mitra, gunakan
template di `data/template_data_riil/`, anonimkan identitas pribadi, dan jangan
unggah dokumen transaksi asli atau rahasia ke repositori publik. Dataset tanpa
label dapat diperiksa dengan memberikan path folder ke `src.dataset`.

## Milestone 1: problem framing dan PEAS

Permasalahan awal proyek adalah membantu koperasi merencanakan rute logistik
kopi dari lokasi rantai pasok menuju Pelabuhan Belawan dengan biaya/jarak yang
lebih efisien dan keputusan yang dapat diaudit. Baseline M1 memodelkan jaringan
sebagai graf dan membandingkan Uniform Cost Search (UCS) dengan A*.

| Elemen PEAS | Spesifikasi |
|---|---|
| **Performance measure** | Rute valid, biaya/jarak total minimum, biaya A* konsisten dengan UCS, dan jumlah simpul tercatat. |
| **Environment** | Kebun, pengumpul, pengolahan, gudang, hub logistik, dan pelabuhan; graf diketahui dan baseline bersifat deterministik. |
| **Actuators** | Menghasilkan rute rekomendasi, total biaya, dan peringatan saat rute tidak ditemukan. |
| **Sensors** | Graf adjacency, koordinat lokasi, biaya/jarak edge, titik awal, dan titik tujuan. |

Formulasi baseline: keadaan adalah lokasi, aksi adalah perpindahan ke tetangga,
transisi mengikuti edge graf, goal adalah Pelabuhan Belawan, dan biaya edge
mewakili estimasi jarak/biaya logistik. Validasi dokumen EUDR ditambahkan pada
M2 sebagai kemampuan terpisah; geolokasi belum dihitung oleh solver dokumen.

## Tim

| Nama | NIM | Peran |
|---|---|---|
| Joice | 12S24020 | AI Architecture & Model Lead |
| Paula Tambunan | 12S24025 | Data & Knowledge Engineer; QA, Evaluation & Ethics Lead |
| Ester | 12S24050 | Integration & Interface Engineer |

Laporan akademik dikumpulkan melalui ECourse sesuai format tugas. Dokumen
laporan tidak menjadi dependensi runtime.

## Lisensi

Untuk keperluan akademik; lihat berkas [LICENSE](./LICENSE).
