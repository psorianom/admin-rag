"""
Test latency of quantized BGE-M3 embeddings (ONNX or transformers).
Measures model load time and query embedding time.
"""

import time
import sys

# Try both backends
try:
    from optimum.onnxruntime import ORTModelForCustomTasks
    from transformers import AutoTokenizer
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

# Sample queries
QUERIES = [
    "période d'essai durée maximale",
    "Quelle est la durée du préavis de démission?",
    "Syntec période d'essai ingénieur",
    "salaire minimum convention collective",
    "licenciement motif économique",
]


def test_embedding_latency_onnx(model_name: str, tokenizer_name: str = "BAAI/bge-m3"):
    """Test ONNX model latency."""
    print("="*80)
    print(f"Testing ONNX: {model_name}")
    print("="*80)
    print()

    # Load tokenizer
    print("1️⃣  Loading tokenizer...")
    start = time.time()
    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
        tokenizer_time = time.time() - start
        print(f"   ✅ Tokenizer loaded in {tokenizer_time:.2f}s")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return

    # Load model
    print("2️⃣  Loading ONNX model...")
    start = time.time()
    try:
        model = ORTModelForCustomTasks.from_pretrained(model_name)
        model_time = time.time() - start
        load_time = tokenizer_time + model_time
        print(f"   ✅ Model loaded in {model_time:.2f}s")
        print(f"   Total load: {load_time:.2f}s")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return

    print()

    # Single query
    print("3️⃣  Embedding single query...")
    query = QUERIES[0]
    start = time.time()
    try:
        input_q = tokenizer([query], padding=True, truncation=True, return_tensors="np")
        output = model(**input_q)
        embed_time = time.time() - start

        # Extract embedding from output (ONNX returns dict with output tensors)
        # BGE-M3 typically returns 'last_hidden_state' or 'sentence_embedding'
        print(f"   Query: {query}")
        print(f"   ✅ Embedded in {embed_time:.2f}s")
        print(f"   Output keys: {output.keys()}")

        # Try to find the embedding tensor
        if hasattr(output, 'last_hidden_state'):
            embedding = output.last_hidden_state[0, 0]  # First token of first sequence
            print(f"   Embedding shape: {embedding.shape}")
            print(f"   Embedding dims: {len(embedding)}")
            print(f"   Sample values (first 5): {embedding[:5]}")
        elif isinstance(output, dict):
            for key, value in output.items():
                print(f"   {key} shape: {value.shape}")

    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return

    print()

    # Batch
    print(f"4️⃣  Embedding batch ({len(QUERIES)} queries)...")
    start = time.time()
    try:
        input_batch = tokenizer(QUERIES, padding=True, truncation=True, return_tensors="np")
        output_batch = model(**input_batch)
        batch_time = time.time() - start
        avg_time = batch_time / len(QUERIES)
        print(f"   ✅ Batch in {batch_time:.2f}s ({avg_time:.2f}s per query)")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return

    print()
    print("📊 Lambda Simulation")
    print("-" * 80)
    print(f"Cold start: {load_time + embed_time:.2f}s")
    print(f"Warm query: {embed_time:.2f}s")
    print()

    if load_time + embed_time < 15:
        print(f"✅ Cold start acceptable")
    else:
        print(f"⚠️  Cold start slow")

    if embed_time < 5:
        print(f"✅ Warm requests fast")
    else:
        print(f"⚠️  Warm requests acceptable")

    print()
    print("="*80)


def test_embedding_latency_transformers(model_name: str):
    """Test transformers model latency."""

    print("="*80)
    print(f"Testing Transformers: {model_name}")
    print("="*80)
    print()

    # Test 1: Model load time (Lambda cold start equivalent)
    print("1️⃣  Loading model...")
    start = time.time()
    try:
        model = SentenceTransformer(model_name)
        load_time = time.time() - start
        print(f"   ✅ Model loaded in {load_time:.2f}s")
    except Exception as e:
        print(f"   ❌ Failed to load model: {e}")
        return

    print()

    # Test 2: Single query embedding (warm)
    print("2️⃣  Embedding single query (warm)...")
    query = QUERIES[0]
    start = time.time()
    try:
        embedding = model.encode(query)
        embed_time = time.time() - start
        print(f"   Query: {query}")
        print(f"   ✅ Embedded in {embed_time:.2f}s")
        print(f"   Embedding dims: {len(embedding)}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return

    print()

    # Test 3: Batch embedding (multiple queries)
    print(f"3️⃣  Embedding batch ({len(QUERIES)} queries)...")
    start = time.time()
    try:
        embeddings = model.encode(QUERIES)
        batch_time = time.time() - start
        avg_time = batch_time / len(QUERIES)
        print(f"   ✅ Batch in {batch_time:.2f}s ({avg_time:.2f}s per query)")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return

    print()

    # Test 4: Summary for Lambda
    print("4️⃣  Lambda Simulation")
    print("-" * 80)
    print(f"Cold start (first query):")
    print(f"  Model load: {load_time:.2f}s")
    print(f"  + Embed query: {embed_time:.2f}s")
    print(f"  = Total: {load_time + embed_time:.2f}s")
    print()
    print(f"Warm requests (after cache):")
    print(f"  Embed query: {embed_time:.2f}s")
    print()

    # Verdict
    cold_total = load_time + embed_time
    warm_total = embed_time

    print("📊 Verdict:")
    if cold_total < 15:
        print(f"   ✅ Cold start acceptable ({cold_total:.2f}s < 15s)")
    else:
        print(f"   ⚠️  Cold start slow ({cold_total:.2f}s >= 15s)")

    if warm_total < 5:
        print(f"   ✅ Warm requests fast ({warm_total:.2f}s < 5s)")
    elif warm_total < 10:
        print(f"   ⚠️  Warm requests acceptable ({warm_total:.2f}s < 10s)")
    else:
        print(f"   ❌ Warm requests too slow ({warm_total:.2f}s >= 10s)")

    print()
    print("="*80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_embedding_latency.py <model_name> [--onnx] [--transformers]")
        print()
        print("Examples:")
        print("  python test_embedding_latency.py gpahal/bge-m3-onnx-int8 --onnx")
        print("  python test_embedding_latency.py BAAI/bge-m3 --transformers")
        sys.exit(1)

    model_name = sys.argv[1]
    use_onnx = "--onnx" in sys.argv
    use_transformers = "--transformers" in sys.argv

    # Auto-detect if neither specified
    if not use_onnx and not use_transformers:
        if "onnx" in model_name.lower():
            use_onnx = True
        else:
            use_transformers = True

    if use_onnx:
        if not ONNX_AVAILABLE:
            print("❌ ONNX backend not available. Install: pip install optimum onnxruntime")
            sys.exit(1)
        test_embedding_latency_onnx(model_name)
    else:
        if not TRANSFORMERS_AVAILABLE:
            print("❌ Transformers backend not available. Install: pip install sentence-transformers")
            sys.exit(1)
        test_embedding_latency_transformers(model_name)
