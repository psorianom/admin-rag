"""
Ingestion script for Code du travail chunks into Qdrant vector store.

This script:
1. Loads Code du travail chunks from JSONL
2. Generates BGE-M3 embeddings using sentence-transformers
3. Indexes documents into Qdrant collection 'code_travail'
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


def load_chunks(jsonl_path: Path) -> List[Document]:
    """Load chunks from JSONL and convert to Haystack Documents."""
    documents = []

    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                chunk = json.loads(line)

                # Create Haystack Document
                doc = Document(
                    content=chunk['text'],
                    meta={
                        'article_id': chunk['article_id'],
                        'article_num': chunk['article_num'],
                        'etat': chunk['etat'],
                        'date_debut': chunk['date_debut'],
                        'date_fin': chunk['date_fin'],
                        'source': chunk['source'],
                        'chunk_id': chunk['chunk_id'],
                        'chunk_index': chunk.get('chunk_index', 0),
                        'total_chunks': chunk.get('total_chunks', 1),
                        'is_chunked': chunk.get('is_chunked', False),
                        # Hierarchy
                        'partie': chunk['hierarchy'].get('partie'),
                        'livre': chunk['hierarchy'].get('livre'),
                        'titre': chunk['hierarchy'].get('titre'),
                        'chapitre': chunk['hierarchy'].get('chapitre'),
                        'section_title': chunk.get('section_title'),
                    }
                )
                documents.append(doc)

            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_num}: {e}")
                continue

    return documents


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


def build_ingestion_pipeline(document_store: QdrantDocumentStore) -> Pipeline:
    """Build Haystack pipeline for embedding and indexing."""

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
        meta_fields_to_embed=["article_num"],  # Also embed article number for better retrieval
    )

    # Initialize generic document writer
    writer = DocumentWriter(document_store=document_store)

    # Build pipeline
    pipeline = Pipeline()
    pipeline.add_component("embedder", embedder)
    pipeline.add_component("writer", writer)
    pipeline.connect("embedder.documents", "writer.documents")

    return pipeline


def ingest_documents(documents: List[Document], pipeline: Pipeline) -> Dict:
    """Run ingestion pipeline on documents."""
    print(f"\nIngesting {len(documents)} documents...")
    print(f"Downloading and loading BGE-M3 model (first run only)...")

    result = pipeline.run({"embedder": {"documents": documents}})

    return result


def main():
    """Main ingestion workflow."""
    print("="*80)
    print("Code du travail Ingestion Pipeline")
    print("="*80)

    # Paths
    project_root = Path(__file__).parent.parent.parent
    chunks_path = project_root / "data" / "processed" / "code_travail_chunks.jsonl"

    if not chunks_path.exists():
        print(f"Error: Chunks file not found at {chunks_path}")
        return

    # Load chunks
    print(f"\nLoading chunks from: {chunks_path}")
    documents = load_chunks(chunks_path)
    print(f"Loaded {len(documents)} documents")

    # Sample document info
    if documents:
        sample = documents[0]
        print(f"\nSample document:")
        print(f"  Article: {sample.meta['article_num']}")
        print(f"  Source: {sample.meta['source']}")
        print(f"  Content length: {len(sample.content)} chars")
        print(f"  Hierarchy: {sample.meta['livre']}")

    # Create Qdrant store
    print(f"\nCreating Qdrant collection 'code_travail'...")
    document_store = create_qdrant_store(
        collection_name="code_travail",
        embedding_dim=1024  # BGE-M3 dimension
    )

    # Build pipeline
    print(f"\nBuilding ingestion pipeline with BGE-M3 embedder...")
    pipeline = build_ingestion_pipeline(document_store)

    # Ingest documents
    result = ingest_documents(documents, pipeline)

    # Summary
    print("\n" + "="*80)
    print("Ingestion Complete!")
    print("="*80)
    print(f"Collection: code_travail")
    print(f"Documents indexed: {len(documents)}")
    print(f"Embedding model: BAAI/bge-m3 (1024 dims)")
    print(f"Qdrant URL: http://localhost:6333")
    print(f"\nYou can view the collection at: http://localhost:6333/dashboard")


if __name__ == "__main__":
    main()
