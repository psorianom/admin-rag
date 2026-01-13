"""
Retrieval pipeline for querying Code du travail and KALI collections.

This script queries Qdrant vector store (local or cloud).
Supports both semantic search (with embeddings) and keyword search (BM25).

This script:
1. Connects to Qdrant (local or cloud, configured via .env file)
2. Uses semantic search on pre-computed embeddings
3. Returns results with metadata and similarity scores
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from haystack import Pipeline, Document
from haystack.utils.auth import Secret
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
from haystack_integrations.components.retrievers.qdrant import QdrantEmbeddingRetriever
from optimum.onnxruntime import ORTModelForCustomTasks
from transformers import AutoTokenizer
from src.config.constants import QDRANT_CONFIG


# Global document stores and embedder (cached after first load)
_document_stores = {}
_embedder = None


def get_embedder():
    """Get or initialize the BGE-M3 ONNX int8 quantized embedder (700MB, 60ms latency)."""
    global _embedder
    if _embedder is None:
        print("Loading BGE-M3 ONNX int8 quantized model (first load only)...")
        _embedder = {
            "model": ORTModelForCustomTasks.from_pretrained("gpahal/bge-m3-onnx-int8"),
            "tokenizer": AutoTokenizer.from_pretrained("BAAI/bge-m3")
        }
    return _embedder


def encode_query(query: str, embedder: dict) -> list:
    """Encode query to 1024-dim embedding using ONNX BGE-M3 model.

    BGE-M3 outputs:
    - dense_vecs: Dense embeddings (1024-dim) - what we use for semantic search
    - sparse_vecs: Sparse embeddings (for hybrid search)
    - colbert_vecs: ColBERT-style embeddings
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        inputs = embedder["tokenizer"]([query], padding=True, truncation=True, return_tensors="np")
        outputs = embedder["model"](**inputs)

        # BGE-M3 ONNX model outputs dense_vecs directly
        if isinstance(outputs, dict) and 'dense_vecs' in outputs:
            embedding = outputs['dense_vecs'][0]  # First (and only) item in batch
            logger.debug(f"Encoded query to {len(embedding)}-dim embedding")
            return embedding.tolist()
        else:
            available_keys = outputs.keys() if isinstance(outputs, dict) else type(outputs)
            error_msg = f"Unexpected ONNX output format. Available keys: {available_keys}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    except Exception as e:
        logger.error(f"Failed to encode query: {e}", exc_info=True)
        raise


def get_document_store(collection_name: str) -> QdrantDocumentStore:
    """Get or create Qdrant document store for a collection."""
    if collection_name in _document_stores:
        return _document_stores[collection_name]

    # Get config from environment
    config = QDRANT_CONFIG
    qdrant_type = config.get("type", "local")

    if qdrant_type == "cloud":
        conn_config = config["cloud"]
        url = conn_config["url"]
        api_key = conn_config["api_key"]
        print(f"Connecting to Qdrant Cloud: {url}")
        # Wrap API key in Secret for cloud
        api_key_secret = Secret.from_token(api_key) if api_key else None
    else:
        conn_config = config["local"]
        url = conn_config["url"]
        api_key_secret = None  # No API key needed for local
        print(f"Connecting to Local Qdrant: {url}")

    # Create document store
    document_store = QdrantDocumentStore(
        url=url,
        api_key=api_key_secret,
        index=collection_name,
        embedding_dim=1024,  # BGE-M3 dimension
        return_embedding=True,
    )

    _document_stores[collection_name] = document_store
    return document_store


def build_retrieval_pipeline(document_store: QdrantDocumentStore) -> Pipeline:
    """Build Haystack semantic search retrieval pipeline."""

    # Initialize embedder for query encoding
    embedder = get_embedder()

    # Initialize Qdrant retriever (semantic search)
    retriever = QdrantEmbeddingRetriever(document_store=document_store)

    # Build pipeline
    pipeline = Pipeline()
    pipeline.add_component("retriever", retriever)

    return pipeline, embedder


def retrieve(
    query: str,
    collection_name: str = "code_travail",
    top_k: int = 10,
    filters: Optional[Dict] = None,
) -> List[Dict]:
    """
    Retrieve relevant chunks for a query using semantic search with embeddings.

    Args:
        query: User question or search query
        collection_name: Collection to search ('code_travail' or 'kali')
        top_k: Number of results to return
        filters: Optional metadata filters

    Returns:
        List of result dictionaries with content, metadata, and similarity scores
    """
    # Get document store and embedder
    document_store = get_document_store(collection_name)
    embedder = get_embedder()

    # Build pipeline
    pipeline, _ = build_retrieval_pipeline(document_store)

    # Encode query
    print(f"\nQuerying collection: {collection_name}")
    print(f"Query: {query}")
    print(f"Top-k: {top_k}")
    print(f"Method: Semantic search (BGE-M3 ONNX int8 embeddings)")

    query_embedding = encode_query(query, embedder)

    # Run retrieval
    result = pipeline.run({
        "retriever": {"query_embedding": query_embedding, "top_k": top_k, "filters": filters}
    })

    # Extract documents
    documents = result["retriever"]["documents"]

    # Format results
    results = []
    for doc in documents:
        results.append({
            "content": doc.content,
            "metadata": doc.meta,
            "score": doc.score,
        })

    return results


def format_result(result: Dict, rank: int) -> str:
    """Format a single result for display."""
    meta = result["metadata"]
    score = result["score"]
    content = result["content"]

    # Build header
    header = f"\n{'='*80}\n"
    header += f"Rank {rank} | Score: {score:.4f}\n"
    header += f"{'='*80}\n"

    # Article info
    info = f"Article: {meta['article_num']}\n"
    info += f"Source: {meta['source']}\n"

    # KALI-specific metadata
    if meta['source'] == 'kali':
        if meta.get('convention_name'):
            info += f"Convention: {meta['convention_name']}\n"
        if meta.get('idcc'):
            info += f"IDCC: {meta['idcc']}\n"

    # Hierarchy
    if meta.get('livre'):
        info += f"Livre: {meta['livre']}\n"
    if meta.get('titre'):
        info += f"Titre: {meta['titre']}\n"
    if meta.get('chapitre'):
        info += f"Chapitre: {meta['chapitre']}\n"
    if meta.get('section_title'):
        info += f"Section: {meta['section_title']}\n"

    # Chunk info
    if meta.get('is_chunked'):
        info += f"Chunk: {meta['chunk_index'] + 1}/{meta['total_chunks']}\n"

    # Content
    content_section = f"\n--- Content ---\n{content[:500]}"
    if len(content) > 500:
        content_section += f"\n... ({len(content) - 500} more chars)"

    return header + info + content_section


def main():
    """Interactive retrieval demo."""
    print("="*80)
    print("Admin-RAG Retrieval Demo")
    print("="*80)

    print("\nAvailable collections:")
    print("  - code_travail (11,644 chunks)")
    print("  - kali (14,154 chunks from 7 conventions)")
    print("\nRetrieval method: Semantic search (BGE-M3 embeddings)")

    print("\n" + "="*80)
    print("Example Queries")
    print("="*80)

    # Example 1: No filter
    print("\n\n[Example 1] Basic query - no filter")
    query = "Quelle est la durée du préavis de démission?"
    print(f"Query: {query}")
    print(f"Collection: code_travail")
    results = retrieve(query, collection_name="code_travail", top_k=5)
    for i, result in enumerate(results[:3], 1):
        print(format_result(result, i))
    print(f"\n... ({len(results) - 3} more results)")
    print("\n" + "-"*80)

    # Example 2: No filter
    print("\n\n[Example 2] Basic query - no filter")
    query = "période d'essai durée maximale"
    print(f"Query: {query}")
    print(f"Collection: code_travail")
    results = retrieve(query, collection_name="code_travail", top_k=5)
    for i, result in enumerate(results[:3], 1):
        print(format_result(result, i))
    print(f"\n... ({len(results) - 3} more results)")
    print("\n" + "-"*80)

    # Example 3: With convention filter (Syntec)
    print("\n\n[Example 3] Query with metadata filter - Syntec only")
    query = "période d'essai ingénieur"
    print(f"Query: {query}")
    print(f"Collection: kali")
    print(f"Filter: IDCC = 1486 (Syntec)")

    # Filter for Syntec convention (IDCC 1486)
    syntec_filter = {"field": "idcc", "operator": "==", "value": "1486"}

    results = retrieve(query, collection_name="kali", top_k=5, filters=syntec_filter)
    for i, result in enumerate(results[:3], 1):
        print(format_result(result, i))
    if len(results) > 3:
        print(f"\n... ({len(results) - 3} more results)")
    print("\n" + "-"*80)

    # Example 4: With convention filter (HCR)
    print("\n\n[Example 4] Query with metadata filter - HCR only")
    query = "période d'essai serveur"
    print(f"Query: {query}")
    print(f"Collection: kali")
    print(f"Filter: IDCC = 1979 (Hotels, cafés, restaurants)")

    hcr_filter = {"field": "idcc", "operator": "==", "value": "1979"}

    results = retrieve(query, collection_name="kali", top_k=5, filters=hcr_filter)
    for i, result in enumerate(results[:3], 1):
        print(format_result(result, i))
    if len(results) > 3:
        print(f"\n... ({len(results) - 3} more results)")
    print("\n" + "-"*80)

    # Available conventions
    print("\n\nAvailable KALI conventions:")
    print("  - 1486: Syntec (IT services, consulting, engineering)")
    print("  - 3248: Métallurgie")
    print("  - 1979: HCR (Hotels, cafés, restaurants)")
    print("  - 1597: Bâtiment (Construction)")
    print("  - 1090: Services de l'automobile")
    print("  - 2216: Commerce alimentaire")
    print("  - 2120: Banque")


if __name__ == "__main__":
    main()
