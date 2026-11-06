"""Milestone 3: pipeline ingestion (word-aware chunking + overlap), embedding dense, dan indeks ChromaDB persisten."""
from __future__ import annotations

import re
from pathlib import Path

# Level pemisahan dari yang terbesar: (pola regex, penyambung saat digabung kembali).
# Pola kalimat memakai lookbehind agar tanda baca tetap menempel pada kalimatnya.
SEPARATORS: list[tuple[str, str]] = [
    (r"\n\s*\n", "\n\n"),
    (r"\n", "\n"),
    (r"(?<=[.!?:])\s+", " "),
    (r"\s+", " "),
]
DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"  # multibahasa, mendukung Bahasa Indonesia
DEFAULT_CORPUS_DIR = "data/corpus"
DEFAULT_DB_PATH = "data/chroma_db"
COLLECTION_NAME = "enterprise_kb"
DEFAULT_CHUNK_SIZE = 120
DEFAULT_OVERLAP = 20


def _split_recursive(text: str, size: int, level: int = 0) -> list[str]:
    """Pecah teks pada level terbesar dulu; turun ke level lebih kecil bila bagian masih terlalu panjang."""
    if len(text.split()) <= size:
        return [text]
    if level >= len(SEPARATORS):
        words = text.split()
        return [" ".join(words[i : i + size]) for i in range(0, len(words), size)]

    pattern, joiner = SEPARATORS[level]
    parts = [p.strip() for p in re.split(pattern, text) if p and p.strip()]
    chunks: list[str] = []
    buf = ""
    for part in parts:
        candidate = part if not buf else buf + joiner + part
        if len(candidate.split()) <= size:
            buf = candidate
            continue
        if buf:
            chunks.append(buf)
        if len(part.split()) > size:
            chunks.extend(_split_recursive(part, size, level + 1))
            buf = ""
        else:
            buf = part
    if buf:
        chunks.append(buf)
    return chunks


def base_chunks(text: str, size: int = DEFAULT_CHUNK_SIZE) -> list[str]:
    """Potongan dasar tanpa overlap."""
    return _split_recursive(text.strip(), size)


def chunk_text(text: str, size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP) -> list[str]:
    """Potongan ~`size` kata; setiap potongan (kecuali pertama) diawali `overlap` kata dari potongan sebelumnya.

    Panjang maksimum tiap potongan adalah size + overlap kata.
    """
    if not 0 <= overlap < size:
        raise ValueError("overlap harus >= 0 dan < size")
    base = base_chunks(text, size)
    if not base:
        return []
    result = [base[0]]
    for prev, cur in zip(base, base[1:]):
        tail = " ".join(prev.split()[-overlap:]) if overlap else ""
        result.append((tail + " " + cur).strip())
    return result


_DOC_TYPE_RULES = [("SOP-", "SOP"), ("KEBIJAKAN", "kebijakan"), ("RINGKASAN", "regulasi")]


def doc_metadata(path: Path, text: str) -> dict:
    """Metadata dokumen: id, judul (baris pertama), jenis dokumen, dan nomor SOP bila ada."""
    title = next((ln.strip() for ln in text.splitlines() if ln.strip()), path.stem)
    doc_type = next((t for prefix, t in _DOC_TYPE_RULES if path.stem.upper().startswith(prefix)), "lainnya")
    m = re.match(r"(SOP-\d+)", path.stem)
    return {
        "doc_id": path.stem,
        "doc_title": title,
        "doc_type": doc_type,
        "sop_number": m.group(1) if m else "",
    }


def load_corpus(corpus_dir: str | Path, size: int, overlap: int) -> list[dict]:
    """Muat dan potong seluruh dokumen .txt, menghasilkan satu record per chunk dengan metadata lengkap."""
    records = []
    for path in sorted(Path(corpus_dir).glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        meta = doc_metadata(path, text)
        chunks = chunk_text(text, size, overlap)
        for i, chunk in enumerate(chunks):
            records.append(
                {
                    "id": f"{meta['doc_id']}-{i:03d}",
                    "text": chunk,
                    "metadata": {
                        **meta,
                        "source": path.name,
                        "chunk": i,
                        "total_chunks": len(chunks),
                        "word_count": len(chunk.split()),
                        "chunk_size": size,
                        "overlap": overlap,
                    },
                }
            )
    return records


def build_index(
    corpus_dir: str = DEFAULT_CORPUS_DIR,
    db_path: str = DEFAULT_DB_PATH,
    model_name: str = DEFAULT_MODEL,
    size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> int:
    """Bangun/perbarui indeks ChromaDB persisten (cosine). Mengembalikan jumlah chunk yang disimpan."""
    import chromadb
    from sentence_transformers import SentenceTransformer

    records = load_corpus(corpus_dir, size, overlap)
    model = SentenceTransformer(model_name)
    embeddings = model.encode(
        [r["text"] for r in records], normalize_embeddings=True, show_progress_bar=True
    )
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )
    collection.upsert(
        ids=[r["id"] for r in records],
        documents=[r["text"] for r in records],
        metadatas=[r["metadata"] for r in records],
        embeddings=embeddings.tolist(),
    )
    return len(records)


if __name__ == "__main__":
    n = build_index()
    print(f"Indeks dibangun: {n} chunk tersimpan di {DEFAULT_DB_PATH}")
