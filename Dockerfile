# Lambda function with FastHTML + ONNX BGE-M3

# Use AWS Lambda Python 3.11 runtime
FROM public.ecr.aws/lambda/python:3.11

# Install system dependencies (if needed for ONNX)
RUN yum install -y gcc-c++ make && yum clean all

# Install Python dependencies
RUN pip install --no-cache-dir \
    fasthtml \
    mangum \
    optimum[onnxruntime] \
    transformers \
    requests \
    haystack-ai \
    qdrant-haystack

# Copy application code
COPY src/retrieval/app.py ${LAMBDA_TASK_ROOT}/

# Copy retrieval module (for imports)
COPY src/retrieval/ ${LAMBDA_TASK_ROOT}/retrieval/
COPY src/retrieval/retrieve.py ${LAMBDA_TASK_ROOT}/

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Set Lambda handler
CMD ["app.lambda_handler"]
