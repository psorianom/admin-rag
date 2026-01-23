# Admin RAG - French Labor Law Assistant

**An intelligent RAG system that answers French labor law questions by combining general law (Code du travail) with collective bargaining agreements (KALI conventions).**

```
Question: "What is my notice period as an IT engineer with 2 years experience?"

Answer: Under the Syntec convention (IDCC 1486), engineers with 2+ years
        get 2 months notice period, which is more favorable than the
        general labor code minimum of 1 month.

        Sources: Convention Syntec Article 4.3, Code du travail L1234-1
```

**Status**: Live on AWS Lambda with Lambda Function URL. Try it at https://zupl7dnbwoqpkamvpxikntjmge0ggnos.lambda-url.eu-west-3.on.aws/

---

## What Makes This Different?

Most legal RAG systems chunk documents arbitrarily. This project preserves legal structure:

- **Semantic Chunking**: Legal articles kept intact, not split mid-paragraph
- **Dual-Source Intelligence**: Separate Code du travail and KALI collections enable smart routing
- **Convention Detection**: LLM automatically identifies which collective agreement applies
- **Answer Synthesis**: GPT-4o-mini generates natural language answers with citations and confidence scores
- **Production Architecture**: AWS Lambda + Qdrant Cloud (not just a local demo)

**25,798 legal chunks** | **7 major conventions** | **BGE-M3 embeddings** | **~€0.0001/query**

## How It Works

```
User Query: "Quelle est la période d'essai pour un ingénieur informatique?"
     │
     ▼
┌─────────────────────┐
│  Routing Agent      │  Detects: IT engineer → Syntec convention (IDCC 1486)
│  (GPT-4o-mini)      │  Strategy: Check Syntec first, then general law
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Multi-Collection   │  Searches Qdrant collections with IDCC filter
│  Retrieval          │  Returns: Top 10 relevant articles (scored)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Answer Generator   │  Synthesizes natural language answer
│  (GPT-4o-mini)      │  Tracks citations, confidence score
└──────────┬──────────┘
           │
           ▼
    "As an IT engineer, your trial period under the Syntec convention
     is 3 months (extendable to 4 months with agreement)..."

     Confidence: 0.92 | Sources: Convention Syntec Article 2.1.3
```

**See [FLOW.md](FLOW.md) for detailed architecture decisions and implementation phases.**

## Quick Start

### Local Development (Recommended)

```bash
# 1. Clone and install dependencies
git clone https://github.com/psorianom/admin-rag.git
cd admin-rag
make setup           # Installs Poetry deps + starts Qdrant Docker

# 2. Configure environment
cp .env.template .env
# Edit .env: Add your OpenAI API key for routing/answer generation
# Qdrant: Use local (default) or add cloud credentials

# 3. Load pre-processed data (40MB JSONL files - contact maintainer)
#    OR parse from raw XML (10GB - see Data Sources section)
make ingest-only     # Index pre-embedded vectors (~1 minute)

# 4. Run web UI
poetry run python -m src.retrieval.app
# Open http://localhost:5001
```

**Try a query**: "Quelle est la période d'essai pour un ingénieur informatique?"

### Prerequisites

- Python 3.10+, Docker, Poetry
- OpenAI API key (for routing and answer generation, ~€0.0001/query)
- 40MB disk space (JSONL files) or 10GB (full raw data)

## System Architecture

**Data**: Code du travail + 7 KALI conventions → 25,798 legal article chunks
**Embeddings**: BGE-M3 (1024-dim, French-optimized) via vast.ai GPU (~€0.20)
**Vector Store**: Qdrant Cloud (free tier, 523MB indexed)
**Routing**: GPT-4o-mini detects conventions, applies metadata filters
**Answer Generation**: GPT-4o-mini synthesizes responses with citations
**Deployment**: AWS Lambda + Function URL (currently fixing timeout issues)

**Total Cost**: ~€0.0001 per query (routing + generation)

See [FLOW.md](FLOW.md) for complete development history, architecture diagrams, and design decisions.

---

## Project Status

**Working**:
- Data pipeline: 25,798 chunks parsed and indexed
- Intelligent routing: Convention detection from job roles
- Multi-collection retrieval: IDCC metadata filtering
- Answer generation: Natural language responses with citations
- Local web UI: FastHTML interface on port 5001
- Test coverage: 33 passing tests (routing, retrieval, generation)

**In Progress**:
- AWS Lambda deployment (timeout issues with API Gateway)
- Switching to Lambda Function URL for longer request times

**Coming Soon**:
- Public web interface
- Multi-turn conversations
- Enhanced citation links to Légifrance

## Key Features

**Intelligent Routing**
- Auto-detects applicable collective agreement from job role mentions
- Routes queries to appropriate collections (code_travail, kali, or both)
- Applies IDCC metadata filters for convention-specific results

**Multi-Source Retrieval**
- Searches both general labor law and conventions
- Understands legal hierarchy (convention rules override general law)
- Merges and ranks results by relevance

**Answer Synthesis**
- Generates natural language French answers from legal text
- Tracks which sources support each claim
- Provides confidence scores (0-1) with visual indicators
- Highlights cited sources in the UI

**Production-Grade Architecture**
- Semantic chunking preserves legal article structure
- BGE-M3 embeddings optimized for French legal text
- Efficient ONNX quantized model for CPU inference
- Comprehensive test coverage (33 tests)

## Tech Stack

**Data**: Haystack 2.x, BGE-M3 embeddings, Qdrant vector store
**Intelligence**: OpenAI GPT-4o-mini (routing + generation)
**Deployment**: AWS Lambda, Terraform, Docker
**Development**: Python 3.10+, Poetry, Make

See [FLOW.md](FLOW.md) for detailed component decisions and implementation phases.

---

## Documentation

- **[FLOW.md](FLOW.md)**: Complete development history, architecture diagrams, and technical decisions
- **[TODO.md](TODO.md)**: Project roadmap and task breakdown
- **[terraform/README.md](terraform/README.md)**: AWS deployment guide

---

## Data Sources & Reproduction

**Raw Data**:
- [Code du travail](https://www.data.gouv.fr/fr/datasets/legi-codes-lois-et-reglements-consolides/) (10GB XML)
- [KALI Conventions](https://www.data.gouv.fr/fr/datasets/kali-conventions-collectives-nationales/) (10GB XML)

**Pre-processed JSONL** (40MB, contact maintainer for access):
- `code_travail_chunks.jsonl` (11,644 chunks)
- `kali_chunks.jsonl` (14,154 chunks)

**Makefile Commands**:
```bash
make all              # Full pipeline: parse raw XML → embed → index
make ingest-only      # Index from pre-processed JSONL (recommended)
make status           # Check pipeline status
```

**Vast.ai GPU Embedding** (optional, if regenerating embeddings):
```bash
poetry run python scripts/run_vast_ingestion.py  # ~€0.20 for 25,798 chunks
```

## Roadmap

**Immediate**: Fix Lambda timeout issues, deploy public web interface
**Short-term**: Multi-turn conversations, enhanced citations to Légifrance
**Medium-term**: Hybrid search (BM25 + semantic), evaluation dataset, more KALI conventions
**Long-term**: Fine-tuned embeddings, PDF export with citations, API authentication

---

## Contributing

Contributions welcome! This is a research project exploring intelligent legal RAG systems.

**Ways to help**:
- Report bugs or suggest features (open an issue)
- Share evaluation datasets or test cases
- Improve documentation
- Contribute legal domain expertise

---

## Acknowledgments

**Data**: [Légifrance](https://www.legifrance.gouv.fr/) via [data.gouv.fr](https://www.data.gouv.fr/)
**Inspiration**: [AgentPublic/legi](https://huggingface.co/datasets/AgentPublic/legi) for BGE-M3 validation
**Tools**: Haystack, Qdrant, vast.ai, OpenAI

---

**License**: MIT (to be added) | **Last Updated**: January 2026
