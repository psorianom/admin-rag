# FastHTML on Lambda using AWS Lambda Web Adapter
FROM public.ecr.aws/docker/library/python:3.11-slim-bullseye

# Install Lambda Web Adapter as extension
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

# Lambda has read-only filesystem except /tmp - redirect HOME for Haystack telemetry
ENV HOME=/tmp
# Disable Haystack telemetry completely (alternative approach)
ENV HAYSTACK_TELEMETRY_ENABLED=False

# Install build tools for packages with C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install CPU-only PyTorch FIRST
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu

# Install Poetry
RUN pip install --no-cache-dir poetry poetry-plugin-export

# Copy Poetry files
COPY pyproject.toml poetry.lock ./

# Export and install dependencies
RUN poetry export --only lambda --without-hashes -o requirements.txt && \
    grep -v "nvidia-" requirements.txt | grep -v "^torch==" > requirements-cpu.txt && \
    pip install --no-cache-dir -r requirements-cpu.txt && \
    rm -rf requirements.txt requirements-cpu.txt

# Pre-download ONNX model and tokenizer to specific local paths
# This avoids all caching and network issues at runtime.
RUN python -c "from huggingface_hub import snapshot_download; \
    snapshot_download(repo_id='gpahal/bge-m3-onnx-int8', local_dir='/app/model', local_dir_use_symlinks=False); \
    snapshot_download(repo_id='BAAI/bge-m3', local_dir='/app/tokenizer', local_dir_use_symlinks=False, ignore_patterns=['*.safetensors', '*.bin'])"

# Copy application code
COPY . .

# Pre-create .haystack directory in /tmp to avoid runtime errors
RUN mkdir -p /tmp/.haystack

# Run FastHTML app normally (Lambda Web Adapter handles the Lambda integration)
CMD ["python", "-m", "src.retrieval.app"]
