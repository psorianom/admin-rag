# Admin RAG - French Labor Law Assistant

Agentic RAG system for French labor law questions, combining Code du travail and KALI conventions (collective agreements).

**Example question**: "What is my période d'essai préavis if I have worked more than a year and I'm in informatics (Syntec convention)?"

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/psorianom/admin-rag.git
cd admin-rag

# 2. Install Poetry (if needed)
curl -sSL https://install.python-poetry.org | python3 -

# 3. Download raw data (see Data Sources below)
# Place in data/raw/

# 4. Run full pipeline
make all
```

That's it! The Makefile handles:
- ✅ Installing dependencies
- ✅ Starting Qdrant vector store
- ✅ Parsing XML → structured JSONL
- ✅ Generating BGE-M3 embeddings
- ✅ Indexing into vector database

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

### ✅ Phase 1: Data Pipeline (Complete)
- Parsed 41,815 Code du travail articles → 11,644 current chunks
- Parsed 289,936 KALI articles → 14,154 chunks (7 major conventions)
- Semantic chunking strategy preserving legal structure
- Rich metadata: hierarchy, section titles, dates, status

**Output**:
- `data/processed/code_travail_chunks.jsonl` (11,644 chunks)
- `data/processed/kali_chunks.jsonl` (14,154 chunks)

### ✅ Phase 2: Retrieval Foundation (Complete)
- **Vector Store**: Qdrant (Docker-based, running at http://localhost:6333)
- **Embedding Model**: BGE-M3 (1024 dims, French-optimized)
- **Ingestion Pipelines**: Haystack 2.x with pre-computed embedding support
  - `ingest_code_travail.py` - 11,644 chunks → `code_travail` collection
  - `ingest_kali.py` - 14,154 chunks → `kali` collection
- **Vast.ai Automation**: GPU-based embedding generation (~$0.10-0.30)
  - `scripts/run_vast_ingestion.py` - Full automation
  - `scripts/embed_chunks.py` - Standalone embedding script
- Separate collections for explicit agent routing
- Full automation via Makefile

**Total: 25,798 chunks indexed with BGE-M3 embeddings**

### ⏳ Phase 3: Agentic Layer (Pending)
- Multi-step reasoning workflow
- Convention identification tool
- Dual-source retrieval (Code du travail + KALI)
- Rule comparison and synthesis

### ⏳ Phase 4: Evaluation & Quality (Pending)
- Test dataset creation
- Retrieval quality tuning
- Citation system
- Edge case handling

## Tech Stack

- **Language**: Python 3.10+
- **Dependency Management**: Poetry
- **RAG Framework**: Haystack 2.x
- **Vector Store**: Qdrant (Docker)
- **Embeddings**: BGE-M3 via sentence-transformers
- **Data Format**: XML → JSONL
- **Automation**: Make

## Key Design Decisions

### Why separate collections (not merged)?
Agent needs explicit routing logic: "Check Code du travail first, then query specific convention". This enables side-by-side comparison where convention rules override base labor code.

### Why semantic chunking (not fixed windows)?
Preserves legal structure (articles, alinéas). Matches how legal professionals cite law. More interpretable results.

### Why BGE-M3?
Validated by [AgentPublic/legi dataset](https://huggingface.co/datasets/AgentPublic/legi) on French legal text. Multilingual, good French performance, reasonable size (1024 dims).

### Why not use pre-processed AgentPublic dataset?
We want flexibility to experiment with chunking strategies. Their fixed-window approach (5000 chars + overlap) creates 2.9x more chunks but splits mid-paragraph.

## Documentation

- **FLOW.md**: Development log with implementation details and decisions
- **TODO.md**: Project roadmap and task breakdown
- **CLAUDE.md**: Instructions for Claude Code (coding assistant)

## Current Status

**Completed**:
- ✅ Phase 1: Data parsing pipeline (11,644 + 14,154 chunks)
- ✅ Phase 2: Vector database with embeddings (25,798 chunks indexed)
  - Qdrant running at http://localhost:6333
  - BGE-M3 embeddings (1024 dims)
  - Two collections: `code_travail` and `kali`
- ✅ Vast.ai automation for GPU-based embedding
- ✅ Makefile automation (`make ingest-only` for pre-computed embeddings)
- ✅ Comprehensive documentation (FLOW.md, TODO.md, CLAUDE.md)

**Next Steps**:
- Phase 3: Build basic retrieval pipeline
- Test retrieval quality with sample labor law queries
- Evaluate chunking strategy performance
- Consider improvements (reranking, hybrid search, parent-child chunking)

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

## License

To be determined

## Contributing

This is a personal research project. See FLOW.md for development context.
