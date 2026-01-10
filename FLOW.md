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
- `code_travail`: 11,644 chunks
- `kali`: 14,154 chunks (pending)

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

## Next Steps

### Phase 2: Retrieval Foundation (In Progress)
- ✅ Vector store setup (Qdrant)
- ✅ Embedding model selection (BGE-M3)
- ✅ Ingestion pipeline implementation
- ⏳ Run Code du travail ingestion
- ⏳ Build KALI ingestion pipeline
- ⏳ Test basic retrieval with sample queries

### Phase 3: Agentic Layer (Pending)
- Multi-step reasoning workflow
- Convention identification tool
- Dual-source retrieval

### Phase 4: Evaluation & Quality (Pending)
- Test dataset creation
- Quality tuning
- Citation system
