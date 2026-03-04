"""
Knowledge Base Ingestion Script — Phase 2
==========================================
Reads all Markdown files from knowledge_base/, chunks them, embeds them,
and upserts into a Pinecone vector index.

Run: python scripts/ingest_knowledge_base.py

Prerequisites:
    pip install pinecone-client openai tiktoken python-dotenv
    Set PINECONE_API_KEY and OPENAI_API_KEY in .env
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Check dependencies before importing
try:
    from pinecone import Pinecone, ServerlessSpec
    import openai
    import tiktoken
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install pinecone-client openai tiktoken")
    sys.exit(1)

PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
INDEX_NAME = os.environ.get("PINECONE_INDEX_NAME", "kenya-safari-knowledge")
EMBED_MODEL = "text-embedding-3-large"
EMBED_DIMENSIONS = 3072
CHUNK_SIZE_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 64

BASE_DIR = Path(__file__).parent.parent
KB_DIR = BASE_DIR / "knowledge_base"


# ─────────────────────────────────────────────────────────────
# Chunking
# ─────────────────────────────────────────────────────────────

def chunk_text(text: str, source: str) -> list[dict]:
    """Split text into overlapping chunks and return with metadata."""
    enc = tiktoken.encoding_for_model("gpt-4")
    tokens = enc.encode(text)
    chunks = []
    start = 0
    chunk_idx = 0

    while start < len(tokens):
        end = min(start + CHUNK_SIZE_TOKENS, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = enc.decode(chunk_tokens)
        chunks.append(
            {
                "id": f"{source}__chunk_{chunk_idx}",
                "text": chunk_text,
                "metadata": {
                    "source": source,
                    "chunk_index": chunk_idx,
                    "char_count": len(chunk_text),
                },
            }
        )
        start += CHUNK_SIZE_TOKENS - CHUNK_OVERLAP_TOKENS
        chunk_idx += 1

    return chunks


def load_knowledge_base() -> list[dict]:
    """Walk the knowledge_base directory and load all .md files."""
    all_chunks: list[dict] = []
    for md_file in KB_DIR.rglob("*.md"):
        relative = str(md_file.relative_to(BASE_DIR))
        text = md_file.read_text(encoding="utf-8")
        chunks = chunk_text(text, source=relative)
        all_chunks.extend(chunks)
        print(f"  ✓ {relative} → {len(chunks)} chunks")

    return all_chunks


# ─────────────────────────────────────────────────────────────
# Embedding
# ─────────────────────────────────────────────────────────────

def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Add embeddings to each chunk using OpenAI text-embedding-3-large."""
    oai = openai.OpenAI(api_key=OPENAI_API_KEY)
    BATCH = 100
    embedded: list[dict] = []

    for i in range(0, len(chunks), BATCH):
        batch = chunks[i : i + BATCH]
        texts = [c["text"] for c in batch]
        print(f"  Embedding batch {i // BATCH + 1} ({len(texts)} chunks)...")
        response = oai.embeddings.create(model=EMBED_MODEL, input=texts)
        for chunk, emb in zip(batch, response.data):
            embedded.append({**chunk, "embedding": emb.embedding})

    return embedded


# ─────────────────────────────────────────────────────────────
# Pinecone Upsert
# ─────────────────────────────────────────────────────────────

def upsert_to_pinecone(embedded_chunks: list[dict]) -> None:
    pc = Pinecone(api_key=PINECONE_API_KEY)

    # Create index if it doesn't exist
    existing = [idx.name for idx in pc.list_indexes()]
    if INDEX_NAME not in existing:
        print(f"  Creating Pinecone index '{INDEX_NAME}'...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBED_DIMENSIONS,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )

    index = pc.Index(INDEX_NAME)

    # Upsert in batches of 100
    BATCH = 100
    vectors = [
        {
            "id": c["id"],
            "values": c["embedding"],
            "metadata": {**c["metadata"], "text": c["text"][:1000]},
        }
        for c in embedded_chunks
    ]

    for i in range(0, len(vectors), BATCH):
        batch = vectors[i : i + BATCH]
        index.upsert(vectors=batch)
        print(f"  Upserted vectors {i + 1}–{i + len(batch)}")

    stats = index.describe_index_stats()
    print(f"\n  ✅ Index '{INDEX_NAME}' total vectors: {stats['total_vector_count']}")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main() -> None:
    print("\nKenya Group Joining Safaris — Knowledge Base Ingestion")
    print("=" * 56)

    if not PINECONE_API_KEY:
        print("❌ PINECONE_API_KEY is not set in .env")
        sys.exit(1)
    if not OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY is not set in .env")
        sys.exit(1)

    print("\n1. Loading knowledge base files...")
    chunks = load_knowledge_base()
    print(f"   Total chunks: {len(chunks)}")

    print("\n2. Embedding chunks (this may take a minute)...")
    embedded = embed_chunks(chunks)

    print("\n3. Upserting to Pinecone...")
    upsert_to_pinecone(embedded)

    print("\n✅ Knowledge base ingestion complete!")
    print("   You can now use the search_knowledge_base tool in the agent.\n")


if __name__ == "__main__":
    main()
