import time
import os
from huggingface_hub import snapshot_download
from optimum.onnxruntime import ORTModelForCustomTasks

# Define local paths and repository details
MODEL_PATH = "./model"
MODEL_REPO = "gpahal/bge-m3-onnx-int8"
MODEL_FILENAME = "model_quantized.onnx"

def setup_local_model():
    """Download model if it doesn't exist locally."""
    if not os.path.exists(MODEL_PATH):
        print(f"Downloading model from {MODEL_REPO} to {MODEL_PATH}...")
        snapshot_download(repo_id=MODEL_REPO, local_dir=MODEL_PATH, local_dir_use_symlinks=False)
    else:
        print(f"Model already exists at {MODEL_PATH}")

def test_loading_without_filename():
    """Test model loading performance WITHOUT the file_name parameter."""
    print(f"\n--- Testing: Loading from '{MODEL_PATH}' WITHOUT `file_name` ---")
    start_time = time.time()
    try:
        model = ORTModelForCustomTasks.from_pretrained(MODEL_PATH)
        end_time = time.time()
        print(f"✅ Success! Time taken: {end_time - start_time:.2f} seconds")
        return model is not None
    except Exception as e:
        end_time = time.time()
        print(f"❌ Failed after {end_time - start_time:.2f} seconds. Error: {e}")
        return False

def test_loading_with_filename():
    """Test model loading performance WITH the file_name parameter."""
    print(f"\n--- Testing: Loading from '{MODEL_PATH}' WITH `file_name='{MODEL_FILENAME}'` ---")
    start_time = time.time()
    try:
        model = ORTModelForCustomTasks.from_pretrained(MODEL_PATH, file_name=MODEL_FILENAME)
        end_time = time.time()
        print(f"✅ Success! Time taken: {end_time - start_time:.2f} seconds")
        return model is not None
    except Exception as e:
        end_time = time.time()
        print(f"❌ Failed after {end_time - start_time:.2f} seconds. Error: {e}")
        return False

if __name__ == "__main__":
    print("="*80)
    print("Setting up local model files (if needed)...")
    setup_local_model()
    print("="*80)
    
    print("\nStarting model loading performance tests...")
    
    # Run the test without the explicit filename
    test_loading_without_filename()
    
    # Run the test with the explicit filename
    test_loading_with_filename()

    print("\n---")
    print("Conclusion: This test measures the time taken by `from_pretrained`.")
    print("A significant difference in time would confirm that providing the `file_name`")
    print("parameter avoids a slow discovery process and proves the hypothesis.")
    print("="*80)
