# Dataset TobaTrace AI — paket dokumen ekspor kopi per lot

## Status data (baca dahulu)
**Data pada folder ini adalah data SINTETIS**, dibangkitkan oleh `generate_dataset.py` (seed 42).
Data paket dokumen ekspor milik eksportir nyata bersifat rahasia dan tidak dipublikasikan;
koperasi pada studi kasus ini juga fiktif. Struktur kolom dan aturan validasi mengikuti
dokumentasi resmi EU (EUDR Information System – Operator API Reference), tetapi **nilai-nilainya
bukan data transaksi nyata**. Jangan menyebutnya "data riil" pada laporan.

Keunggulan sintetis: setiap lot punya **label kebenaran (labels.csv)** sehingga akurasi solver
dapat diukur. Data riil tidak punya label seperti ini kecuali dilabeli manual oleh pakar.

## Tabel (3NF, tanpa redundansi)
| Berkas | Kunci | Isi |
|---|---|---|
| operators.csv | operator_id | 8 operator fiktif; nama disimpan **sekali** |
| lots.csv | lot_id | 300 lot + tanggal validasi `as_of` |
| documents.csv | doc_id; unik (lot_id, doc_type, version) | 2.903 dokumen, satu baris per dokumen/versi |
| labels.csv | lot_id | status yang diharapkan + jenis cacat (untuk evaluasi, terpisah dari input) |

Aturan format (sudah baku, tanpa normalisasi lanjutan): tanggal ISO `YYYY-MM-DD`; boolean `0/1`;
negara ISO-2 (`ID`); HS code `0901` (heading 4 digit, seperti pada DDS) atau `0901.11`
(faktur); kuantitas bilangan bulat kg; sel kosong = tidak berlaku (NULL).
Versi dokumen (`version`) adalah riwayat resubmisi yang sah, bukan duplikasi; ambil
`version` tertinggi bila hanya butuh yang terbaru.

## Komposisi
223 VALID (termasuk 10 kasus batas, 20 risiko non-negligible dengan mitigasi, 30 resubmisi),
15 INCOMPLETE, 31 INVALID_DOCUMENT, 31 INCONSISTENT. Satu cacat per lot agar label jelas.

## Pemakaian
```bash
python -m src.dataset                 # cek integritas + ringkasan status
python -m benchmarks.eval_dataset     # akurasi vs label + latensi
```
```python
from src.dataset import load_dataset, evaluate
ds = load_dataset()                   # ~25 ms; dokumen terindeks per lot
res = evaluate(ds)                    # {lot: (ValidationReport, ms)}
```

## Memakai data riil (bila ada mitra)
1. Salin `template_data_riil/` (hanya header) dan isi dengan skema yang sama.
2. Anonimkan nama operator/personal; jangan unggah dokumen asli ke repo publik.
3. `labels.csv` boleh dihilangkan; jalankan `python -m src.dataset <folder>`.
