"""Builds the search index from the official documents (FR-DATA-03).

Run from backend/:   python -m scripts.ingest
- reads data/raw_docs/<service_id>/*.md (files that fail check_docs are skipped and listed),
- cuts them into passages, embeds them with e5 ("passage: " prefix),
- replaces the Chroma collection and prints passages per service.
Exit code 1 if a service ends up with no passages at all.
"""

import logging
import sys
from collections import Counter

from app.config import BACKEND_DIR, get_settings
from app.container import Container
from app.infrastructure.retrieval.chroma_retriever import embedding_text
from app.infrastructure.retrieval.chunker import chunk_documents
from app.infrastructure.retrieval.documents import load_documents

RAW_DOCS = BACKEND_DIR / "data" / "raw_docs"


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    container = Container(get_settings())
    service_ids = [s.id for s in container.services if s.id != "other"]

    docs, problems = load_documents(RAW_DOCS, service_ids)
    chunks = chunk_documents(docs)
    print(f"{len(docs)} documents -> {len(chunks)} passages. Embedding (first run loads the model)...")

    stored = container.retriever.rebuild(chunks)

    per_service = Counter(c.service_id for c in chunks)
    print(f"\n{'service':22} {'passages':>8}")
    for sid in service_ids:
        print(f"{sid:22} {per_service.get(sid, 0):>8}")
    print(f"{'total stored':22} {stored:>8}   (in {container.settings.chroma_dir})")

    embedder = container.embedder
    too_long = [c.chunk_id for c in chunks if embedder.token_count(embedding_text(c)) > embedder.max_tokens]
    if too_long:
        print(f"\nWARNING: {len(too_long)} passage(s) are longer than the model reads: {', '.join(too_long)}")
    if problems:
        print("\nSkipped (fix with python -m scripts.check_docs):")
        for p in problems:
            print("  -", p)

    empty = [sid for sid in service_ids if not per_service.get(sid)]
    if empty:
        print(f"\nNo passages for: {', '.join(empty)}")
    return 1 if empty else 0


if __name__ == "__main__":
    sys.exit(main())
