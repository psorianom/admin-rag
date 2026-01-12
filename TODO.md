# Project Roadmap

Estimated total: **10-13 days of focused work**

## Phase 1: Data Pipeline (2-3 days)

### Goal
Clean, structured data ready for ingestion from both Code du travail and KALI corpus.

### Tasks
- [x] Explore Code du travail XML structure
- [x] Parse section metadata for article enrichment
- [x] Write parser to filter obsolete articles
- [x] Fix duplicate articles (filter historical versions)
- [x] Analyze article lengths
- [x] **Implement chunking strategy**
  - Articles < 500 tokens → keep whole
  - Articles > 500 tokens → split by paragraphs & numbered lists
  - Preserve parent context in metadata
  - Only 0.9% (101 articles) need chunking
- [x] **Download KALI corpus**
  - Data in `data/raw/kali/kali/global/`
  - 289,936 articles, 86,996 conventions
- [x] **Explore KALI structure**
  - Identical to Code du travail (article/, section_ta/, texte/)
  - Filter by IDCC numbers in CONTENEUR tags
- [x] **Parse KALI XML**
  - Created kali_parser.py for top 10 conventions
  - Target 10 major sectors (Métallurgie, Syntec, HCR, etc.)
  - Extracted 13,033 articles from 7/10 conventions
  - Same filtering logic as Code du travail (obsolete, historical)
- [x] **Chunk KALI articles**
  - Reuse article_chunker.py (same logic)
  - Run parse_kali.py script
  - Result: 14,154 chunks from 7 conventions

### Deliverable
- `data/processed/code_travail_chunks.jsonl` - 11,644 Code du travail chunks ✅
- `data/processed/kali_chunks.jsonl` - 14,154 KALI chunks ✅
- **Decision**: Keep datasets SEPARATE for explicit agent routing (not merged)

---

## Phase 2: Retrieval Foundation (2-3 days)

### Goal
Basic RAG system that can retrieve relevant articles from both sources.

### Tasks
- [x] **Choose vector store**
  - **Decision**: Qdrant
  - Fast (Rust-based), free (open source)
  - Excellent metadata filtering for multi-source RAG
  - Running at http://localhost:6333
- [x] **Select embedding model**
  - **Decision**: BGE-M3 (BAAI/bge-m3, 1024 dims)
  - Validated by AgentPublic/legi dataset on French legal text
  - Multilingual with excellent French performance
  - Sentence-transformers compatible
- [x] **Install dependencies**
  - qdrant-haystack (4.2.0)
  - sentence-transformers (3.4.1)
  - PyTorch (2.9.1) + transformers (4.57.3)
- [x] **Build Haystack ingestion pipeline**
  - Created `src/retrieval/ingest_code_travail.py`
  - Load JSONL → Haystack Documents
  - BGE-M3 embedding generation (auto-detects GPU/CPU)
  - Qdrant indexing with rich metadata
- [x] **Build KALI ingestion pipeline**
  - Created `src/retrieval/ingest_kali.py`
  - Preserves KALI-specific metadata (IDCC, convention names)
  - Embeds convention info for better retrieval
  - Collection: `kali`
- [x] **Create Makefile automation**
  - `make setup`, `make parse`, `make ingest`, `make ingest-only`
  - Built-in error checking and status validation
  - `make ingest-only`: JSONL-only ingestion (no raw data needed)
- [x] **Build vast.ai automation for GPU embedding**
  - Created `scripts/run_vast_ingestion.py` - Full automation
  - Created `scripts/embed_chunks.py` - Standalone embedding generator
  - Simplified workflow: Upload JSONL + script, embed, download
  - No Docker complexity, no GitHub required
  - Cost: ~$0.10-0.30 for 25,798 chunks
  - Key learnings: Use dlperf/score, test SSH connectivity, SCP syntax
- [x] **Update ingestion scripts for pre-computed embeddings**
  - Both scripts detect embeddings in JSONL automatically
  - Skip embedding step if present, load directly
  - Fast local indexing (2 minutes vs 20+ minutes)
- [x] **Run embeddings ingestion**
  - Embeddings generated on vast.ai (24GB VRAM GPU, ~15-20 min)
  - Code du travail: 11,644 chunks → `code_travail` collection ✅
  - KALI: 14,154 chunks → `kali` collection ✅
  - Total: 25,798 chunks with BGE-M3 embeddings (1024 dims)
  - Qdrant running at http://localhost:6333
- [x] **Data quality analysis**
  - Code du travail: 60% <500 chars, mean 587 chars
  - KALI: 46% <500 chars, mean 1130 chars
  - 175 empty chunks (1.2%), 285 oversized chunks (1.1%)
  - Decision: Proceed, refactor if retrieval quality suffers
- [ ] **Build basic retrieval pipeline**
  - Query → Embedding → Retrieval
  - Top-k selection
  - Metadata-based filtering
- [ ] **Test retrieval quality**
  - Manual testing with sample questions
  - Check if correct articles are retrieved
  - Tune top-k and similarity thresholds
  - Evaluate chunking strategy performance

### Deliverable
✅ **PHASE 2 COMPLETE**: 25,798 chunks indexed in Qdrant with BGE-M3 embeddings
- Working vast.ai automation for GPU embedding
- Pre-computed embedding support in pipelines
- Makefile automation for reproducibility
- Ready for retrieval pipeline development

---

## Phase 3: Retrieval Pipeline ✅

### Goal
Basic RAG system that can retrieve relevant articles from both sources.

### Completed Tasks
- [x] **Build basic retrieval pipeline**
  - BM25 keyword search (no embeddings needed locally)
  - Loads JSONL into InMemoryDocumentStore
  - Works on both code_travail and kali collections

- [x] **Create FastHTML web UI**
  - Search box with query input
  - Collection selector (code_travail / kali)
  - Convention filter (dynamically shown for KALI)
  - Result cards with scores and metadata
  - HTMX for dynamic updates, no page reloads

- [x] **Implement metadata filtering**
  - Filter by IDCC for convention-specific searches
  - Filter by article_num, source, hierarchy
  - Works seamlessly with BM25

- [x] **Test retrieval quality**
  - Manual testing with sample labor law questions
  - Confirmed correct articles retrieved
  - BM25 works well for keyword matching
  - Limitation: Pure keyword matching, no semantic understanding

### Deliverable
✅ **PHASE 3 COMPLETE**: Functional retrieval system with web UI
- BM25 retrieval pipeline
- FastHTML web interface
- Metadata filtering by convention
- Tested and working locally

---

## Phase 3b: Infrastructure & Deployment ✅

### Goal
Deploy production-ready system on AWS serverless stack (€0/month).

### Tasks
- [x] **Test ONNX BGE-M3 int8 model latency**
  - Tested `gpahal/bge-m3-onnx-int8` model locally
  - Cold start: 4.99s (acceptable)
  - Warm query: 0.06s (60ms - excellent!)
  - Confirmed 1024-dim dense embeddings
  - Installed `optimum[onnxruntime]` + `transformers`
  - Decision: Lambda is viable for production

- [x] **Architecture decision: Lambda vs EC2**
  - Lambda wins: 60ms query latency vs 5-8s on EC2
  - Cost: €0 (free tier) vs €10/month
  - Auto-scaling for concurrent users
  - Qdrant Cloud free tier fits data (523MB < 1GB)

- [x] **Design Terraform infrastructure (Lambda)**
  - Lambda function (3GB RAM - account limit, Docker image)
  - IAM roles and permissions (`iam.tf`)
  - API Gateway for public access (`api_gateway.tf`)
  - CloudWatch for logging (automatic with IAM role)
  - All files: provider.tf, variables.tf, lambda.tf, outputs.tf
  - Terraform README.md with 8-step deployment guide

- [x] **Create Lambda Docker image**
  - Dockerfile with FastHTML + ONNX BGE-M3
  - Install `optimum[onnxruntime]` + `transformers`
  - All dependencies: mangum, haystack-ai, qdrant-haystack
  - Ready to build: `docker build -t admin-rag-retrieval .`

- [x] **Integrate BGE-M3 embeddings into retrieval**
  - Updated retrieve.py to use semantic search
  - Uses `QdrantEmbeddingRetriever` with BGE-M3 embeddings
  - Encodes queries: `embedder.encode(query)`
  - Connects to Qdrant Cloud API (via config)
  - Same public API: `retrieve(query, collection, top_k)`

- [x] **Create Qdrant config system**
  - `config/qdrant_config.json` with cloud/local switching
  - Updated ingestion scripts: `ingest_code_travail.py`, `ingest_kali.py`
  - Updated retrieval: `retrieve.py` uses config
  - No code changes needed to switch environments

- [x] **Set up Qdrant Cloud**
  - Free tier account created
  - Cluster URL: https://0444a90a-65a9-4e85-979a-adf963861027.eu-west-2-0.aws.cloud.qdrant.io:6333
  - API key: (in config/qdrant_config.json)
  - Ready to ingest: 1GB limit, 523MB for our 25,798 vectors

### Next Tasks (In Order)
- [ ] **Run ingestion scripts to populate Qdrant Cloud**
  ```bash
  poetry run python src/retrieval/ingest_code_travail.py
  poetry run python src/retrieval/ingest_kali.py
  ```
  - Loads JSONL files with pre-computed embeddings
  - Creates collections in Qdrant Cloud
  - Takes ~5-10 minutes total

- [ ] **Build Docker image locally**
  ```bash
  docker build -t admin-rag-retrieval .
  ```

- [ ] **Deploy to AWS Lambda**
  - Run Terraform: `cd terraform && terraform init && terraform plan && terraform apply`
  - Authenticates Docker to ECR
  - Pushes image to ECR
  - Lambda pulls and starts serving

- [ ] **Test and verify**
  - Web UI accessible via API Gateway URL (from Terraform output)
  - Vector search works with cloud Qdrant
  - Latency acceptable (60ms warm queries)
  - Monitor AWS costs (should be €0)

### Deliverable ✅
Production serverless system on AWS Lambda + Qdrant Cloud, ready for ingestion and deployment.

---

## Phase 4: Agentic Layer (Pending)

### Goal
Multi-step reasoning system that orchestrates retrieval and combines rules.

### Tasks
- [ ] **Design agent workflow**
  - Query analysis → entity extraction
  - Convention identification
  - Multi-source retrieval
  - Rule comparison and synthesis
- [ ] **Implement agent tools**
  - Convention identifier tool (extract job role, industry)
  - Code du travail retriever tool
  - KALI retriever tool (convention-specific)
  - Rule comparison logic (hierarchy, favor rules)
- [ ] **Setup Haystack agent**
  - Configure agent orchestration
  - Tool registration and routing
  - Multi-step reasoning flow
- [ ] **Choose & integrate LLM(s)**
  - Test Claude API (better reasoning, €10-15/month)
  - Test Mistral Large (cheaper, French-native, ~€3/month)
  - Evaluate tradeoffs
- [ ] **Prompt engineering**
  - System prompts for legal reasoning
  - Few-shot examples for French labor law
  - Citation formatting instructions

### Budget allocation:
- Infrastructure: €0/month (Lambda + Qdrant Cloud free tier)
- LLM API: €20-25/month (full budget available)

### Deliverable
Agent that can answer complex questions requiring multi-step reasoning across sources.

---

## Phase 5: Iteration & Quality (Pending)

### Goal
Production-ready system with validated answer quality.

### Tasks
- [ ] **Build evaluation dataset**
  - Collect 20-30 representative questions
  - Create ground truth answers
  - Cover different question types:
    - Simple lookups
    - Convention-specific queries
    - Multi-source reasoning
    - Temporal/seniority-based rules
- [ ] **Tune retrieval parameters**
  - Optimize top-k for each source
  - Test reranking strategies
  - Refine metadata filters
- [ ] **Improve prompts**
  - Iterate based on wrong/incomplete answers
  - Add legal reasoning guidance
  - Handle edge cases (conflicting rules, gaps)
- [ ] **Add citation system**
  - Return article references
  - Include article numbers and sources
  - Link to original legal text
- [ ] **Handle edge cases**
  - Missing conventions
  - Conflicting rules between sources
  - Temporal validity issues
  - Out-of-scope questions

### Deliverable
Reliable system with good answer quality and proper citations.

---

## Phase 6: Polish & Extensions (Optional)

**Time**: Open-ended, depends on requirements

### Possible Enhancements
- [ ] **Parse article citation links**
  - Extract `<LIENS>` tags from XML (CITATION, MODIFIE, ABROGE types)
  - Add cross-references to article metadata
  - Enable following article references in RAG
  - Potential knowledge graph construction
- [ ] Support for multiple conventions beyond Syntec
- [ ] Temporal queries ("what was the rule in 2020?")
- [ ] Knowledge graph for article cross-references
- [ ] UI/web interface
- [ ] API wrapper (FastAPI)
- [ ] Feedback collection mechanism
- [ ] Continuous data updates from Legifrance
- [ ] Answer explanation/reasoning traces
- [ ] Multi-language support (if needed)

---

## Key Decisions Log

### Why Haystack?
- Familiarity (contributor experience)
- Agent support in 2.x
- Pipeline flexibility
- Vector store agnostic

### Why Poetry?
- Modern dependency management
- Better than pip + requirements.txt
- Lockfile for reproducibility

### Why include section metadata?
- Provides richer context than generic hierarchy
- Improves retrieval quality
- Small effort (~30 min) for significant gain

### Chunking strategy: semantic boundaries
- Preserve legal structure (alinéas)
- Avoid splitting mid-thought
- Matches how legal professionals cite law

### Why top 10 conventions instead of just Syntec?
- More useful system covering major French sectors
- Still manageable dataset (~13K articles vs 289K total)
- Includes: Métallurgie, Syntec, HCR, Bâtiment, Automobile, Banking, Retail, etc.

### Why not use AgentPublic/legi pre-processed dataset?
- They have 33K Code du travail chunks (vs our 11K) due to fixed-window chunking + overlap
- Pre-computed BGE-M3 embeddings (time saver)
- BUT: We want flexibility to experiment with chunking strategies
- Our semantic chunking preserves legal structure better
- Our metadata is richer (hierarchy + section titles)
- Decision: Use our data, adopt BGE-M3 model for compatibility
