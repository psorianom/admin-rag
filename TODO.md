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
- [ ] **Chunk KALI articles**
  - Reuse article_chunker.py (same logic)
  - Run parse_kali.py script
- [ ] **Create unified document format**
  - Combine Code du travail chunks + KALI chunks
  - Standardized metadata schema
  - Single unified JSONL output

### Deliverable
- `data/processed/code_travail_chunks.jsonl` - 11,644 Code du travail chunks ✅
- `data/processed/kali_chunks.jsonl` - ~13,000 KALI chunks (pending)
- `data/processed/unified_corpus.jsonl` - Combined corpus (~25K chunks total)

---

## Phase 2: Retrieval Foundation (2-3 days)

### Goal
Basic RAG system that can retrieve relevant articles from both sources.

### Tasks
- [ ] **Choose vector store**
  - Evaluate: Qdrant, Weaviate, or simple FAISS
  - Consider: scale, metadata filtering, ease of use
- [ ] **Select embedding model**
  - Test French-specific models (Camembert-based)
  - Compare with multilingual models
  - Benchmark on sample legal queries
- [ ] **Build Haystack ingestion pipeline**
  - Document preprocessor
  - Embedding generation
  - Vector store indexing
- [ ] **Implement metadata filtering**
  - Filter by source (code_travail vs convention)
  - Filter by convention type (Syntec, etc.)
  - Filter by article type (legislative vs regulatory)
- [ ] **Build basic retrieval pipeline**
  - Query → Embedding → Retrieval
  - Top-k selection
  - Metadata-based filtering
- [ ] **Test retrieval quality**
  - Manual testing with sample questions
  - Check if correct articles are retrieved
  - Tune top-k and similarity thresholds

### Deliverable
Working retrieval pipeline that can find relevant legal articles for queries.

---

## Phase 3: Agentic Layer (3-4 days)

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
  - Test Mistral Large/Medium (French-native, cheaper)
  - Test Claude Sonnet (better reasoning, more expensive)
  - Test open-weight alternatives
  - Potentially hybrid approach
- [ ] **Prompt engineering**
  - System prompts for legal reasoning
  - Few-shot examples for French labor law
  - Citation formatting instructions

### Deliverable
Agent that can answer complex questions requiring multi-step reasoning across sources.

---

## Phase 4: Iteration & Quality (2-3 days)

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

## Phase 5: Polish & Extensions (Optional)

**Time**: Open-ended, depends on requirements

### Possible Enhancements
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
