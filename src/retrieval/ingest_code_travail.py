"""
Ingestion script for Code du travail chunks into Qdrant vector store.

This script:
1. Loads Code du travail chunks from JSONL
2. Generates BGE-M3 embeddings using sentence-transformers
3. Indexes documents into Qdrant collection 'code_travail'

Supports both local Qdrant and Qdrant Cloud (via config/qdrant_config.json)
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
                    },
                    embedding=embedding  # Will be None if not present
                )
                documents.append(doc)

            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_num}: {e}")
                continue

    return documents, has_embeddings


def load_qdrant_config() -> Dict:
    """Load Qdrant configuration from config file."""
    config_path = Path(__file__).parent.parent.parent / "config" / "qdrant_config.json"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r') as f:
        config = json.load(f)

    return config


def create_qdrant_store(collection_name: str, embedding_dim: int = 1024) -> QdrantDocumentStore:
    """Create and configure Qdrant document store (local or cloud)."""
    config = load_qdrant_config()
    qdrant_type = config.get("type", "local")

    if qdrant_type == "cloud":
        conn_config = config["cloud"]
        url = conn_config["url"]
        api_key = conn_config["api_key"]
        print(f"Using Qdrant Cloud: {url}")
    else:
        conn_config = config["local"]
        url = conn_config["url"]
        api_key = conn_config.get("api_key")
        print(f"Using Local Qdrant: {url}")

    document_store = QdrantDocumentStore(
        url=url,
        api_key=api_key,
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
            meta_fields_to_embed=["article_num"],  # Also embed article number for better retrieval
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
    documents, has_embeddings = load_chunks(chunks_path)
    print(f"Loaded {len(documents)} documents")

    # Sample document info
    if documents:
        sample = documents[0]
        print(f"\nSample document:")
        print(f"  Article: {sample.meta['article_num']}")
        print(f"  Source: {sample.meta['source']}")
        print(f"  Content length: {len(sample.content)} chars")
        print(f"  Hierarchy: {sample.meta['livre']}")
        if sample.embedding:
            print(f"  Embedding: present ({len(sample.embedding)} dims)")

    # Create Qdrant store
    print(f"\nCreating Qdrant collection 'code_travail'...")
    document_store = create_qdrant_store(
        collection_name="code_travail",
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
    config = load_qdrant_config()
    qdrant_url = config[config.get("type", "local")]["url"]
    print(f"Collection: code_travail")
    print(f"Documents indexed: {len(documents)}")
    print(f"Embedding model: BAAI/bge-m3 (1024 dims)")
    print(f"Qdrant URL: {qdrant_url}")
    if "cloud" in qdrant_url:
        print(f"\nYou can view the collection at your Qdrant Cloud console")
    else:
        print(f"\nYou can view the collection at: {qdrant_url}/dashboard")


if __name__ == "__main__":
    main()
