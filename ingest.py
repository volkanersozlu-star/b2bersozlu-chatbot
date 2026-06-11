import sys
from pathlib import Path

import chromadb
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

CHROMA_DIR = "chroma_db"
EMBED_MODEL = "all-MiniLM-L6-v2"

_splitter = None
_embedder = None


def _get_splitter():
    global _splitter
    if _splitter is None:
        _splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    return _splitter


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


def _collection_name(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


def _get_collection(tenant_id: str):
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    return client.get_or_create_collection(_collection_name(tenant_id))


def _docs_dir(tenant_id: str) -> Path:
    d = Path("tenants") / tenant_id / "docs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def ingest_pdf(pdf_path: Path, tenant_id: str = "default") -> int:
    collection = _get_collection(tenant_id)
    existing = {m["source"] for m in collection.get(include=["metadatas"])["metadatas"]}

    if pdf_path.name in existing:
        return 0

    text = extract_text(pdf_path)
    if not text.strip():
        raise ValueError("PDF'den metin çıkarılamadı.")

    chunks = _get_splitter().split_text(text)
    embeddings = _get_embedder().encode(chunks).tolist()
    ids = [f"{pdf_path.stem}_{i}" for i in range(len(chunks))]
    metadatas = [{"source": pdf_path.name, "chunk": i} for i in range(len(chunks))]

    collection.add(documents=chunks, embeddings=embeddings, ids=ids, metadatas=metadatas)
    return len(chunks)


def delete_pdf(filename: str, tenant_id: str = "default") -> int:
    collection = _get_collection(tenant_id)
    results = collection.get(where={"source": filename}, include=["metadatas"])
    ids = results["ids"]
    if ids:
        collection.delete(ids=ids)
    return len(ids)


def list_documents(tenant_id: str = "default") -> list:
    collection = _get_collection(tenant_id)
    metadatas = collection.get(include=["metadatas"])["metadatas"]
    counts: dict = {}
    for m in metadatas:
        counts[m["source"]] = counts.get(m["source"], 0) + 1
    return [{"name": name, "chunks": count} for name, count in sorted(counts.items())]


def delete_tenant_collection(tenant_id: str):
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    name = _collection_name(tenant_id)
    try:
        client.delete_collection(name)
    except Exception:
        pass


def main():
    tenant_id = "default"
    docs_dir = _docs_dir(tenant_id)
    pdf_files = list(docs_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"tenants/{tenant_id}/docs/ klasöründe PDF bulunamadı.")
        sys.exit(0)

    total = 0
    for pdf_path in pdf_files:
        added = ingest_pdf(pdf_path, tenant_id)
        if added == 0:
            print(f"Atlandı (zaten indeksli): {pdf_path.name}")
        else:
            print(f"{pdf_path.name}: {added} chunk eklendi.")
            total += added

    print(f"\nToplam {total} yeni chunk kaydedildi.")


if __name__ == "__main__":
    main()
