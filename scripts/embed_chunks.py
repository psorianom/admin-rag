"""
Generate BGE-M3 embeddings for JSONL chunks and save back to JSONL.

This script:
1. Reads chunks from JSONL files
2. Generates BGE-M3 embeddings (GPU accelerated if available)
3. Adds 'embedding' field to each chunk
4. Saves back to JSONL files

Use this on vast.ai to generate embeddings, then download and index locally.
"""

import json
import torch
from pathlib import Path
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


def load_chunks(jsonl_path: Path) -> List[Dict[str, Any]]:
    """Load chunks from JSONL file."""
    chunks = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            chunks.append(json.loads(line))
    return chunks


def save_chunks(chunks: List[Dict[str, Any]], jsonl_path: Path):
    """Save chunks with embeddings to JSONL file."""
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + '\n')


def embed_chunks(chunks: List[Dict[str, Any]], model: SentenceTransformer, batch_size: int = 32) -> List[Dict[str, Any]]:
    """Add embeddings to chunks."""
    print(f"Embedding {len(chunks)} chunks...")

    # Extract texts
    texts = [chunk['text'] for chunk in chunks]

    # Generate embeddings in batches with progress bar
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True
    )

    # Add embeddings to chunks
    for chunk, embedding in zip(chunks, embeddings):
        chunk['embedding'] = embedding.tolist()

    return chunks


def main():
    """Main workflow."""
    print("="*80)
    print("BGE-M3 Embedding Generator")
    print("="*80)

    # Detect device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\nDevice: {device}")
    if device == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")

    # Paths
    project_root = Path(__file__).parent.parent
    code_travail_path = project_root / "data" / "processed" / "code_travail_chunks.jsonl"
    kali_path = project_root / "data" / "processed" / "kali_chunks.jsonl"

    # Check files exist
    if not code_travail_path.exists():
        print(f"❌ Missing: {code_travail_path}")
        return
    if not kali_path.exists():
        print(f"❌ Missing: {kali_path}")
        return

    # Load model
    print(f"\n📥 Loading BGE-M3 model...")
    model = SentenceTransformer('BAAI/bge-m3', device=device)
    print(f"✅ Model loaded (embedding dim: {model.get_sentence_embedding_dimension()})")

    # Process Code du travail
    print(f"\n" + "="*80)
    print("Processing Code du travail")
    print("="*80)

    print(f"Loading chunks from {code_travail_path.name}...")
    code_travail_chunks = load_chunks(code_travail_path)
    print(f"Loaded {len(code_travail_chunks)} chunks")

    code_travail_chunks = embed_chunks(code_travail_chunks, model, batch_size=32)

    print(f"Saving embeddings to {code_travail_path}...")
    save_chunks(code_travail_chunks, code_travail_path)
    print(f"✅ Saved {len(code_travail_chunks)} chunks with embeddings")

    # Process KALI
    print(f"\n" + "="*80)
    print("Processing KALI conventions")
    print("="*80)

    print(f"Loading chunks from {kali_path.name}...")
    kali_chunks = load_chunks(kali_path)
    print(f"Loaded {len(kali_chunks)} chunks")

    kali_chunks = embed_chunks(kali_chunks, model, batch_size=32)

    print(f"Saving embeddings to {kali_path}...")
    save_chunks(kali_chunks, kali_path)
    print(f"✅ Saved {len(kali_chunks)} chunks with embeddings")

    # Summary
    total_chunks = len(code_travail_chunks) + len(kali_chunks)
    print(f"\n" + "="*80)
    print("✅ Embedding Complete!")
    print("="*80)
    print(f"Total chunks embedded: {total_chunks:,}")
    print(f"  - Code du travail: {len(code_travail_chunks):,}")
    print(f"  - KALI: {len(kali_chunks):,}")
    print(f"\nFiles updated:")
    print(f"  - {code_travail_path}")
    print(f"  - {kali_path}")
    print(f"\nNext steps:")
    print(f"  1. Compress: gzip data/processed/*_chunks.jsonl")
    print(f"  2. Download to local machine")
    print(f"  3. Decompress: gunzip data/processed/*.jsonl.gz")
    print(f"  4. Index: make ingest-only")


if __name__ == "__main__":
    main()
