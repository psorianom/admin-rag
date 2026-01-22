# Development Flow

This document tracks what we've built and the decisions made along the way.

## Project Overview

Building an agentic RAG system in French for labor law questions, combining:
- **Code du travail** (French labor code)
- **KALI corpus** (Convention collectives - e.g., Syntec for IT workers)

**Example question**: "What is my période d'essai préavis if I have worked more than a year and I'm in informatics (Syntec convention)?"

## Phase 0: Project Setup ✅

### Structure Created
```
admin-rag/
├── data/
│   ├── raw/           # Original Legifrance XML
│   ├── processed/     # Cleaned JSONL output
│   └── eval/          # Evaluation datasets
├── src/
│   ├── ingestion/     # Data extraction & processing
│   ├── retrieval/     # RAG components
│   ├── agents/        # Agentic layer
│   └── evaluation/    # Quality assessment
├── notebooks/         # Experiments
├── configs/           # Configuration
└── tests/
```

### Tech Stack
- **Dependency management**: Poetry
- **RAG framework**: Haystack 2.x
- **Data format**: XML → JSONL
- **Language**: Python 3.10+

## Phase 1: Data Pipeline (In Progress)

### 1.1 Understanding the Data ✅

**Raw data location**: `data/raw/code_travail_LEGITEXT000006072050/`

**Structure discovered**:
- 41,815 article XML files (`article/`)
- 10,567 section XML files (`section_ta/`)
- 2 texte files (root metadata)

**Key XML structure**:
```xml
<ARTICLE>
  <NUM>L6234-2</NUM>              <!-- Article number -->
  <ETAT>ABROGE</ETAT>             <!-- Status: VIGUEUR, MODIFIE, ABROGE -->
  <DATE_DEBUT>2018-04-15</DATE_DEBUT>
  <DATE_FIN>2019-01-01</DATE_FIN>
  <BLOC_TEXTUEL>
    <CONTENU>...</CONTENU>         <!-- Article text -->
  </BLOC_TEXTUEL>
  <CONTEXTE>
    <!-- Hierarchical structure: Partie > Livre > Titre > Chapitre -->
  </CONTEXTE>
</ARTICLE>
```

### 1.2 Section Metadata Enhancement ✅

**Decision**: Parse section files to enrich articles with section titles

**Why**: Section titles provide more specific context than generic hierarchy
- Example: "Paragraphe 3: Modalités particulières pour les travailleurs intérimaires"
- Better than just "Sous-section 2"

**Implementation**:
- `src/ingestion/parsers/section_parser.py` - Extracts section titles and article mappings
- Builds `article_id → section_title` mapping
- Output: `data/processed/article_to_section_mapping.json`

### 1.3 Article Parser ✅

**Implementation**: `src/ingestion/parsers/code_travail_parser.py`

**What it does**:
- Parses all 41,815 article XML files
- Filters out obsolete articles (`ETAT=ABROGE`)
- Extracts:
  - Article ID and number
  - Current state (VIGUEUR, MODIFIE)
  - Validity dates
  - Article text content
  - Hierarchical context (Partie, Livre, Titre, Chapitre)
  - Section title (from mapping)
- Output: `data/processed/code_travail_articles.jsonl`

**Article schema**:
```json
{
  "article_id": "LEGIARTI000036802200",
  "article_num": "L6234-2",
  "etat": "VIGUEUR",
  "date_debut": "2018-04-15",
  "date_fin": null,
  "text": "Le fait d'exercer des fonctions...",
  "hierarchy": {
    "partie": "Partie législative",
    "livre": "Livre II : L'apprentissage",
    "titre": "Titre III : Centres de formation...",
    "chapitre": "Chapitre IV : Dispositions pénales"
  },
  "section_title": "Paragraphe 3: Modalités particulières...",
  "source": "code_travail",
  "obsolete": false
}
```

### 1.4 Main Parsing Script ✅

**Implementation**: `src/ingestion/parse_code_travail.py`

**Workflow**:
1. Parse sections → build article-to-section mapping
2. Parse articles with section enrichment
3. Save to JSONL with full metadata

**To run**:
```bash
poetry run python src/ingestion/parse_code_travail.py
```

### 1.5 Fixing Duplicate Articles ✅

**Problem discovered**: Same article number appeared multiple times with different states:
- MODIFIE (historical versions with past `date_fin`)
- VIGUEUR (current version with `date_fin = "2999-01-01"`)

**Solution**: Filter to keep only current versions
- Keep articles where `date_fin == "2999-01-01"` or `date_fin is None`
- Removed 19,907 historical versions (keeping only 11,494 current articles)

**Results after fix**:
- 11,494 valid current articles (no duplicates)
- 30,321 filtered out (ABROGE + historical versions)
- 100% have section metadata

### 1.6 Article Length Analysis ✅

**Statistics on clean data**:
- Average article length: 91.5 tokens
- 99.1% (11,393) under 500 tokens
- 0.9% (101) need chunking
- Longest: 17,205 tokens

**Decision**: Only chunk the 0.9% that exceed 500 tokens

### 1.7 Chunking Implementation ✅

**Implementation**: `src/ingestion/chunkers/article_chunker.py`

**Strategy**:
- Articles < 500 tokens → keep as single chunk
- Articles ≥ 500 tokens → split by semantic boundaries:
  - Double newlines (paragraph breaks)
  - Numbered lists (1°, 2°, 3° common in French legal text)
  - Combine paragraphs until ~500 token limit
  - Never split mid-paragraph (preserve coherence)

**Output schema** (adds to article schema):
```json
{
  ...all article fields...,
  "chunk_id": "LEGIARTI000036802200_0",
  "chunk_index": 0,
  "total_chunks": 3,
  "is_chunked": true
}
```

**To run**:
```bash
poetry run python src/ingestion/chunkers/article_chunker.py
```

**Output**: `data/processed/code_travail_chunks.jsonl` (~11,600 chunks)

### 1.8 KALI Corpus Exploration ✅

**Data location**: `data/raw/kali/kali/global/`

**Structure discovered**: Identical to Code du travail
- 289,936 article XML files
- 105,871 section files
- 86,996 texte files (conventions)
- Uses `KALI` prefix instead of `LEGI`

**Key difference**: Articles belong to conventions identified by IDCC numbers
- Found via `<CONTENEUR nature="IDCC" num="1486">` in article XML
- Each IDCC = one convention collective

**Decision**: Parse top 10 conventions by sector importance instead of just Syntec

### 1.9 KALI Parser Implementation ✅

**Implementation**: `src/ingestion/parsers/kali_parser.py`

**Target conventions** (top 10 by sector):
| IDCC | Convention | Sector |
|------|------------|--------|
| 3248 | Métallurgie | Metal/tech industries |
| 1486 | Syntec | IT services, consulting, engineering |
| 1979 | HCR | Hotels, cafés, restaurants |
| 1597 | Bâtiment | Construction (10+ employees) |
| 1090 | Automobile | Auto services, repair shops |
| 2216 | Commerce alimentaire | Food retail |
| 0016 | Transports routiers | Road transport |
| 0044 | Industries chimiques | Chemical industries |
| 2120 | Banque | Banking |
| 0573 | Commerces de gros | Wholesale trade |

**Parser features**:
- Filters by IDCC numbers
- Removes obsolete articles (ABROGE, PERIME)
- Filters historical versions (keeps only date_fin = "2999-01-01")
- Extracts convention metadata (IDCC, convention name, title)
- Same structure as code_travail_parser

**Results**:
- **13,033 valid articles** from 7/10 conventions
- 276,903 filtered out (other conventions + obsolete)
- Breakdown:
  - Métallurgie (3248): 4,230 articles
  - Services automobile (1090): 3,363 articles
  - Bâtiment (1597): 1,782 articles
  - Syntec (1486): 1,045 articles
  - Banque (2120): 1,000 articles
  - Commerce alimentaire (2216): 992 articles
  - HCR (1979): 621 articles

**Missing conventions** (3/10): Transports routiers, Industries chimiques, Commerces de gros
- Likely different IDCC numbers or in non_vigueur folder

**To run**:
```bash
poetry run python src/ingestion/parsers/kali_parser.py
```

**Output**: `data/processed/kali_articles.jsonl`

### 1.10 KALI Chunking (Ready)

**Implementation**: Reuses `src/ingestion/chunkers/article_chunker.py`
- Same chunking logic as Code du travail
- Works on any JSONL with article structure

**Main script**: `src/ingestion/parse_kali.py`
- Parses KALI articles
- Chunks them automatically

**To run**:
```bash
poetry run python src/ingestion/parse_kali.py
```

**Output**: `data/processed/kali_chunks.jsonl`

### 1.11 KALI Chunking ✅

**Results**:
- 13,033 articles processed
- 96.1% (12,531) kept as-is
- 3.9% (502) chunked into multiple pieces
- **14,154 total chunks** output
- Saved to `data/processed/kali_chunks.jsonl`

### 1.12 AgentPublic/legi Dataset Exploration ✅

**Discovery**: HuggingFace dataset with pre-processed French legal corpus
- Dataset: `AgentPublic/legi` (1.26M legal document chunks)
- Pre-computed BGE-M3 embeddings (1024 dims)
- Parquet format with rich metadata

**Investigation results**:
- Scanned 1.26M records to find Code du travail
- Found **33,418 Code du travail chunks** (vs our 11,644)
- **Ratio: 2.9x more chunks** from same source data

**Their approach**:
- Fixed-window chunking: 5000 chars per chunk
- 250 char overlap between chunks
- Uses LangChain chunking utilities
- Extracts citation links (`<LIENS>` tags) as JSON
- Includes ministry, category, nota fields

**Our approach**:
- Semantic chunking: paragraph/numbered list boundaries
- ~500 tokens per chunk (~2000 chars)
- No overlap (cleaner citations)
- 99.1% of articles kept whole (only 0.9% chunked)
- Rich metadata: hierarchy + section titles

**Decision: Keep our processed data**

**Reasons**:
1. **Experimentation flexibility**: Can test different chunking strategies
2. **Semantic chunking**: Preserves legal structure better
3. **Richer metadata**: Hierarchy + section titles vs citations
4. **No overlap**: Cleaner for citations/attribution
5. **Simplicity**: Modern RAG favors simpler chunking

**What we adopt from them**:
- ✅ **BGE-M3 embedding model** (validated on French legal text)
- 📝 Future: Parse `<LIENS>` tags for article cross-references (Phase 5)

## Phase 1 Complete! ✅

**Final dataset:**
- Code du travail: **11,644 chunks**
- KALI (7 conventions): **14,154 chunks**
- **Total: 25,798 chunks**

### Data Pipeline Flow Diagram

```mermaid
graph LR
    A[Raw XML Files] --> B[Parse Sections]
    B --> C[Build Article-to-Section Mapping]
    C --> D[Parse Articles]
    D --> E[Filter Current Versions]
    E --> F[Analyze Article Lengths]
    F --> G{Length > 500 tokens?}
    G -->|No| H[Keep as Single Chunk]
    G -->|Yes| I[Semantic Chunking]
    H --> J[Output JSONL]
    I --> J
    J --> K[Final Chunks Dataset]

    subgraph "Code du travail"
    A
    B
    C
    D
    E
    F
    G
    H
    I
    J
    end

    subgraph "KALI Conventions"
    A2[Raw XML Files] --> D2[Parse with IDCC Filter]
    D2 --> E2[Filter Current Versions]
    E2 --> F2[Analyze Lengths]
    F2 --> G2{Length > 500 tokens?}
    G2 -->|No| H2[Keep as Single Chunk]
    G2 -->|Yes| I2[Semantic Chunking]
    H2 --> J2[Output JSONL]
    I2 --> J2
    J2 --> K2[KALI Chunks Dataset]
    end
```

### Architecture Decision: Separate Collections vs Merged Corpus

**Decision: Keep datasets SEPARATE for proper agent routing**

**Why NOT merge:**
- Agent needs explicit routing logic
- Query workflow: "Check Code du travail first, then query specific convention"
- Can compare rules side-by-side (hierarchy: convention ≥ Code du travail)
- Better observability (which source was queried?)

**Phase 2 approach:**
- Separate vector collections:
  - `code_travail` collection (11,644 chunks)
  - `kali_<idcc>` collections per convention (7 collections)
- Agent tools:
  - `retrieve_code_travail(query)`
  - `retrieve_convention(query, idcc)`
  - `identify_convention(job_role, industry)`

## Phase 2: Retrieval Foundation (In Progress)

### 2.1 Vector Store Setup ✅

**Decision: Qdrant**

**Why Qdrant:**
- Fast (Rust-based) and free (open source)
- Excellent metadata filtering (critical for multi-source RAG)
- Native collection support (separate code_travail/kali collections)
- Perfect scale for 26K vectors
- Good Haystack integration

**Setup:**
```bash
docker run -d -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage:z \
  --name qdrant qdrant/qdrant
```

**Running at**: `http://localhost:6333`
**Dashboard**: `http://localhost:6333/dashboard`

### 2.2 Embedding Model Selection ✅

**Decision: BGE-M3** (BAAI/bge-m3)

**Why BGE-M3:**
- Validated by AgentPublic/legi on French legal text
- Multilingual support (excellent French performance)
- 1024 dimensions (good balance of quality/size)
- Sentence-transformers compatible

**Dependencies installed:**
- `qdrant-haystack` (4.2.0)
- `sentence-transformers` (3.4.1)
- `torch` (2.9.1) + `transformers` (4.57.3)

### 2.3 Ingestion Pipeline ✅

**Implementation**: `src/retrieval/ingest_code_travail.py`

**Pipeline architecture:**
1. Load chunks from JSONL
2. Convert to Haystack Documents with rich metadata
3. Generate BGE-M3 embeddings (auto-detects GPU/CPU)
4. Index into Qdrant collection

**Metadata preserved:**
- Article identifiers (article_id, article_num)
- Status (etat, dates)
- Hierarchy (partie, livre, titre, chapitre)
- Section titles
- Chunk information (for multi-chunk articles)
- Source identifier

**Collections:**
- `code_travail`: 11,644 chunks (script: `ingest_code_travail.py`)
- `kali`: 14,154 chunks (script: `ingest_kali.py`)

### Ingestion Pipeline Architecture Diagram

```mermaid
graph LR
    JSONL[JSONL Files<br/>with embeddings] --> Loader[Load Documents]

    Loader --> Check{Has pre-computed<br/>embeddings?}

    Check -->|Yes| Skip[Skip Embedding<br/>Load from JSONL]
    Check -->|No| Embed[BGE-M3 Embedder<br/>Generate 1024-dim vectors]

    Skip --> Docs[Haystack Documents<br/>with metadata + embeddings]
    Embed --> Docs

    Docs --> Writer[Document Writer]
    Writer --> Qdrant[Qdrant Collection]

    Config[qdrant_config.json] -.->|Connection settings| Qdrant

    subgraph "Metadata Preserved"
        Meta[article_id<br/>article_num<br/>hierarchy<br/>section_title<br/>chunk_info<br/>source]
    end

    Docs -.-> Meta

    style JSONL fill:#e1f5ff
    style Qdrant fill:#d4edda
    style Check fill:#fff3cd
```

### 2.4 Pipeline Automation ✅

**Implementation**: `Makefile`

**Purpose**: Simplify reproduction and deployment

**Why Makefile (not Airflow/Prefect)?**
- Pipeline runs once or infrequently (not scheduled)
- Linear dependencies (no complex DAG)
- Small scale (26K documents)
- No need for orchestration overhead

**Key targets:**
```bash
make all      # Full pipeline: setup → parse → ingest
make setup    # Install deps + start Qdrant
make parse    # Phase 1: XML → JSONL
make ingest   # Phase 2: Embed → Qdrant
make status   # Check pipeline status
```

**Benefits:**
- One-command reproduction on new machines
- Clear documentation of dependencies
- Built-in error checking (data presence, Qdrant status)
- Clean separation of phases

**Key target: `make ingest-only`**
- Ingests from existing JSONL files (skips parsing)
- No raw XML data needed (only 40MB JSONL vs 10GB XML)
- Perfect for cloud GPU instances or moving between machines
- Enables testing different embedding models without re-parsing

### 2.5 Vast.ai Automation ✅

**Challenge**: Local GPU insufficient for BGE-M3 embedding generation (requires 24GB VRAM)

**Solution**: Automated vast.ai workflow for cloud GPU embedding

**Implementation**: `scripts/run_vast_ingestion.py`

**Workflow**:
1. Search for GPU instances (≥24GB VRAM, good dlperf score)
2. Provision instance (~$0.20-0.50/hr)
3. Upload JSONL files + embedding script
4. Generate BGE-M3 embeddings on GPU
5. Compress and download embedded JSONL files
6. Destroy instance (or keep alive for testing)

**Architecture decision: Simplified embedding-only workflow**
- **Problem**: Docker-in-Docker complexity, private repo access
- **Solution**: Upload `embed_chunks.py` directly, no git clone needed
- **Benefits**: Faster setup, lower costs (gzip compression), no GitHub required

**Key learnings**:
- Use `dlperf` (tested) not `inet_down` (self-reported, often fake)
- Sort by `score` (ML performance) not just price
- SSH connectivity testing required (status "running" ≠ SSH ready)
- SCP uses `-P` (uppercase), SSH uses `-p` (lowercase)
- PyTorch in Docker images may need upgrading for compatibility

**Files created**:
- `scripts/embed_chunks.py` - Standalone embedding generator
- `scripts/run_vast_ingestion.py` - Full automation
- Updated ingestion scripts to detect pre-computed embeddings

**Cost**: ~$0.10-0.30 for full embedding generation (25,798 chunks)

### Vast.ai Automation Workflow Diagram

```mermaid
sequenceDiagram
    participant Local as Local Machine
    participant Vast as Vast.ai API
    participant Instance as GPU Instance
    participant Storage as Cloud Storage

    Local->>Vast: Search for GPU instances (≥24GB VRAM)
    Vast-->>Local: Return available instances
    Local->>Vast: Create instance (~$0.30/hr)
    Vast-->>Local: Instance ID + SSH credentials

    loop Wait for SSH Ready
        Local->>Instance: Test SSH connectivity
        Instance-->>Local: Connection status
    end

    Local->>Instance: SCP upload JSONL files (40MB)
    Local->>Instance: SCP upload embed_chunks.py
    Local->>Instance: SSH: pip install dependencies
    Local->>Instance: SSH: python embed_chunks.py

    Instance->>Instance: Load BGE-M3 model (2.7GB)
    Instance->>Instance: Generate embeddings (1024 dims)
    Instance->>Instance: Write to JSONL + gzip compress

    Local->>Instance: SCP download compressed JSONL
    Instance-->>Local: Embedded JSONL files (~140MB+170MB)

    Local->>Vast: Destroy instance (or keep alive)
    Vast-->>Local: Instance destroyed
```

### 2.6 Embedding Generation & Indexing ✅

**Embeddings generated on vast.ai:**
- Model: BAAI/bge-m3 (1024 dimensions)
- GPU: 24GB VRAM instances (RTX 3090/4090 class)
- Time: ~15-20 minutes for 25,798 chunks
- Size: ~140MB (code_travail) + ~170MB (kali) with embeddings

**Local indexing:**
- Detected pre-computed embeddings in JSONL
- Skipped embedding step (just load + write to Qdrant)
- Time: ~2 minutes total (fast, CPU-bound)

**Collections created:**
- `code_travail`: 11,644 chunks with BGE-M3 embeddings
- `kali`: 14,154 chunks with BGE-M3 embeddings
- **Total: 25,798 vectors indexed in Qdrant**

**Qdrant dashboard**: `http://localhost:6333/dashboard`

### 2.7 Data Quality Observations

**Chunking analysis:**
- Code du travail: 60% <500 chars (short articles), mean 587 chars
- KALI: 46% <500 chars, mean 1130 chars
- 175 empty chunks in KALI (1.2% - parsing failures)
- 7 oversized chunks in code_travail (>8000 chars - annexes with tables)
- 278 oversized chunks in KALI (2%)

**Decision**: Proceed with current chunking, refactor if retrieval quality suffers
- Can always re-chunk and re-embed later
- Most chunks are reasonable size
- Issues affect <3% of data
- Better to validate with real queries first

**Future improvements**:
- Parent-child chunking for tiny articles
- Better annex handling (tables, lists)
- Filter empty chunks before embedding

## Phase 2 Complete! ✅

**Achievements:**
- ✅ Qdrant vector store running locally
- ✅ BGE-M3 embeddings generated (25,798 chunks)
- ✅ All data indexed with rich metadata
- ✅ Vast.ai automation for GPU embedding
- ✅ Pre-computed embedding detection in pipelines
- ✅ Makefile automation for reproducibility

**Ready for Phase 3**: Build retrieval pipeline and test with labor law queries

## Phase 3: Retrieval Pipeline ✅

**Completed:**
- ✅ Built BM25 retrieval pipeline (no embeddings needed locally)
- ✅ Created FastHTML web UI for testing
- ✅ Implemented metadata filtering (by IDCC, collection)
- ✅ Tested with sample labor law queries

**Key decisions:**
- BM25 keyword search for local development (no GPU needed)
- Embedding via external API (Cohere/HF) for inference
- Pre-computed BGE-M3 embeddings in Qdrant for semantic search later

## Phase 3b: Infrastructure & Deployment (In Progress)

### Architecture Decision Evolution

**Budget:** €75 for 3 months (~€25/month)

#### Testing Phase: ONNX BGE-M3 int8 Performance ✅

**Model tested:** `gpahal/bge-m3-onnx-int8` (quantized int8 ONNX model)

**Results:**
- Model size: ~700MB (fits Lambda)
- Cold start: 4.99s (model load + tokenizer)
- Warm query: **0.06s** (60ms!) ✅
- Embeddings confirmed: 1024-dim dense vectors
- Quality: int8 quantization (~1-2% accuracy loss, acceptable for demo)

**Key insight:** CPU inference with ONNX int8 is **fast enough** for production UI.

**Dependencies:** `optimum[onnxruntime]` + `transformers`

#### Final Architecture: AWS Lambda + Qdrant Cloud (Serverless)

**Tech stack:**
- **Compute**: AWS Lambda (10GB RAM) - FastHTML web app + BGE-M3 ONNX inference
- **Vector DB**: Qdrant Cloud free tier (523MB vector storage, fits 25,798 docs)
- **Web framework**: FastHTML (Python)
- **Embeddings**: BGE-M3 ONNX int8 model (local in Lambda, 60ms latency)
- **IaC**: Terraform (learn AWS Lambda + serverless infrastructure)

**Why Lambda over EC2:**
- True serverless: €0 for bursty/low traffic (free tier: 1M requests/month)
- Auto-scales: Multiple concurrent users = parallel Lambda instances
- Fast warm latency: 60ms query embedding (vs 5-8s on EC2 t4g.small CPU)
- Qdrant Cloud free tier: 523MB fits our data perfectly

**Why this beats EC2:**
- EC2 t4g.small CPU: 5-8s embedding time (too slow for demo)
- Lambda with ONNX int8: 0.06s embedding time (production-ready)
- Cost: €0 vs €10/month
- Complexity: Similar (Terraform for both)

**Deployment flow:**
1. Terraform provisions Lambda function, IAM roles, API Gateway
2. Package Lambda: Docker image with FastHTML + ONNX model + dependencies
3. Deploy to Lambda with 10GB RAM allocation
4. Qdrant Cloud: Create free tier cluster, upload vectors
5. Web app: Query → Lambda embeds → Qdrant Cloud searches → results

### Infrastructure Architecture Diagram

```mermaid
graph TB
    User["👤 User"]
    APIGW["API Gateway<br/>(Public HTTP Endpoint)"]
    Lambda["AWS Lambda<br/>(10GB RAM)<br/>FastHTML + ONNX BGE-M3"]
    Qdrant["Qdrant Cloud<br/>(Free Tier)<br/>523MB Vectors"]
    ECR["ECR Repository<br/>(Docker Images)"]

    User -->|HTTP Request| APIGW
    APIGW -->|Invoke Function| Lambda
    Lambda -->|Load Image| ECR
    Lambda -->|Vector Search| Qdrant
    Qdrant -->|Results| Lambda
    Lambda -->|HTTP Response| APIGW
    APIGW -->|Response| User
```

### Terraform Files Dependency Diagram

```mermaid
graph TD
    Provider["provider.tf<br/>(AWS Config)"]
    Variables["variables.tf<br/>(Lambda Settings)"]
    IAM["iam.tf<br/>(Roles & Permissions)"]
    Lambda_File["lambda.tf<br/>(Lambda + ECR)"]
    APIGateway["api_gateway.tf<br/>(HTTP Endpoint)"]
    Outputs["outputs.tf<br/>(Display URLs)"]

    Provider -->|Required by all| Variables
    Variables -->|Used by| IAM
    Variables -->|Used by| Lambda_File
    Variables -->|Used by| APIGateway
    IAM -->|Role ARN to| Lambda_File
    Lambda_File -->|Function ARN to| APIGateway
    APIGateway -->|Stage URL to| Outputs
    Lambda_File -->|ECR URL to| Outputs
    Lambda_File -->|Function name to| Outputs
```

**Note**: This cost breakdown was superseded. See the complete "Cost Analysis: Production Infrastructure" section after Phase 5 for current pricing with Lambda Function URL architecture.

## Phase 3b: Infrastructure & Deployment ✅

### 3b.1 Qdrant Configuration System ✅

**Implementation**: `config/qdrant_config.json`

**Feature**: Unified config supporting both local and cloud Qdrant

**Config structure**:
```json
{
  "type": "cloud",  // or "local"
  "cloud": {
    "url": "https://...",
    "api_key": "..."
  },
  "local": {
    "url": "http://localhost:6333",
    "api_key": null
  }
}
```

**Benefits**:
- Single config file, easy switching between environments
- No code changes needed (just edit config)
- Supports credentials management
- Works with both ingestion and retrieval

### 3b.2 Updated Ingestion Scripts ✅

**Changes**:
- `src/retrieval/ingest_code_travail.py`: Now reads config, supports cloud/local
- `src/retrieval/ingest_kali.py`: Same improvements
- Both auto-detect config type and print which Qdrant being used

**New function**: `load_qdrant_config()`
- Reads from `config/qdrant_config.json`
- Returns config dict with URL and API key
- Used in `create_qdrant_store()` function

### 3b.3 Semantic Search Retrieval ✅

**Implementation**: `src/retrieval/retrieve.py` rewritten

**Key changes**:
- Switched from BM25 (keyword) to semantic search (embeddings)
- Now uses `QdrantEmbeddingRetriever` instead of `InMemoryBM25Retriever`
- Encodes queries with BGE-M3: `embedder.encode(query).tolist()`
- Searches Qdrant cloud or local by similarity
- Same API - `retrieve(query, collection, top_k)` works identically

**Architecture**:
```python
# 1. Get Qdrant document store (cloud or local)
document_store = get_document_store("code_travail")

# 2. Get BGE-M3 embedder (cached globally)
embedder = get_embedder()  # Loads once, reuses

# 3. Encode query to embedding
query_embedding = embedder.encode(query).tolist()

# 4. Search in Qdrant by similarity
retriever.run({"query_embedding": query_embedding, "top_k": 10})
```

### Semantic Search Retrieval Pipeline Diagram

```mermaid
graph TB
    Query[User Query] --> Embedder[BGE-M3 Embedder]
    Embedder --> QEmbed[Query Embedding<br/>1024 dimensions]

    QEmbed --> Qdrant[Qdrant Document Store]

    subgraph "Qdrant Collections"
        CodeTravail[code_travail<br/>11,644 vectors]
        KALI[kali<br/>14,154 vectors]
    end

    Qdrant --> CodeTravail
    Qdrant --> KALI

    CodeTravail --> Similarity[Cosine Similarity Search]
    KALI --> Similarity

    Similarity --> TopK[Top-K Results<br/>with metadata]
    TopK --> Results[Formatted Results<br/>Article + Score + Context]

    Config[qdrant_config.json] -.->|Cloud/Local| Qdrant

    style Query fill:#e1f5ff
    style Results fill:#d4edda
    style Qdrant fill:#fff3cd
```

### 3b.4 Lambda & Infrastructure ✅

**Files created**:
- `Dockerfile`: Lambda runtime with FastHTML + ONNX BGE-M3
- `src/retrieval/app.py`: FastHTML web UI with Lambda handler
- `terraform/`: Complete IaC for AWS Lambda + API Gateway
  - `provider.tf`: AWS provider config
  - `variables.tf`: Lambda settings (3GB memory, 30s timeout)
  - `iam.tf`: IAM roles and permissions
  - `lambda.tf`: Lambda function + ECR repository
  - `api_gateway.tf`: HTTP endpoint for public access
  - `outputs.tf`: Display URLs after deployment
  - `README.md`: Deployment guide (8-step walkthrough)

**Tech stack**:
- Compute: AWS Lambda (3GB RAM - account limit)
- Web app: FastHTML + Mangum ASGI adapter
- Embeddings: BGE-M3 via sentence-transformers
- Vector DB: Qdrant Cloud API (free tier)
- IaC: Terraform 1.x with AWS provider 5.0

**Deployment ready**: Just needs:
1. Run ingest scripts to populate cloud
2. Build Docker image: `docker build -t admin-rag-retrieval .`
3. Push to ECR (credentials obtained from Terraform output)
4. Lambda automatically pulls image and starts serving

### 3b.5 Qdrant Cloud Setup ✅

**Account created** with free tier:
- Cluster URL: `https://0444a90a-65a9-4e85-979a-adf963861027.eu-west-2-0.aws.cloud.qdrant.io:6333`
- API Key: (configured in .env file)
- Storage: 1GB limit (523MB used by 25,798 vectors)
- Cost: €0/month

### 3b.6 Configuration Refactoring ✅

**Problem**: Configuration with secrets in JSON file committed to git

**Solution**: Migrated to environment variables
- Created `.env.template` with placeholder values (safe to commit)
- Created `src/config/constants.py` to load from `.env` using python-dotenv
- Updated all scripts to import from constants module:
  - `src/retrieval/ingest_code_travail.py`
  - `src/retrieval/ingest_kali.py`
  - `src/retrieval/retrieve.py`
- Added `config/qdrant_config.json` to `.gitignore`
- Created `config/qdrant_config.json.template` for reference

**Benefits**:
- Secrets never committed to git
- Easy local/cloud switching via QDRANT_TYPE env var
- Standard practice for production deployments
- Works seamlessly with Docker (env injection)

### 3b.7 Qdrant Cloud Ingestion ✅

**Vectors uploaded**:
- Code du travail: 11,644 chunks (took ~43 seconds)
- KALI: 14,154 chunks (took ~64 seconds)
- Total: 25,798 vectors in cloud (523MB/1GB used)

**Both collections live and ready for queries**

### 3b.8 Documentation Enhancements ✅

**README.md**:
- Added ASCII architecture diagram showing data flow
- Added detailed design decisions with reasoning:
  - Separate collections vs merged
  - Semantic chunking vs fixed windows
  - Config-based Qdrant connection
  - BGE-M3 embeddings
  - Lambda deployment vs EC2
  - Vast.ai for embeddings
- Added status markers (Complete, In Progress, Coming Soon)
- Added .env setup instructions
- Removed all emojis for professional presentation

**FLOW.md**:
- Added mermaid diagrams:
  - Data pipeline flow (Phase 1)
  - Vast.ai automation workflow (Phase 2)
  - Ingestion pipeline architecture (Phase 2)
  - Semantic search retrieval pipeline (Phase 3)

**Repository cleanup**:
- Removed CLAUDE.md from git (kept local only, added to .gitignore)
- Repository now ready for public sharing

### 3b.9 Lambda Docker Container ✅

**Challenge**: Package FastHTML app + ONNX BGE-M3 model for Lambda deployment

**Key fixes implemented**:

1. **Docker context optimization**:
   - Created `.dockerignore` to exclude `data/`, `qdrant_storage/` (was 4.89GB!)
   - Build context reduced from 4.89GB → ~50MB
   - Build time improved from cancelled/stuck → ~6 minutes

2. **ONNX int8 quantized model integration**:
   - Switched from `sentence-transformers` (huge) to `optimum[onnxruntime]` + `transformers`
   - Model: `gpahal/bge-m3-onnx-int8` (~700MB, tested in Phase 3b.1)
   - Pre-downloaded model in Dockerfile (baked into image, no runtime downloads)
   - Fixed embedding extraction: uses `dense_vecs` output (1024-dim dense embeddings)

3. **Import structure improvements**:
   - Removed `sys.path.insert()` hack from app.py
   - Uses proper absolute imports: `from src.retrieval.retrieve import retrieve`
   - Works consistently across local dev, Docker, and Lambda environments

4. **Error handling and logging**:
   - Added logging configuration to app.py
   - Exception handling logs full stack traces
   - Errors visible in both UI and console logs

5. **Fixed Haystack import paths**:
   - Corrected: `from haystack_integrations.components.retrievers.qdrant import QdrantEmbeddingRetriever`
   - Updated: `ORTModelForCustomTasks` (matches test script)

**Docker build command**:
```bash
docker build -t admin-rag-lambda .
```

**Local testing**:
```bash
docker run -it -p 5001:5001 --env-file .env admin-rag-lambda python -m src.retrieval.app
```

**Result**: Working Docker container with:
- FastHTML web UI on port 5001
- ONNX BGE-M3 int8 embeddings (60ms warm query)
- Qdrant Cloud integration
- ~1GB final image size (fits Lambda 10GB limit with headroom)

## Phase 3b Complete! ✅

**Achievements**:
- ✅ Qdrant Cloud setup with 25,798 vectors
- ✅ Configuration refactored to use environment variables
- ✅ ONNX int8 quantized embeddings (700MB model, 60ms latency)
- ✅ Docker container ready for Lambda deployment
- ✅ Proper logging and error handling
- ✅ Documentation updated with architecture diagrams

**Ready for Phase 4**: Deploy to AWS Lambda or proceed with agentic layer

## Phase 4: Intelligent Routing Agent ✅

### Overview
Implemented intelligent query routing agent that:
1. Detects convention-specific queries using OpenAI GPT-4o-mini
2. Auto-maps job roles to IDCC conventions (e.g., "ingénieur informatique" → Syntec 1486)
3. Routes queries to appropriate collections (code_travail, kali, or both)
4. Applies IDCC metadata filtering for convention-specific results

### Implementation Details

**Routing Agent** (`src/agents/routing_agent.py`):
- Uses OpenAI GPT-4o-mini with structured outputs (Pydantic validation)
- Four routing strategies:
  - `code_only`: General labor law questions
  - `kali_only`: Convention-specific questions
  - `both_code_first`: Check general law first, then convention
  - `both_kali_first`: Convention is primary (more favorable rules)
- Detects IDCC conventions from keywords in query
- Deterministic (temperature=0) for consistent routing

**Convention Mapping** (7 conventions indexed):
- 1486: Syntec (IT services, consulting, engineering)
- 3248: Métallurgie (Metallurgy)
- 1979: HCR (Hotels, cafés, restaurants)
- 1597: Bâtiment (Construction)
- 1090: Automobile (Auto services)
- 2216: Commerce alimentaire (Food retail)
- 2120: Banque (Banking)

**Multi-Collection Retrieval** (`src/agents/multi_retriever.py`):
- Executes retrieval on specified collections in order
- Applies IDCC metadata filtering using Qdrant's nested field indexes (`meta.idcc`)
- Merges results from multiple collections
- Sorts by score and returns top-k
- Tags results with collection source and convention info

**Fixed Qdrant Indexing**:
- Recreated kali collection with proper nested field indexes
- Indexes on: `meta.idcc`, `meta.convention_name`, `meta.source`, `meta.article_num`
- Fixed issue where IDCC filtering returned 0 results

**Web UI Updates** (`src/retrieval/app.py`):
- Removed manual collection/convention selector
- Integrated routing agent for automatic decisions
- Displays agent's routing strategy and reasoning
- Shows which convention (IDCC) was detected

### Test Coverage

**18 tests total** (18 passed, 1 skipped):

**Routing Agent Tests** (8 tests):
- ✅ Pydantic validation of routing decisions
- ✅ General query routing (code_only)
- ✅ IT engineer detection (Syntec 1486)
- ✅ Explicit convention routing (kali_only)
- ✅ Fallback on LLM error
- ✅ Singleton pattern

**Multi-Retriever Tests** (10 tests):
- ✅ IDCC filtering with nested meta fields
- ✅ Multi-collection merging and sorting
- ✅ All four routing strategies
- ✅ Result tagging with convention metadata
- ✅ Empty result handling
- ✅ Top-k limiting
- ✅ Score-based sorting
- ✅ Different IDCC values
- ✅ Null IDCC handling

### Example Queries (All French)

**Query 1**: "Quelle est la durée du préavis de démission?"
- Agent: Detects general legal question
- Routing: `code_only`
- Result: General labor law rules

**Query 2**: "Période d'essai pour un ingénieur informatique"
- Agent: Detects IT engineer + Syntec convention (IDCC 1486)
- Routing: `both_kali_first` with IDCC=1486 filter
- Result: Syntec rules (more favorable) + general law

**Query 3**: "Convention Syntec congés payés"
- Agent: Explicit convention mention
- Routing: `kali_only` with IDCC=1486 filter
- Result: Syntec-specific vacation rules

**Query 4**: "Licenciement serveur restaurant"
- Agent: Detects HCR worker (IDCC 1979)
- Routing: `both_kali_first` with IDCC=1979 filter
- Result: HCR convention + general dismissal law

### Costs
- **OpenAI GPT-4o-mini (routing only)**: ~€0.000023 per query
- See "Cost Analysis: Production Infrastructure" section after Phase 5 for complete breakdown

### Files Changed
- `src/agents/routing_agent.py` - Core routing logic (170 lines)
- `src/agents/multi_retriever.py` - Multi-collection retrieval (76 lines)
- `src/retrieval/app.py` - Updated FastHTML UI
- `src/retrieval/ingest_kali.py` - Fixed IDCC indexing
- `src/retrieval/retrieve.py` - Updated demo examples
- `src/config/constants.py` - Added LLM config
- `tests/test_routing_agent.py` - Routing tests
- `tests/test_multi_retriever.py` - Retriever tests
- `.env.template` - Added LLM_PROVIDER and OPENAI_* variables
- `pyproject.toml` - Added openai dependency

## Phase 4 Complete! ✅

**Achievements**:
- ✅ Intelligent routing agent using GPT-4o-mini
- ✅ Auto-IDCC detection from job roles
- ✅ Multi-collection retrieval with metadata filtering
- ✅ 18 passing tests (routing + retrieval)
- ✅ Fixed Qdrant nested field indexing
- ✅ Production-ready cost (see centralized cost table after Phase 5)
- ✅ Full end-to-end testing verified

**Ready for Phase 5**: Answer generation and citations

## Phase 5: Answer Generation & Citations ✅

### Overview
Implemented natural language answer generation from retrieved context with citation tracking and confidence scoring. Answers synthesized using OpenAI GPT-4o-mini, automatically identifying which sources support each claim.

### Implementation Details

**Answer Generator** (`src/agents/answer_generator.py`):
- Generates coherent French answers from top 3 retrieved results
- Uses Pydantic `AnswerWithCitations` model for structured output:
  - `answer`: Natural language response (French)
  - `confidence`: Score 0-1 reflecting answer certainty
  - `citation_indices`: Which results support the answer
  - `reasoning`: Explanation of generation approach
- Temperature=0.7 for natural yet consistent responses
- Validates citation indices to prevent out-of-range references
- Graceful error handling with fallback answers

**Citation Formatting** (`src/agents/citation_formatter.py`):
- `format_citation()`: Converts results to readable citations
  - Code du travail: "Article L1221-19 (Code du travail)"
  - KALI: "Convention Syntec (IDCC 1486) - Article 2.3"
- `get_source_url()`: Placeholder for future Légifrance links

**Web UI Updates** (`src/retrieval/app.py`):
- Added `answer_section()` component displaying generated answer with reasoning
- Added `confidence_badge()` component with color-coded confidence levels:
  - Green (≥0.8): High confidence
  - Yellow (0.6-0.8): Medium confidence
  - Red (<0.6): Low confidence
- Enhanced `result_card()` to highlight cited sources with blue left border
- Updated `/search` endpoint to:
  1. Route query
  2. Retrieve results (top 10)
  3. Generate answer (uses top 3 internally)
  4. Display answer + confidence + sources with highlights

### Design Decisions

✅ **Context Window**: Top 3 results only
- Reduces token usage (~€0.0001 per query vs €0.0002 for 10)
- Most legal answers fit in 3 relevant chunks
- Reduces noise and conflicting sources

✅ **Answer Delivery**: Batch generation
- Simpler implementation, no WebSocket complexity
- Sufficient latency for typical queries (<2 seconds)
- User can explore other sources while reading answer

✅ **Citation Highlighting**: Blue left border
- Subtle, professional appearance (3px solid #007bff)
- Easy visual scanning without clutter
- Consistent with answer section styling

### Test Coverage

**15 new unit tests** in `tests/test_answer_generator.py`:
- ✅ Pydantic model validation (bounds, defaults)
- ✅ Answer generation from results
- ✅ Empty results handling
- ✅ Citation index validation and filtering
- ✅ Top-3 context window enforcement
- ✅ Context building with/without convention info
- ✅ Error handling (graceful fallback)
- ✅ Singleton pattern
- ✅ Multiple citation support
- ✅ Confidence scoring (high/low/medium)
- 1 skipped integration test (requires OpenAI API)

**Total test count**: 33 passing (15 answer + 10 retriever + 8 routing)

### Example Output

Query: "Quelle est la durée du préavis de démission?"

Agent decides: `code_only` (general labor law question)

Retrieved: 5 articles from Code du travail

Generated answer:
```
La durée du préavis de démission est généralement déterminée par la loi,
une convention collective ou un accord collectif. En l'absence de telles
dispositions, elle est fixée selon les usages locaux et professionnels
(Source 1). Par exemple, dans certaines professions comme le journalisme,
le préavis est d'un mois pour une ancienneté de trois ans ou moins,
et de deux mois pour plus de trois ans (Source 2).
```

Confidence: 0.90 (High)
Cited sources: [1, 2] → Article L1237-1, Source 2

UI shows answer with green confidence badge + Sources 1 & 2 highlighted with blue borders.

### Costs

**Per query**:
- Routing agent (GPT-4o-mini): €0.000023
- Answer generation (GPT-4o-mini, ~150 tokens): €0.000100
- **Total**: €0.000123 per query

See "Cost Analysis: Production Infrastructure" section below for complete breakdown including AWS and Qdrant costs.

### Files Changed

**New Files**:
- `src/agents/answer_generator.py` - Answer generation (180 lines)
- `src/agents/citation_formatter.py` - Citation utilities (50 lines)
- `tests/test_answer_generator.py` - 15 comprehensive tests (310 lines)

**Modified Files**:
- `src/retrieval/app.py` - Answer UI integration (65 lines added)
- `FLOW.md` - This documentation

**No changes needed**:
- `pyproject.toml` - openai already included
- `.env` - existing LLM_CONFIG reused

### Verification Checklist

- ✅ AnswerGenerator produces coherent French answers
- ✅ AnswerWithCitations validates all responses
- ✅ Citation indices correctly track sources
- ✅ Confidence scores reflect answer quality
- ✅ UI displays answer + sources with highlighting
- ✅ 33 tests passing (15 new + 18 from Phase 4)
- ✅ All 4 example queries tested end-to-end
- ✅ Cost estimates verified
- ✅ Error handling graceful (fallback answers)

## Phase 5 Complete! ✅

**Achievements**:
- ✅ Answer generation from retrieved context
- ✅ Automatic citation tracking
- ✅ Confidence scoring (0-1)
- ✅ Blue border highlighting for cited sources
- ✅ Comprehensive test coverage
- ✅ Production-ready answer generation layer
- ✅ Minimal cost increase (€0.000123 per query, see cost table below)

**Total system capability**:
1. Intelligent routing (detects conventions)
2. Multi-collection retrieval (code_travail + KALI)
3. Answer generation (GPT-4o-mini synthesis)
4. Citation tracking (sources highlighted)
5. Confidence scoring (visual confidence badges)

**Ready for Phase 6**: AWS Lambda deployment

---

## Cost Analysis: Production Infrastructure

### Complete Cost Breakdown

| Service | Configuration | Free Tier | Current Usage | Monthly Cost | Notes |
|---------|--------------|-----------|---------------|--------------|-------|
| **AWS Lambda** | 3GB RAM, 120s timeout, 5 concurrent max | 1M requests/month<br/>400,000 GB-seconds/month | ~100-1000 requests/month<br/>~10-100 GB-seconds | **€0** | Within free tier for demo/testing. Cold start ~90s, warm ~1-2s |
| **AWS ECR** | Docker image storage | 500MB/month (12 months for new accounts) | ~1GB image | **€0-0.10** | €0.10/GB/month after free tier |
| **Lambda Function URL** | Public HTTPS endpoint | Included with Lambda | N/A | **€0** | No additional cost beyond Lambda invocations |
| **CloudWatch Logs** | Application logging | 5GB ingestion, 5GB storage/month | ~100MB/month | **€0** | Within free tier for low traffic |
| **Qdrant Cloud** | Vector database | 1GB storage, unlimited requests | 523MB (25,798 vectors) | **€0** | Free tier covers full dataset |
| **OpenAI API** | GPT-4o-mini (routing + generation) | None | Variable by query volume | **€0.00012/query** | Routing: €0.000023<br/>Generation: €0.0001 |
| **Vast.ai** | GPU embedding generation (one-time) | None | 25,798 chunks embedded | **€0.20** (paid) | One-time cost, already completed |

### Monthly Cost Estimates by Usage

| Usage Scenario | Queries/Month | Lambda | ECR | OpenAI | **Total/Month** |
|----------------|---------------|--------|-----|--------|----------------|
| **Demo/Testing** | 100 | €0 | €0 | €0.01 | **€0.01** |
| **Light Production** | 1,000 | €0 | €0.10 | €0.12 | **€0.22** |
| **Medium Production** | 10,000 | €0 | €0.10 | €1.23 | **€1.33** |
| **Heavy Production** | 100,000 | €0* | €0.10 | €12.30 | **€12.40** |

*Lambda remains free up to 1M requests/month. Heavy production would use ~10-100k GB-seconds, still within 400k free tier.

### Cost Drivers

**Current (Demo Phase)**: ~€0.01-0.22/month
- Primary cost: OpenAI API (scales with query volume)
- AWS services: Free tier covers all usage
- Qdrant: Free tier sufficient

**Future Optimizations** (if scaling):
1. **Reduce OpenAI calls**: Cache routing decisions for common query patterns
2. **Optimize Lambda**: Reduce cold starts with provisioned concurrency (~€13/month for 1 instance)
3. **Self-host embeddings**: Replace OpenAI with local inference (increases Lambda costs, eliminates API costs)

### One-Time Setup Costs

| Item | Cost | Status |
|------|------|--------|
| Vast.ai GPU embedding generation | €0.20 | ✅ Paid |
| **Total Setup** | **€0.20** | ✅ Complete |

### Comparison: Alternative Architectures

| Architecture | Monthly Cost | Pros | Cons |
|--------------|--------------|------|------|
| **Current: Lambda + Qdrant Cloud** | €0.22 | Serverless, auto-scaling, €0 infra | 90s cold starts |
| EC2 t4g.small + Qdrant Cloud | €10-15 | No cold starts | Always-on cost, slow CPU inference |
| EC2 g4dn.xlarge + self-hosted Qdrant | €250+ | Fast GPU inference | Very expensive, overkill for demo |

**Decision**: Current architecture is optimal for demo and light production use.

---

## Phase 6: AWS Lambda Deployment (In Progress)

### Overview
Deploying the complete RAG system to AWS Lambda with FastHTML UI, using Lambda Web Adapter for seamless integration.

### 6.1 Initial Terraform Infrastructure ✅

**Files created:**
- `terraform/provider.tf` - AWS provider configuration (eu-west-3)
- `terraform/variables.tf` - Lambda settings (3GB RAM, 30s timeout)
- `terraform/iam.tf` - IAM roles and permissions
- `terraform/lambda.tf` - Lambda function + ECR repository
- `terraform/api_gateway.tf` - HTTP endpoint
- `terraform/outputs.tf` - Display deployment URLs
- `terraform/README.md` - 8-step deployment guide

**Infrastructure provisioned:**
- Lambda function: `admin-rag-retrieval` (3GB RAM - account limit)
- ECR repository: `908027388369.dkr.ecr.eu-west-3.amazonaws.com/admin-rag-retrieval`
- API Gateway endpoint: `https://rs3vbew2bh.execute-api.eu-west-3.amazonaws.com/prod`

### 6.2 Docker Image Evolution (Multiple Iterations)

**Approach 1: Manual Lambda Handler**
- Created `handler.py` wrapper for Lambda
- Issue: `Runtime.InvalidEntrypoint` - Lambda couldn't find handler
- Problem: Complex path resolution in Lambda environment

**Approach 2: Lambda Base Image with manylinux wheels**
- Switched to `public.ecr.aws/lambda/python:3.11`
- Tried `--platform manylinux2014_x86_64 --only-binary=:all:` for numpy
- Issue: `apsw==3.51.2.0` has no pre-compiled wheels, requires compilation
- Problem: Amazon Linux 2 has GCC 7.3.1, NumPy 2.x requires GCC >= 9.3

**Approach 3: Multi-stage Build**
- Stage 1: Build on Debian (modern GCC)
- Stage 2: Copy to Lambda runtime
- Works but adds complexity

**Approach 4: AWS Lambda Web Adapter** ✅
- Discovered official AWS example: FastHTML on Lambda
- Uses `public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1`
- Regular Python image + Lambda Web Adapter extension
- No manual Lambda handler needed - FastHTML runs normally
- Simpler: Just `CMD ["python", "-m", "src.retrieval.app"]`

### 6.3 Current Dockerfile (Lambda Web Adapter)

```dockerfile
FROM public.ecr.aws/docker/library/python:3.11-slim-bullseye

# Install Lambda Web Adapter as extension
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

# Lambda has read-only filesystem except /tmp
ENV HOME=/tmp
ENV HAYSTACK_TELEMETRY_ENABLED=False

# Install build tools (for apsw and other C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install PyTorch CPU + dependencies via Poetry
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir poetry poetry-plugin-export

COPY pyproject.toml poetry.lock ./

RUN poetry export --only lambda --without-hashes -o requirements.txt && \
    grep -v "nvidia-" requirements.txt | grep -v "^torch==" > requirements-cpu.txt && \
    pip install --no-cache-dir -r requirements-cpu.txt && \
    rm -rf requirements.txt requirements-cpu.txt

# Pre-download ONNX BGE-M3 model
RUN python -c "from optimum.onnxruntime import ORTModelForCustomTasks; from transformers import AutoTokenizer; ORTModelForCustomTasks.from_pretrained('gpahal/bge-m3-onnx-int8'); AutoTokenizer.from_pretrained('BAAI/bge-m3')"

COPY . .

# Pre-create .haystack directory in /tmp
RUN mkdir -p /tmp/.haystack

CMD ["python", "-m", "src.retrieval.app"]
```

### 6.4 Deployment Issues & Fixes

**Issue 1: Invalid Entrypoint**
- Error: `Runtime.InvalidEntrypoint` - couldn't find `app.lambda_handler`
- Root cause: Using standard Python image without Lambda runtime
- Fix: Switched to Lambda Web Adapter approach

**Issue 2: NumPy GCC Version Mismatch**
- Error: NumPy 2.x requires GCC >= 9.3, Amazon Linux 2 has GCC 7.3.1
- Attempted: manylinux wheels with `--platform` and `--only-binary`
- Problem: `apsw` (FastHTML dependency) has no pre-compiled wheels
- Fix: Use regular Debian image (modern GCC) + Lambda Web Adapter

**Issue 3: Haystack Telemetry Filesystem Error** (Current)
- Error: `OSError: [Errno 30] Read-only file system: '/home/sbx_user1051'`
- Root cause: Haystack tries to write telemetry config to home directory
- Lambda filesystem is read-only except `/tmp`
- Fixes applied:
  - `ENV HOME=/tmp` - redirect home to writable directory
  - `ENV HAYSTACK_TELEMETRY_ENABLED=False` - disable telemetry
  - `RUN mkdir -p /tmp/.haystack` - pre-create directory
- Status: Awaiting rebuild and deployment test

### 6.5 Makefile Deployment Targets ✅

Added to Makefile:
```makefile
docker-build:   Build Docker image with ECR tag
docker-push:    Authenticate and push to ECR
deploy:         Full workflow (build → push → terraform apply)
```

**Usage:**
```bash
make deploy
```

### 6.6 Key Learnings

**Docker for Lambda:**
- AWS Lambda Web Adapter simplifies web framework deployment
- No need for custom Lambda handlers with Mangum
- Regular Python image works with adapter extension
- Debian base image better than Amazon Linux 2 for modern dependencies

**Filesystem constraints:**
- Lambda has read-only filesystem except `/tmp`
- Set `HOME=/tmp` for packages that write config files
- Pre-create directories in Dockerfile to avoid runtime errors

**Dependency challenges:**
- FastHTML → fastlite → apsw (C extension without manylinux wheels)
- Solution: Use Debian base with proper build tools
- Avoid Amazon Linux 2 for packages requiring modern GCC

**Cost efficiency:**
- Test locally FIRST before pushing to AWS
- Each deployment iteration costs time and usage
- `docker run` locally can catch most issues

### Current Status

**Working:**
- ✅ Terraform infrastructure provisioned
- ✅ ECR repository created
- ✅ Docker image builds successfully
- ✅ Lambda Web Adapter integrated
- ✅ Qdrant Cloud fully populated (25,798 vectors)

**Pending:**
- ⏳ Haystack telemetry filesystem fix (rebuild in progress)
- ⏳ Final deployment test
- ⏳ End-to-end Lambda API verification

**Next Steps:**
1. Rebuild Docker image with filesystem fixes
2. Push to ECR
3. Wait for Lambda to pull new image
4. Test API endpoint
5. Verify FastHTML UI loads
6. Test search functionality end-to-end

### Files Changed
- `Dockerfile` - Multiple iterations, now using Lambda Web Adapter
- `Makefile` - Added docker-build, docker-push, deploy targets
- `terraform/*.tf` - Complete infrastructure as code
- `handler.py` - Created then deleted (not needed with adapter)

## Phase 6 Status: In Progress

**Deployment blocked by Haystack telemetry filesystem error - fix applied, awaiting verification**

---

**Ready for Phase 7**: Quality evaluation and user feedback (after deployment complete)

## Next Steps

### Phase 6: Evaluation & Quality (Pending)
- Test dataset creation
- Quality metrics and benchmarking
- User feedback collection
- Fine-tuning for improved routing/answer quality

### Phase 7: Enhancement Features (Pending)
- Streaming answer generation
- Follow-up question suggestions
- Source comparison (Code du travail vs convention)
- Chat history for multi-turn Q&A
- User rating/feedback system

### 6.7 Deployment Troubleshooting & Final Architecture ✅

Deploying the application to AWS Lambda revealed several challenges related to HTTP routing and the Lambda runtime environment. This section documents the issues, the solutions, and the final working architecture.

#### Issue 1: API Gateway Stage Routing (404 Not Found)

- **Symptom**: Initial requests to the public API Gateway URL succeeded for the root path (`/`) but failed with a `404 Not Found` for any other path (e.g., `/search`). Logs confirmed that requests were arriving at the Lambda with a `/prod` prefix (e.g., `GET /prod/search`), which the application's router did not recognize.

- **Architectural Context (`Mangum` vs. `aws-lambda-web-adapter`)**: A key point of clarification was the application's architecture. While `src/retrieval/app.py` contained a `lambda_handler` using the `Mangum` library, the `Dockerfile`'s `CMD` starts a `uvicorn` web server directly. This means the application uses the **AWS Lambda Web Adapter pattern**, where the adapter runs as a sidecar process, converting Lambda events into HTTP requests for the running `uvicorn` server. The `Mangum`-based `lambda_handler` is therefore inactive in the deployed environment.

- **Solution Iteration**:
    1. **Attempt 1 (`AWS_LWA_REMOVE_BASE_PATH`)**: Setting the `AWS_LWA_REMOVE_BASE_PATH=/prod` environment variable in Terraform. This correctly stripped the prefix on the server-side, but did not solve the client-side issue where the browser, making requests from `.../prod/`, would request incorrect absolute paths (e.g., `.../search` instead of `.../prod/search`).
    2. **Attempt 2 (Relative Paths)**: Changing the form's post URL from `hx_post="/search"` to `hx_post="search"`. This was also unreliable, as browser behavior for relative paths differs based on the presence of a trailing slash in the URL (`/prod` vs `/prod/`).
    3. **Final Solution (Stage-Aware Application)**: The most robust solution was to make the application itself aware of the stage it's running in.
        - **Terraform**: An `API_STAGE` environment variable was passed to the Lambda function.
        - **Python**: The application reads `API_STAGE` from `src/config/constants.py` and dynamically prepends it to all routes and generated URLs. This ensures the application always generates correct, absolute paths (e.g., `/prod/search`) that work reliably.

#### Issue 2: Lambda Ephemeral Storage (No Space Left on Device)

- **Symptom**: After fixing the routing, logs showed `IO Error: No space left on device`. The application was trying to download the 570MB embedding model into the Lambda's temporary `/tmp` directory, which is limited to 512MB by default.

- **Root Cause**: The Hugging Face library was not using the model pre-downloaded during the Docker build. Instead, it was attempting to create a new cache at runtime in `/tmp`, its default cache location in this environment.

- **Solution**: Rather than simply increasing the storage (the "easy fix"), the root cause was addressed by creating a consistent cache path.
    - **Dockerfile**: The `ENV HF_HOME /app/cache` instruction was added.
    - **Mechanism**: This forces the Hugging Face library to use `/app/cache` as its cache location during both the `docker build` (when the model is downloaded) and at runtime. The library now finds the model in the expected location and does not attempt to re-download it.

This approach resolved the storage issue without requiring changes to the Lambda resource limits, resulting in a more elegant and efficient solution.

The final deployed architecture is now robust, stage-aware, and correctly configured to handle its dependencies within the Lambda runtime constraints.

#### Issue 3: Lambda Timeout on First Request

- **Symptom**: After fixing the routing and caching issues, the application began to fail with a `Task timed out after 30.66 seconds` error on the first request.
- **Analysis**: A 28-second gap was identified in the logs between the attempt to load the embedding model and the final timeout. This indicated that the model loading process itself was taking too long, blocking the main thread and causing the web server to become unresponsive to the Lambda Web Adapter.
- **Initial Diagnosis Flaw**: The first proposed solution was to move the slow operation into the Lambda `Init` phase. However, this was correctly identified as flawed because the `Init` phase has its own stricter timeout of 10 seconds, which a 28-second process would also fail.
- **New Hypothesis**: The extreme slowness is likely caused by the `from_pretrained` function entering a slow "discovery" mode because it's not being given the explicit filename of the model (`model_quantized.onnx`) and has to scan for it. Fixing the `Could not find any ONNX files with standard file name model.onnx` warning, even though it's logged as a warning, may unlock a "fast path" for loading and drastically reduce the time.
- **Verification Step**: To test this hypothesis without another lengthy deployment cycle, a local test script was created: `scripts/test_model_load_time.py`. This script's purpose is to isolate the model loading function and measure the time difference between calling it with and without the explicit `file_name` parameter. This provides a data-driven way to confirm the cause of the slowness before applying a fix to the main application.

#### Final Resolution: The API Gateway Timeout

- **Symptom**: After deploying a version with a 120-second Lambda timeout, the application logs in CloudWatch showed a successful ~90-second execution. However, the web UI did not update with the results.
- **Root Cause**: This discrepancy revealed the true bottleneck: the **AWS API Gateway** has a hard, non-configurable integration timeout of **29 seconds**. While the Lambda function was correctly running to completion in the background, API Gateway was terminating the client connection after 29 seconds and sending an error response to the browser.

**Understanding the Two Timeouts:**

1. **Lambda Timeout (120 seconds)** - Configurable in `variables.tf`
   - Controls how long Lambda will execute before being killed
   - Set to 120s to accommodate ~90s model loading on cold start
   - This timeout was sufficient - Lambda always completed successfully

2. **API Gateway Timeout (29 seconds)** - AWS hard limit, cannot be changed
   - Controls how long API Gateway waits for Lambda response before dropping connection
   - Hardcoded AWS limitation for both HTTP API and REST API Gateway
   - This was the bottleneck - too short for cold start

**The Problem Flow:**
```
User → API Gateway → Lambda
        │             └─> [Loading model... 10s... 20s... 29s... 90s... SUCCESS ✅]
        └─> [29s TIMEOUT! Closes connection, returns 504 to user ❌]

Result: CloudWatch logs show "200 OK" but browser shows timeout error
```

**Why "sometimes it worked":**
- **Worked**: Lambda was warm (previous request < 15min ago), responds in 1-2s < 29s limit
- **Failed**: Lambda cold start (no requests for 15min), takes 90s > 29s limit, connection dropped

Lambda always completed and generated correct answers (visible in logs), but API Gateway already told the browser "give up" before Lambda could send the response back.

- **The Architectural Wall**: This 29-second limit is a hard wall for the current architecture. A synchronous process that takes ~90 seconds cannot be served through a standard API Gateway integration.
- **Solution**: Switch from API Gateway to **Lambda Function URL**, which respects the Lambda function's timeout (up to 15 minutes), allowing the full 120s for cold starts.

##### Throttling and Cost Control

A `reserved_concurrent_executions` limit of 5 was added to the Lambda function's configuration. This acts as a crucial safety throttle, ensuring the function cannot scale uncontrollably and protecting against runaway costs. It guarantees that a maximum of 5 instances can run simultaneously.
