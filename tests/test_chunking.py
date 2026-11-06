import pytest

from src.ingest import chunk_text, doc_metadata, load_corpus
from pathlib import Path


def test_chunk_size_respected():
    text = " ".join(f"kata{i}" for i in range(500))
    chunks = chunk_text(text, size=50, overlap=10)
    assert all(len(c.split()) <= 50 + 10 for c in chunks)


def test_overlap_present():
    text = " ".join(f"kata{i}" for i in range(200))
    chunks = chunk_text(text, size=50, overlap=10)
    assert len(chunks) > 1
    assert chunks[0].split()[-10:] == chunks[1].split()[:10]


def test_no_empty_chunks_and_all_text_kept():
    text = "Paragraf satu.\n\nParagraf dua yang lebih panjang. Kalimat kedua di sini.\n\nParagraf tiga."
    chunks = chunk_text(text, size=5, overlap=0)
    assert all(c.strip() for c in chunks)
    joined = " ".join(chunks)
    for word in ["satu", "dua", "tiga"]:
        assert word in joined


def test_invalid_overlap_raises():
    with pytest.raises(ValueError):
        chunk_text("abc", size=10, overlap=10)


def test_doc_metadata_sop():
    meta = doc_metadata(Path("SOP-07_kebun_deforestasi.txt"), "SOP-07 Penanganan Kebun\n\nIsi")
    assert meta["doc_type"] == "SOP"
    assert meta["sop_number"] == "SOP-07"
    assert meta["doc_title"] == "SOP-07 Penanganan Kebun"


def test_doc_metadata_regulasi():
    meta = doc_metadata(Path("RINGKASAN_EUDR.txt"), "Judul\nIsi")
    assert meta["doc_type"] == "regulasi"
    assert meta["sop_number"] == ""


def test_load_corpus_has_full_metadata():
    records = load_corpus("data/corpus", size=120, overlap=20)
    assert len(records) >= 12
    required = {"doc_id", "doc_title", "doc_type", "sop_number", "source", "chunk",
                "total_chunks", "word_count", "chunk_size", "overlap"}
    for r in records:
        assert required <= set(r["metadata"])
        assert r["metadata"]["word_count"] == len(r["text"].split())


def test_no_tokens_lost_on_real_corpus():
    """Regresi: tanda baca di batas chunk tidak boleh hilang (bug separator sebelumnya)."""
    from pathlib import Path as _P

    for path in sorted(_P("data/corpus").glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        for size in (60, 90, 120, 200):
            chunks = chunk_text(text, size=size, overlap=0)
            assert set(text.split()) <= set(" ".join(chunks).split()), (path.name, size)


def test_sentence_split_keeps_punctuation():
    chunks = chunk_text("Kalimat satu. Kalimat dua! Kalimat tiga?", size=2, overlap=0)
    assert " ".join(chunks) == "Kalimat satu. Kalimat dua! Kalimat tiga?"
