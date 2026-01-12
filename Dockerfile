# Lambda function with Retrieval API + BGE-M3 embeddings
# CPU-only (no CUDA) for Lambda environment

FROM public.ecr.aws/lambda/python:3.11

# Install system dependencies
RUN yum install -y gcc-c++ make && yum clean all

# Install CPU-only PyTorch FIRST (before Poetry) to avoid CUDA dependencies
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy project files
COPY pyproject.toml ${LAMBDA_TASK_ROOT}/

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Configure Poetry to not create virtualenvs (we're in a container)
# Install remaining dependencies (torch already installed above)
RUN poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-root && \
    rm -rf ~/.cache/pip && \
    rm -rf ~/.cache/pypoetry/artifacts && \
    rm -rf ~/.cache/pypoetry/cache

# Copy application code
COPY src/retrieval/app.py ${LAMBDA_TASK_ROOT}/

# Copy retrieval module and config
COPY src/retrieval/ ${LAMBDA_TASK_ROOT}/retrieval/
COPY config/ ${LAMBDA_TASK_ROOT}/config/

# Set Lambda handler
CMD ["app.lambda_handler"]
