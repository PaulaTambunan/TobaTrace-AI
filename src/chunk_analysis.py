"""Justifikasi parameter chunking: uji berbagai size & overlap tanpa model embedding.

Metrik:
- jumlah_chunk, rata-rata panjang chunk (kata)
- sentence_cut_rate: proporsi batas chunk yang memotong kalimat di tengah
  (potongan dasar tidak berakhir dengan tanda baca akhir kalimat).
- coverage_ok: seluruh kata dokumen asli muncul di minimal satu chunk.
"""
from __future__ import annotations

import csv
import itertools
from pathlib import Path

from src.ingest import base_chunks, chunk_text, load_corpus

SIZES = [60, 90, 120, 160, 200]
OVERLAPS = [0, 10, 20, 40]
_SENTENCE_END = (".", "!", "?", ":")


def analyze(corpus_dir: str = "data/corpus") -> list[dict]:
    rows = []
    files = sorted(Path(corpus_dir).glob("*.txt"))
    for size, overlap in itertools.product(SIZES, OVERLAPS):
        if overlap >= size:
            continue
        total_chunks = 0
        total_words = 0
        boundaries = 0
        cuts = 0
        coverage_ok = True
        for path in files:
            text = path.read_text(encoding="utf-8")
            base = base_chunks(text, size)
            for piece in base[:-1]:
                boundaries += 1
                if not piece.rstrip().endswith(_SENTENCE_END):
                    cuts += 1
            chunks = chunk_text(text, size, overlap)
            total_chunks += len(chunks)
            total_words += sum(len(c.split()) for c in chunks)
            if set(text.split()) - set(" ".join(chunks).split()):
                coverage_ok = False
        rows.append(
            {
                "chunk_size": size,
                "overlap": overlap,
                "jumlah_chunk": total_chunks,
                "rata_kata_per_chunk": round(total_words / total_chunks, 1),
                "batas_chunk": boundaries,
                "sentence_cut_rate": round(cuts / boundaries, 3) if boundaries else 0.0,
                "coverage_ok": coverage_ok,
            }
        )
    return rows


def save_csv(rows: list[dict], out_path: str = "data/chunk_analysis.csv") -> None:
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    rows = analyze()
    save_csv(rows)
    for r in rows:
        print(r)
