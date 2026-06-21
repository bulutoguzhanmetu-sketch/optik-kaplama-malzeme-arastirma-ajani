"""
source_pdfs/ klasöründeki akademik makaleleri (PDF) okuyup parçalara böler,
ChromaDB kalıcı vektör veritabanına yazar. ingested_manifest.json sayesinde
yalnızca yeni veya değişmiş (hash değişen) dosyalar yeniden işlenir.

Kullanım:
    python ingest.py
"""
import hashlib
import json
import sys

import chromadb
from pypdf import PdfReader

import config


def _file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _load_manifest():
    if config.MANIFEST_PATH.exists():
        with open(config.MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_manifest(manifest):
    with open(config.MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def _sanitize_text(text):
    """Bazı PDF'lerin özel font kodlamalarından kaynaklanan eşleşmemiş (surrogate)
    Unicode karakterlerini temizler; aksi halde ChromaDB'nin embedding tokenizer'ı
    'TextInputSequence must be str' hatasıyla çöker."""
    return text.encode("utf-8", "ignore").decode("utf-8")


def _extract_pages(pdf_path):
    """PDF'den sayfa sayfa metin döndürür: [(sayfa_no, metin), ...]"""
    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = _sanitize_text(text).strip()
        if text:
            pages.append((i, text))
    return pages


def _chunk_pages(pages, chunk_words, overlap_words):
    """Sayfa metinlerini kelime bazlı, overlap'li chunk'lara böler.
    Her chunk'ın hangi sayfa aralığından geldiğini metadata olarak taşır."""
    chunks = []
    for page_no, text in pages:
        words = text.split()
        if not words:
            continue
        start = 0
        while start < len(words):
            end = min(start + chunk_words, len(words))
            chunk_text = " ".join(words[start:end])
            chunks.append({"text": chunk_text, "page": page_no})
            if end == len(words):
                break
            start = end - overlap_words
    return chunks


def ingest_pdf(pdf_path, collection):
    pages = _extract_pages(pdf_path)
    if not pages:
        print(f"Uyarı: '{pdf_path.name}' içinden metin çıkarılamadı (taranmış/görsel PDF olabilir).")
        return 0

    chunk_words = int(config.CHUNK_TOKEN_SIZE * 0.75)
    overlap_words = int(config.CHUNK_TOKEN_OVERLAP * 0.75)
    chunks = _chunk_pages(pages, chunk_words, overlap_words)

    ids, documents, metadatas = [], [], []
    for idx, chunk in enumerate(chunks):
        chunk_id = f"{pdf_path.stem}__{idx}"
        ids.append(chunk_id)
        documents.append(chunk["text"])
        metadatas.append({"source": pdf_path.name, "page": chunk["page"]})

    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    return len(chunks)


def remove_pdf_chunks(file_stem, collection):
    """Manifest'te olup artık diskte olmayan veya değişen bir dosyanın eski chunk'larını siler."""
    existing = collection.get(where={"source": {"$eq": file_stem}})
    if existing and existing.get("ids"):
        collection.delete(ids=existing["ids"])


def main():
    client = chromadb.PersistentClient(path=str(config.CHROMA_DB_DIR))
    collection = client.get_or_create_collection(name=config.COLLECTION_NAME)

    manifest = _load_manifest()
    pdf_files = sorted(config.SOURCE_PDF_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"'{config.SOURCE_PDF_DIR}' klasöründe PDF bulunamadı.")
        return

    processed, skipped, failed = 0, 0, 0
    for pdf_path in pdf_files:
        current_hash = _file_hash(pdf_path)
        prev_entry = manifest.get(pdf_path.name)

        if prev_entry and prev_entry.get("hash") == current_hash:
            skipped += 1
            continue

        if prev_entry:
            # Dosya değişmiş: eski parçaları temizleyip yeniden işle.
            remove_pdf_chunks(pdf_path.name, collection)

        try:
            chunk_count = ingest_pdf(pdf_path, collection)
        except Exception as exc:
            print(f"Hata: '{pdf_path.name}' işlenemedi, atlanıyor. ({exc})")
            failed += 1
            continue

        manifest[pdf_path.name] = {"hash": current_hash, "chunks": chunk_count}
        _save_manifest(manifest)
        print(f"İşlendi: {pdf_path.name} ({chunk_count} parça)")
        processed += 1

    # Diskte artık olmayan dosyaları manifest'ten ve veritabanından temizle.
    current_names = {p.name for p in pdf_files}
    removed = [name for name in manifest if name not in current_names]
    for name in removed:
        remove_pdf_chunks(name, collection)
        del manifest[name]
        print(f"Kaldırıldı: {name} (kaynak dosya artık mevcut değil)")

    _save_manifest(manifest)
    print(
        f"\nToplam: {processed} işlendi, {skipped} atlandı (değişmedi), "
        f"{failed} hatalı, {len(removed)} kaldırıldı."
    )
    print(f"Vektör veritabanı: {config.CHROMA_DB_DIR}")


if __name__ == "__main__":
    sys.exit(main() or 0)
