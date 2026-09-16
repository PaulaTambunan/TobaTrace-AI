# TobaTrace — Sistem Copilot Cerdas Kepatuhan Ekspor & Ketertelusuran Kopi Sumatera (EUDR Compliance Copilot)

> Tugas Mata Kuliah **10S3001 - Kecerdasan Buatan (Artificial Intelligence)**
> Program Studi Sarjana Sistem Informasi — Institut Teknologi Del
> Milestone Proyek Terpadu (PjBL) — Semester Gasal 2026/2027

## 1. Ringkasan Proyek

**TobaTrace** adalah purwarupa *Enterprise AI Assistant / Copilot* yang membantu
koperasi dan eksportir kopi arabika Sumatera (kawasan Danau Toba) memenuhi
persyaratan **EU Deforestation Regulation (EUDR)** — regulasi Uni Eropa yang mewajibkan
setiap lot kopi yang diekspor terbukti *deforestation-free*, legal, dan dapat
ditelusuri hingga titik geolokasi kebun petani.

Copilot ini akan (di milestone-milestone berikutnya) membantu staf ekspor:
- Menjawab pertanyaan berbasis dokumen kebijakan/SOP internal & regulasi EUDR (RAG).
- Menghitung rute logistik kopi dari kebun ke pelabuhan ekspor secara optimal (Search).
- Mengecek kelengkapan dokumen *Due Diligence Statement* (DDS) via *tool calling* (MCP).
- Menyajikan dashboard interaktif untuk staf non-teknis (Gradio).

## 2. Status Milestone

| Milestone | Status | Deskripsi |
|---|---|---|
| M1 (W02) | ✅ Selesai | Problem Framing, PEAS, Baseline Search (UCS/A*), Setup Repo |
| M2 (W04) | ⏳ Belum dikerjakan | Business Constraint Solver (CSP/GA) |
| M3 (W07) | ⏳ Belum dikerjakan | Knowledge Base & Vector Search (ChromaDB) |
| M4 (W11) | ⏳ Belum dikerjakan | AI Agent Pipeline (LLM + RAG + MCP) |
| M5 (W13) | ⏳ Belum dikerjakan | Web Interaktif (Gradio) |

## 3. Struktur Repositori

```
tobatrace-ai/
├── README.md
├── pyproject.toml          # dependensi & konfigurasi environment (Astral uv)
├── .gitignore
├── docs/
│   └── Laporan_Tugas1_Milestone1.pdf   # laporan problem framing & PEAS
├── src/
│   └── search_baseline.py  # modul UCS & A* Search (Milestone 1)
└── tests/
    └── test_search_baseline.py         # pytest unit test
```

## 4. Cara Menjalankan (Astral `uv`)

Proyek ini memakai [Astral `uv`](https://docs.astral.sh/uv/) sebagai package manager
Python modern untuk memastikan environment tim konsisten.

```bash
# 1. Install uv (sekali saja, jika belum ada)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone repositori
git clone https://github.com/<org-tim>/tobatrace-ai.git
cd tobatrace-ai

# 3. Sinkronisasi environment & dependensi
uv sync

# 4. Jalankan modul baseline search
uv run python src/search_baseline.py

# 5. Jalankan seluruh pengujian otomatis
uv run pytest -v
```

Jika `uv` belum tersedia, alternatif dengan `pip` standar:
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/search_baseline.py
pytest -v
```

## 5. Anggota Tim & Peran

| Nama | NIM | Peran |
|---|---|---|
| Joice | 12S24020 | AI Architecture & Model Lead |
| Paula Tambunan | 12S24025 | Data & Knowledge Engineer **+** QA, Evaluation & Ethics Lead |
| Ester | 12S24050 | Integration & Interface Engineer |

## 6. Lisensi

Proyek ini dibuat untuk keperluan akademik (tugas kuliah) — MIT License (lihat `LICENSE`).
