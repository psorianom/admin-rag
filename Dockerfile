# Lambda function with Retrieval API + BGE-M3 embeddings
# CPU-only (no CUDA) for Lambda environment
# Using standard Python image (not Lambda-specific) for better build compatibility
# The final artifact can still be deployed to Lambda

FROM python:3.11-slim

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create Lambda task root (mimic Lambda structure)
ENV LAMBDA_TASK_ROOT=/var/task
RUN mkdir -p ${LAMBDA_TASK_ROOT}

# Install CPU-only PyTorch FIRST to avoid CUDA dependencies
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu

# Install Poetry and export plugin
RUN pip install --no-cache-dir poetry poetry-plugin-export

# Copy Poetry config files
COPY pyproject.toml poetry.lock ${LAMBDA_TASK_ROOT}/

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Export lambda group dependencies, filter CUDA packages, and install
# Filter out nvidia-* packages and torch (already installed as CPU-only)
RUN poetry export --only lambda --without-hashes -o requirements.txt && \
    grep -v "nvidia-" requirements.txt | grep -v "^torch==" > requirements-cpu.txt && \
    pip install --no-cache-dir -r requirements-cpu.txt && \
    rm -rf ~/.cache/pip requirements.txt requirements-cpu.txt

# Pre-download ONNX BGE-M3 model (~700MB) to avoid runtime downloads
RUN python -c "from optimum.onnxruntime import ORTModelForCustomTasks; from transformers import AutoTokenizer; ORTModelForCustomTasks.from_pretrained('gpahal/bge-m3-onnx-int8'); AutoTokenizer.from_pretrained('BAAI/bge-m3')"

# Copy entire project
COPY . ${LAMBDA_TASK_ROOT}/

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Set Lambda handler
CMD ["app.lambda_handler"]
