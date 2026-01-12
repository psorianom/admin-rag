# Admin RAG - French Labor Law Assistant

**Status**: In Development | **Live API**: Coming Soon

Agentic RAG system for French labor law questions, combining Code du travail and KALI conventions (collective agreements).

**Example question**: "What is my période d'essai préavis if I have worked more than a year and I'm in informatics (Syntec convention)?"

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  Code du travail (11,644 chunks)  │  KALI Conventions (14,154 chunks)  │
│  Légifrance XML → Parsed JSONL     │  7 major conventions              │
└──────────────────┬──────────────────────────────────┬──────────────────┘
                   │                                  │
                   ▼                                  ▼
         ┌─────────────────────────────────────────────────┐
         │     BGE-M3 Embeddings (1024 dims)              │  [Complete]
         │     Generated on vast.ai GPU (~$0.20)          │
         └─────────────────┬───────────────────────────────┘
                           │
                           ▼
         ┌─────────────────────────────────────────────────┐
         │          Qdrant Vector Database                 │  [Deployed]
         │     Cloud: 25,798 vectors (523MB/1GB free)     │
         │     Collections: code_travail, kali             │
         └─────────────────┬───────────────────────────────┘
                           │
         ┌─────────────────┴───────────────────────────────┐
         │                                                  │
         ▼                                                  ▼
┌──────────────────────┐                     ┌──────────────────────────┐
│   Retrieval API      │  [Coming Soon]      │   Agentic Layer (LLM)   │  [Planned]
│   AWS Lambda         │                     │   Multi-step reasoning  │
│   FastHTML + ONNX    │                     │   Convention detection  │
│   API Gateway        │                     │   Dual-source retrieval │
└──────────────────────┘                     └──────────────────────────┘
         │                                                  │
         └─────────────────┬────────────────────────────────┘
                           ▼
                  ┌─────────────────┐
                  │   Web Interface │  [Planned]
                  │   Chat UI       │
                  └─────────────────┘
```

## Why This Project?

Existing French legal RAG systems (like AgentPublic/legi) use fixed-window chunking that splits legal articles arbitrarily. This project takes a different approach:

**Key Features**:
- **Semantic Chunking**: Preserves legal article structure (not arbitrary 5000-char windows)
- **Dual Collections**: Separate Code du travail & KALI for proper legal hierarchy
- **Agentic Routing**: LLM agent decides which collection to query and how to synthesize
- **Production-Ready**: Deployed on AWS Lambda with Qdrant Cloud (not just local)
- **Cost-Optimized**: Pay-per-request Lambda + vast.ai GPU for embeddings (~$0.20 total)

**Corpus Size**:
- 25,798 legal chunks (11,644 Code du travail + 14,154 KALI)
- 7 major collective agreements (Syntec, Métallurgie, HCR, etc.)
- 1024-dim BGE-M3 embeddings (523MB in Qdrant Cloud)

## Key Design Decisions & Reasoning

### Separate Collections (not merged)
**Decision**: Code du travail and KALI in separate Qdrant collections

**Reasoning**: Enables explicit agent routing logic. Convention rules override base labor code, so the agent needs to:
1. Check Code du travail first (general rules)
2. Query specific convention (e.g., Syntec IDCC 1486)
3. Compare and synthesize (convention > code)

Without separation, the vector store would return mixed results, making it impossible to implement proper legal hierarchy.

### Semantic Chunking (not fixed windows)
**Decision**: Chunk at article/section level, preserving legal structure

**Reasoning**:
- Legal citations reference articles, not arbitrary text spans
- Preserves complete legal concepts (don't split mid-paragraph)
- More interpretable results for legal professionals
- **Trade-off**: 11,644 chunks vs AgentPublic's 33,000+ (they use 5000-char fixed windows)
- **Benefit**: Better for our agentic approach (agent needs to understand article boundaries)

### Config-Based Qdrant Connection
**Decision**: Single config file for cloud/local switching

**Reasoning**:
- **Local development**: Fast iteration with Docker Qdrant (`http://localhost:6333`)
- **Production**: Qdrant Cloud (managed, persistent, no server maintenance)
- **Switch via**: `config/qdrant_config.json` → Change `"type": "cloud"` or `"local"`
- **No code changes**: Same retrieval scripts work in both environments

### BGE-M3 Embeddings
**Decision**: BAAI/bge-m3 (1024 dims)

**Reasoning**:
- Validated by [AgentPublic/legi dataset](https://huggingface.co/datasets/AgentPublic/legi) on French legal text
- Multilingual (French-optimized)
- Good balance: performance vs size (1024 dims vs 768 for base models)
- Sentence-transformers support (easy to use)

### Lambda Deployment (not EC2)
**Decision**: AWS Lambda with Docker + ONNX-quantized BGE-M3

**Reasoning**:
- **Latency test**: ONNX quantized model → 58ms per query (acceptable for RAG)
- **Cost**: Pay-per-request vs always-on EC2 ($5-20/month)
- **Scaling**: Auto-scales, no server management
- **Trade-off**: 3GB RAM limit (required CPU-only PyTorch, no CUDA)

### Vast.ai for Embeddings
**Decision**: Generate embeddings on GPU cloud, index locally

**Reasoning**:
- **Embedding generation**: Compute-bound, needs GPU (25,798 chunks × 1024 dims)
- **Indexing**: I/O-bound, fast on CPU (~1 minute locally)
- **Cost**: $0.10-0.30 for full corpus on vast.ai (15-20 min) vs hours locally
- **Simplified workflow**: Upload JSONL → Generate → Download (no Docker-in-Docker complexity)

## Quick Start

### Try It Locally (Local Development)

```bash
# 1. Clone repository
git clone https://github.com/psorianom/admin-rag.git
cd admin-rag

# 2. Install Poetry (if needed)
curl -sSL https://install.python-poetry.org | python3 -

# 3. Option A: Use pre-embedded JSONL files (RECOMMENDED - no raw data needed)
#    Place code_travail_chunks.jsonl and kali_chunks.jsonl in data/processed/
#    (Contact maintainer for access - 40MB total)

make setup           # Install deps + start local Qdrant
make ingest-only     # Index pre-embedded vectors (fast, ~1 minute)

# 4. Option B: Full pipeline from raw data (requires 10GB XML dumps)
#    Download raw data (see Data Sources below) → Place in data/raw/

make all             # Parse + embed + index (slow, requires GPU or vast.ai)
```

### Try It Online (Coming Soon)

Once Lambda deployment is complete:
```bash
curl https://api.admin-rag.example.com/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Quelle est la durée du préavis de démission?",
    "collection": "code_travail",
    "top_k": 5
  }'
```

**Note**: Public API endpoint will be available after Lambda deployment (in progress).

## Prerequisites

- **Python**: 3.10+
- **Docker**: For Qdrant vector store
- **Poetry**: Dependency management
- **Disk space**: ~10GB for raw data + processed outputs
- **RAM**: 4-6GB minimum (for embeddings)

## Data Sources

### Code du travail
Download from [data.gouv.fr LEGI dataset](https://www.data.gouv.fr/fr/datasets/legi-codes-lois-et-reglements-consolides/):
```bash
# Extract to data/raw/code_travail_LEGITEXT000006072050/
```

### KALI (Conventions collectives)
Download KALI corpus from [data.gouv.fr](https://www.data.gouv.fr/fr/datasets/kali-conventions-collectives-nationales/):
```bash
# Extract to data/raw/kali/kali/global/
```

## Project Structure

```
admin-rag/
├── data/
│   ├── raw/           # Original XML from Legifrance
│   ├── processed/     # Cleaned, chunked JSONL documents
│   └── eval/          # Evaluation datasets
├── src/
│   ├── ingestion/     # Data extraction & processing (Phase 1)
│   ├── retrieval/     # RAG components (Phase 2)
│   ├── agents/        # Agentic layer (Phase 3)
│   └── evaluation/    # Quality assessment (Phase 4)
├── scripts/           # Utility scripts
├── notebooks/         # Exploration & experiments
├── configs/           # Configuration files
├── tests/             # Unit tests
├── Makefile           # Pipeline automation
├── FLOW.md            # Development log & decisions
└── TODO.md            # Project roadmap
```

## Makefile Targets

### Main Workflows

```bash
make all              # Run full pipeline (setup → parse → ingest)
make setup            # Install dependencies + start Qdrant
make parse            # Parse Code du travail + KALI (Phase 1)
make ingest           # Embed and index into Qdrant (Phase 2)
make ingest-only      # Ingest from existing JSONL files (skip parsing)
make status           # Check pipeline status
```

**If you already have parsed JSONL files (no raw data needed):**
```bash
# Place files in data/processed/:
#   - code_travail_chunks.jsonl (16MB)
#   - kali_chunks.jsonl (24MB)

make setup           # Install deps + start Qdrant
make ingest-only     # Embed and index (skips parsing)
```

This is ideal for:
- Moving between machines (40MB vs 10GB raw data)
- Cloud GPU instances (vast.ai) - just upload JSONL files
- Sharing with collaborators

### Individual Steps

```bash
make parse-code-travail    # Parse Code du travail only
make parse-kali            # Parse KALI conventions only
make ingest-code-travail   # Ingest Code du travail only
make ingest-kali           # Ingest KALI only (when implemented)
```

### Utilities

```bash
make start-qdrant     # Start Qdrant Docker container
make stop-qdrant      # Stop Qdrant
make clean            # Remove cache files
make clean-processed  # Remove processed JSONL files
make clean-qdrant     # Remove Qdrant storage (destructive!)
```

## Development Phases

### Phase 1: Data Pipeline (Complete)
- Parsed 41,815 Code du travail articles → 11,644 current chunks
- Parsed 289,936 KALI articles → 14,154 chunks (7 major conventions)
- Semantic chunking strategy preserving legal structure
- Rich metadata: hierarchy, section titles, dates, status

**Output**:
- `data/processed/code_travail_chunks.jsonl` (11,644 chunks)
- `data/processed/kali_chunks.jsonl` (14,154 chunks)

### Phase 2: Retrieval Foundation (Complete)
- **Vector Store**: Qdrant Cloud (25,798 vectors deployed, 523MB/1GB used)
- **Embedding Model**: BGE-M3 (1024 dims, French-optimized)
- **Ingestion Pipelines**: Haystack 2.x with pre-computed embedding support
  - `ingest_code_travail.py` - 11,644 chunks → `code_travail` collection
  - `ingest_kali.py` - 14,154 chunks → `kali` collection
- **Vast.ai Automation**: GPU-based embedding generation (~$0.10-0.30)
  - `scripts/run_vast_ingestion.py` - Full automation
  - `scripts/embed_chunks.py` - Standalone embedding script
- **Config System**: Cloud/local Qdrant switching via `config/qdrant_config.json`
- Separate collections for explicit agent routing
- Full automation via Makefile

**Total: 25,798 chunks indexed with BGE-M3 embeddings**

### Phase 3a: Lambda Deployment (In Progress)
- **Status**: Building Docker image for AWS Lambda
- **Infrastructure**: Terraform configuration ready (Lambda + API Gateway)
- **Docker Image**: CPU-only PyTorch + ONNX BGE-M3 + Haystack
- **Expected Latency**: ~58ms per query (based on ONNX benchmarks)

**Next Steps**:
- Lambda function deployed to AWS
- Public API endpoint via API Gateway
- `/retrieve` endpoint for semantic search

### Phase 3b: Agentic Layer (Planned)
- Multi-step reasoning workflow with LLM (Claude/Mistral)
- Convention identification tool
- Dual-source retrieval (Code du travail + KALI)
- Rule comparison and synthesis
- Conversational interface

### Phase 4: Evaluation & Quality (Planned)
- Test dataset creation
- Retrieval quality tuning
- Citation system (article references)
- Edge case handling
- Web UI for chat interface

## Tech Stack

### Core Technologies
- **Language**: Python 3.10+
- **Dependency Management**: Poetry
- **RAG Framework**: Haystack 2.x
- **Vector Store**: Qdrant Cloud (free tier 1GB)
- **Embeddings**: BGE-M3 via sentence-transformers (1024 dims)
- **Data Format**: XML → JSONL
- **Automation**: Make

### Deployment (In Progress)
- **Compute**: AWS Lambda (3GB RAM)
- **API**: API Gateway (REST)
- **Infrastructure**: Terraform
- **Docker**: CPU-only PyTorch + ONNX quantized BGE-M3
- **Monitoring**: CloudWatch (coming soon)

## Documentation

- **FLOW.md**: Development log with implementation details and decisions
- **TODO.md**: Project roadmap and task breakdown
- **CLAUDE.md**: Instructions for Claude Code (coding assistant)

## Current Status

**What's Working Now**:
- Data parsing pipeline: 25,798 legal chunks (Code du travail + KALI)
- BGE-M3 embeddings: 1024-dim vectors for semantic search
- Qdrant Cloud: Deployed and indexed (523MB/1GB used)
- Local development: Full Makefile automation for ingestion
- Vast.ai integration: GPU-based embedding generation ($0.10-0.30)

**In Progress**:
- Lambda Docker image (building now)
- Terraform infrastructure (ready to deploy)
- API Gateway endpoint (pending Lambda deployment)

**Coming Soon**:
- Public retrieval API (semantic search endpoint)
- Agentic layer with LLM (Claude/Mistral)
- Web UI for conversational queries
- Citation system with article references

### Running Embedding Generation on vast.ai (Optional)

Already done for this project, but if you want to regenerate embeddings or use different models:

```bash
# 1. Setup vast.ai CLI
pip install vastai
vastai set api-key YOUR_KEY  # Get from https://cloud.vast.ai/account/

# 2. Run automated embedding generation
poetry run python scripts/run_vast_ingestion.py
```

The script automatically:
- Finds best GPU (≥24GB VRAM, good dlperf/score)
- Uploads JSONL files + embedding script (40MB)
- Generates BGE-M3 embeddings on GPU
- Compresses and downloads embedded JSONL files
- Destroys instance (or keeps alive with `keep_alive=True`)

**Cost**: ~$0.10-0.30 for 25,798 chunks (15-20 minutes)

**Then locally:**
```bash
gunzip data/processed/*.jsonl.gz
make ingest-only  # Fast local indexing with pre-computed embeddings
```

See `scripts/README.md` for details and troubleshooting.

## Roadmap

**Short-term** (Next 2-4 weeks):
- Complete Lambda deployment with retrieval API
- Integrate LLM agent (Claude/Mistral) for multi-step reasoning
- Build web UI for conversational queries

**Medium-term** (1-3 months):
- Evaluation dataset creation (legal Q&A pairs)
- Retrieval quality tuning (hybrid search, reranking)
- Citation system with article references
- Support for more KALI conventions (currently 7/200+)

**Long-term** (3-6 months):
- Fine-tune embeddings on French legal text
- Multi-turn conversation with context
- Export to PDF/Word with citations
- API rate limiting and authentication

## Contributing

This is currently a personal research project, but contributions and feedback are welcome!

**Ways to contribute**:
- Report issues or bugs
- Suggest features or improvements
- Improve documentation
- Share evaluation datasets or test cases
- Collaborate on legal domain expertise

**Interested in collaborating?** Open an issue or reach out via GitHub.

## License

MIT License (to be added)

## Acknowledgments

- **Data**: [Légifrance](https://www.legifrance.gouv.fr/) via [data.gouv.fr](https://www.data.gouv.fr/)
- **Inspiration**: [AgentPublic/legi](https://huggingface.co/datasets/AgentPublic/legi) for BGE-M3 validation
- **Tools**: [Haystack 2.x](https://haystack.deepset.ai/), [Qdrant](https://qdrant.tech/), [vast.ai](https://vast.ai/)

---

**Status**: Active Development | **Last Updated**: January 2026
