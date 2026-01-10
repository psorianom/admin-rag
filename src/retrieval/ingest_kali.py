"""
Ingestion script for KALI conventions chunks into Qdrant vector store.

This script:
1. Loads KALI convention chunks from JSONL
2. Generates BGE-M3 embeddings using sentence-transformers
3. Indexes documents into Qdrant collection 'kali'
"""

import json
import torch
from pathlib import Path
from typing import List, Dict
from haystack import Document, Pipeline
from haystack.components.embedders import SentenceTransformersDocumentEmbedder
from haystack.components.writers import DocumentWriter
from haystack.utils.device import ComponentDevice
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore


def load_chunks(jsonl_path: Path) -> tuple[List[Document], bool]:
    """
    Load chunks from JSONL and convert to Haystack Documents.

    Returns:
        (documents, has_embeddings): List of documents and whether they have pre-computed embeddings
    """
    documents = []
    has_embeddings = False

    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                chunk = json.loads(line)

                # Check if embeddings are present
                embedding = chunk.get('embedding')
                if line_num == 1:
                    has_embeddings = embedding is not None
                    if has_embeddings:
                        print(f"   ℹ️  JSONL contains pre-computed embeddings (will skip embedding step)")

                # Create Haystack Document
                doc = Document(
                    content=chunk['text'],
                    meta={
                        'article_id': chunk['article_id'],
                        'article_num': chunk.get('article_num'),
                        'etat': chunk['etat'],
                        'date_debut': chunk['date_debut'],
                        'date_fin': chunk['date_fin'],
                        'source': chunk['source'],
                        'chunk_id': chunk['chunk_id'],
                        'chunk_index': chunk.get('chunk_index', 0),
                        'total_chunks': chunk.get('total_chunks', 1),
                        'is_chunked': chunk.get('is_chunked', False),
                        # KALI-specific metadata
                        'idcc': chunk['idcc'],
                        'convention_name': chunk['convention_name'],
                        'convention_title': chunk.get('convention_title'),
                        # Hierarchy (may be empty for some KALI articles)
                        'partie': chunk['hierarchy'].get('partie'),
                        'livre': chunk['hierarchy'].get('livre'),
                        'titre': chunk['hierarchy'].get('titre'),
                        'chapitre': chunk['hierarchy'].get('chapitre'),
                        'section_title': chunk.get('section_title'),
                    },
                    embedding=embedding  # Will be None if not present
                )
                documents.append(doc)

            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_num}: {e}")
                continue

    return documents, has_embeddings


def create_qdrant_store(collection_name: str, embedding_dim: int = 1024) -> QdrantDocumentStore:
    """Create and configure Qdrant document store."""
    document_store = QdrantDocumentStore(
        url="http://localhost:6333",
        index=collection_name,
        embedding_dim=embedding_dim,
        recreate_index=True,  # Recreate collection if exists
        return_embedding=True,
        wait_result_from_api=True,
    )
    return document_store


def build_ingestion_pipeline(document_store: QdrantDocumentStore, has_embeddings: bool = False) -> Pipeline:
    """Build Haystack pipeline for embedding and indexing."""

    # Initialize generic document writer
    writer = DocumentWriter(document_store=document_store)

    # Build pipeline
    pipeline = Pipeline()

    if not has_embeddings:
        # Need to generate embeddings
        # Auto-detect device
        if torch.cuda.is_available():
            device = ComponentDevice.from_str("cuda:0")
            print(f"Using device: cuda")
            print(f"GPU: {torch.cuda.get_device_name(0)}")
        else:
            device = ComponentDevice.from_str("cpu")
            print(f"Using device: cpu")

        # Initialize BGE-M3 embedder
        embedder = SentenceTransformersDocumentEmbedder(
            model="BAAI/bge-m3",
            device=device,
            batch_size=32,
            progress_bar=True,
            meta_fields_to_embed=["convention_name", "idcc"],  # Embed convention info for better retrieval
        )

        pipeline.add_component("embedder", embedder)
        pipeline.add_component("writer", writer)
        pipeline.connect("embedder.documents", "writer.documents")
    else:
        # Embeddings already exist, just write to store
        print(f"Using pre-computed embeddings from JSONL")
        pipeline.add_component("writer", writer)

    return pipeline


def ingest_documents(documents: List[Document], pipeline: Pipeline, has_embeddings: bool = False) -> Dict:
    """Run ingestion pipeline on documents."""
    print(f"\nIngesting {len(documents)} documents...")

    if not has_embeddings:
        print(f"Downloading and loading BGE-M3 model (first run only)...")
        result = pipeline.run({"embedder": {"documents": documents}})
    else:
        print(f"Using pre-computed embeddings...")
        result = pipeline.run({"writer": {"documents": documents}})

    return result


def main():
    """Main ingestion workflow."""
    print("="*80)
    print("KALI Conventions Ingestion Pipeline")
    print("="*80)

    # Paths
    project_root = Path(__file__).parent.parent.parent
    chunks_path = project_root / "data" / "processed" / "kali_chunks.jsonl"

    if not chunks_path.exists():
        print(f"Error: Chunks file not found at {chunks_path}")
        return

    # Load chunks
    print(f"\nLoading chunks from: {chunks_path}")
    documents, has_embeddings = load_chunks(chunks_path)
    print(f"Loaded {len(documents)} documents")

    # Sample document info
    if documents:
        sample = documents[0]
        print(f"\nSample document:")
        print(f"  IDCC: {sample.meta['idcc']}")
        print(f"  Convention: {sample.meta['convention_name']}")
        print(f"  Source: {sample.meta['source']}")
        print(f"  Content length: {len(sample.content)} chars")
        if sample.meta.get('article_num'):
            print(f"  Article: {sample.meta['article_num']}")
        if sample.embedding:
            print(f"  Embedding: present ({len(sample.embedding)} dims)")

    # Show convention breakdown
    print(f"\nConvention breakdown:")
    from collections import Counter
    convention_counts = Counter([doc.meta['convention_name'] for doc in documents])
    for convention, count in convention_counts.most_common():
        idcc = [doc.meta['idcc'] for doc in documents if doc.meta['convention_name'] == convention][0]
        print(f"  {convention} (IDCC {idcc}): {count:,} chunks")

    # Create Qdrant store
    print(f"\nCreating Qdrant collection 'kali'...")
    document_store = create_qdrant_store(
        collection_name="kali",
        embedding_dim=1024  # BGE-M3 dimension
    )

    # Build pipeline
    if has_embeddings:
        print(f"\nBuilding ingestion pipeline (embeddings from JSONL)...")
    else:
        print(f"\nBuilding ingestion pipeline with BGE-M3 embedder...")
    pipeline = build_ingestion_pipeline(document_store, has_embeddings)

    # Ingest documents
    result = ingest_documents(documents, pipeline, has_embeddings)

    # Summary
    print("\n" + "="*80)
    print("Ingestion Complete!")
    print("="*80)
    print(f"Collection: kali")
    print(f"Documents indexed: {len(documents):,}")
    print(f"Conventions: {len(convention_counts)}")
    print(f"Embedding model: BAAI/bge-m3 (1024 dims)")
    print(f"Qdrant URL: http://localhost:6333")
    print(f"\nYou can view the collection at: http://localhost:6333/dashboard")


if __name__ == "__main__":
    main()
