# Project Roadmap

## Current Status (January 2026)

**Completed**:
- ✅ Data pipeline (25,798 legal chunks from Code du travail + 7 KALI conventions)
- ✅ Qdrant Cloud deployment (523MB vectors indexed)
- ✅ Intelligent routing agent (GPT-4o-mini with convention detection)
- ✅ Answer generation with citations and confidence scoring
- ✅ Lambda Function URL infrastructure (fixed API Gateway timeout issue)

**Ready for Deployment**:
- Terraform configuration cleaned up (API Gateway removed, Lambda Function URL added)
- Run `./cleanup_api_gateway.sh` and `terraform apply` to deploy

**Next Phase**:
- Phase 6: Evaluation & quality tuning
- Collect evaluation dataset and benchmark answer quality

---

## Original Estimate

Estimated total: **10-13 days of focused work** (actual: ~15 days with deployment debugging)

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
- [x] **Build basic retrieval pipeline**
  - Query → Embedding → Retrieval
  - Top-k selection
  - Metadata-based filtering (IDCC, source, hierarchy)
  - Semantic search with BGE-M3 embeddings
- [x] **Test retrieval quality**
  - Manual testing with sample questions
  - Correct articles retrieved with good relevance scores
  - Top-k and similarity thresholds validated
  - Chunking strategy performs well

### Deliverable
✅ **PHASE 2 COMPLETE**: 25,798 chunks indexed in Qdrant Cloud with BGE-M3 embeddings
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
  - Configuration via .env file (credentials not in git)
  - Ready to ingest: 1GB limit, 523MB for our 25,798 vectors

- [x] **Refactor configuration to use environment variables**
  - Created .env.template for local development
  - Created src/config/constants.py to load from .env
  - Updated all scripts (ingest_code_travail.py, ingest_kali.py, retrieve.py)
  - Added config/qdrant_config.json to .gitignore
  - Security: Secrets now in .env (not committed to git)

- [x] **Ingest vectors to Qdrant Cloud**
  - Code du travail: 11,644 chunks uploaded
  - KALI: 14,154 chunks uploaded
  - Total: 25,798 vectors in cloud (523MB/1GB used)
  - Both collections live and ready for queries

- [x] **Documentation improvements**
  - Enhanced README with architecture diagrams and design decisions
  - Added mermaid diagrams to FLOW.md (pipeline, workflow, architecture)
  - Removed CLAUDE.md from repo (kept local only)
  - Added .env setup instructions to README

### Deployment Status (Complete) ✅
- [x] **Terraform infrastructure created**
  - Lambda function provisioned (3GB RAM)
  - ECR repository created
  - API Gateway endpoint: https://rs3vbew2bh.execute-api.eu-west-3.amazonaws.com/prod

- [x] **Docker image approach evolved**
  - Switched to AWS Lambda Web Adapter (simpler than manual Lambda handlers)
  - Uses regular Python image + Lambda Web Adapter extension
  - FastHTML runs normally, adapter handles Lambda integration

- [x] **Qdrant Cloud setup complete**
  - 25,798 vectors uploaded (523MB/1GB used)
  - Both collections (code_travail, kali) live and queryable

- [x] **Deployment issues resolved**
  - Fixed API Gateway stage routing by making the application stage-aware.
  - Solved model re-downloading and disk space errors by setting a consistent `HF_HOME` cache path in the `Dockerfile`.

### Deliverable ✅
**PHASE 3b COMPLETE**: Infrastructure ready for deployment with Lambda Function URL architecture.

---

## Phase 8: Lambda Function URL Migration ✅

### Goal
Replace API Gateway with Lambda Function URL to solve the 29-second timeout issue.

**Problem**: API Gateway has a hard 29-second timeout that cannot be changed. Lambda cold starts take ~90s to load the ONNX model, causing timeouts even though Lambda completes successfully.

**Solution**: Lambda Function URL respects Lambda's full 120-second timeout.

### Completed Tasks
- [x] **Update Terraform Configuration**
  - Removed `api_gateway.tf` (deleted file)
  - Added `aws_lambda_function_url` resource in `lambda.tf` with CORS support
  - Removed API_STAGE environment variable (no longer needed)
  - Created `cleanup_api_gateway.sh` script to remove stale state

- [x] **Update Documentation**
  - Updated `FLOW.md` with detailed timeout explanation
  - Updated `README.md` to reflect Lambda Function URL architecture
  - Updated `terraform/README.md` with simplified deployment flow

- [x] **Prepare for Deployment**
  - Code changes committed and pushed
  - Next steps documented in cleanup script

### Next Steps (To Deploy)
```bash
cd terraform
./cleanup_api_gateway.sh  # Remove old API Gateway from state
terraform plan             # Review changes
terraform apply            # Deploy Lambda Function URL
terraform output lambda_function_url  # Get new public URL
```

### Deliverable ✅
Clean Terraform configuration with Lambda Function URL. Ready to deploy.

---

## Phase 4: Agentic Layer ✅

### Goal
Multi-step reasoning system that orchestrates retrieval and combines rules.

### Completed Tasks
- [x] **Design agent workflow**
  - Query analysis with GPT-4o-mini
  - Convention identification from job roles/industries
  - Multi-collection retrieval (code_travail + KALI)
  - Four routing strategies: code_only, kali_only, both_code_first, both_kali_first

- [x] **Implement agent tools**
  - `routing_agent.py`: GPT-4o-mini powered routing with Pydantic validation
  - `multi_retriever.py`: Multi-collection retrieval with IDCC metadata filtering
  - Convention mapping for 7 major sectors (Syntec, Métallurgie, HCR, etc.)
  - Nested field indexes in Qdrant for efficient filtering

- [x] **LLM integration**
  - OpenAI GPT-4o-mini for routing decisions
  - Structured outputs with Pydantic models
  - Temperature=0 for deterministic routing
  - Cost: ~€0.000023 per query

- [x] **Test coverage**
  - 18 passing tests (8 routing + 10 retrieval)
  - End-to-end testing with French labor law queries
  - Convention auto-detection verified

### Budget:
- Infrastructure: €0/month (Lambda + Qdrant Cloud free tier)
- LLM API: ~€0.70/month (1000 queries/day)

### Deliverable ✅
Agent that intelligently routes queries to appropriate collections with automatic convention detection.

---

## Phase 5: Answer Generation & Citations ✅

### Goal
Natural language answer generation with citation tracking and confidence scoring.

### Completed Tasks
- [x] **Answer generation**
  - `answer_generator.py`: GPT-4o-mini synthesizes answers from top 3 results
  - Pydantic `AnswerWithCitations` model for structured outputs
  - Temperature=0.7 for natural yet consistent responses
  - Automatic citation index tracking

- [x] **Citation system**
  - `citation_formatter.py`: Formats citations for Code du travail and KALI
  - Blue left border highlighting for cited sources in UI
  - Article references with IDCC numbers for conventions

- [x] **Confidence scoring**
  - 0-1 confidence score for each answer
  - Color-coded badges (green/yellow/red) in UI
  - Based on result quality and coverage

- [x] **Web UI integration**
  - Answer section with reasoning display
  - Confidence badges with visual indicators
  - Cited sources highlighted with blue borders
  - Works locally and ready for Lambda

- [x] **Test coverage**
  - 15 comprehensive tests for answer generation
  - Total: 33 passing tests (15 answer + 10 retriever + 8 routing)
  - All 4 example queries tested end-to-end

### Cost:
- Per query: ~€0.000123 (routing + answer generation)
- Monthly estimate: ~€0.37/month (1000 queries/day)

### Deliverable ✅
Complete RAG system with intelligent routing, answer generation, and citation tracking.

---

## Phase 6: Evaluation & Quality (Next Priority)

### Goal
Validate answer quality and tune for production use after Lambda deployment.

### Tasks
- [ ] **Deploy to AWS Lambda**
  - Run `./cleanup_api_gateway.sh` in terraform directory
  - Apply Terraform changes with `terraform apply`
  - Verify Lambda Function URL works with cold starts
  - Test end-to-end with public URL

- [ ] **Build evaluation dataset**
  - Collect 20-30 representative French labor law questions
  - Create ground truth answers with legal expert input
  - Cover different question types:
    - General Code du travail questions
    - Convention-specific queries
    - Multi-source comparisons
    - Edge cases (contradictions, temporal queries)

- [ ] **Measure baseline performance**
  - Run evaluation dataset through system
  - Track metrics: answer accuracy, citation correctness, confidence calibration
  - Document failure cases and error patterns

- [ ] **Tune retrieval parameters**
  - Optimize top-k for each source (currently 10)
  - Test reranking strategies (cross-encoder models)
  - Refine metadata filters for better precision
  - Consider hybrid search (BM25 + semantic)

- [ ] **Improve prompts**
  - Iterate routing agent prompt based on misrouted queries
  - Enhance answer generation prompt for legal reasoning
  - Add handling for contradictions between sources
  - Improve confidence scoring calibration

### Deliverable
Validated system with benchmarked answer quality and documented performance metrics.

---

## Phase 7: Polish & Extensions (Optional)

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
