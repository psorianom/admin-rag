# Instructions for Claude Code

This file contains specific instructions for Claude when working on this project.

## Project Overview

This is an **agentic RAG system for French labor law** combining:
- **Code du travail** (French labor code) - 11,644 chunks
- **KALI corpus** (collective bargaining agreements) - 14,154 chunks
- **BGE-M3** multilingual embeddings (1024 dims)
- **Qdrant** vector database
- **Haystack 2.x** RAG framework

**Key principle**: Preserve legal document structure through semantic chunking (article-level), not fixed-window chunking.

## Architecture Decisions

### Why Semantic Chunking?
- Legal documents have meaningful structure (articles, sections)
- Preserves complete legal concepts vs arbitrary text windows
- Enables experimentation with different chunking strategies
- More flexible than AgentPublic/legi's fixed 5000-char windows

### Why Simplified Vast.ai Workflow?
- **Problem**: Docker-in-Docker complexity, private repo access
- **Solution**: Upload script + JSONL directly, generate embeddings, download compressed
- **Benefits**: No GitHub needed, faster setup, lower transfer costs (gzip)

### Why Local Qdrant Indexing?
- Embedding generation needs GPU (vast.ai)
- Indexing is CPU-bound and fast (local)
- Separation of concerns: compute-heavy vs I/O-heavy tasks

## Git Commits

**When to commit:**
- After completing a significant feature or phase
- After major refactoring or infrastructure changes
- When multiple files are modified and logically related
- Don't commit incomplete work or work-in-progress changes

**How to commit:**
- Write clear, concise commit messages (1-2 sentences)
- Summarize what was done and why (focus on intent, not mechanics)
- Use `git status` and `git diff` to review changes before committing
- Stage related changes together, unrelated changes separately

**NEVER add the following to commit messages:**
- "Generated with Claude Code" footer
- "Co-Authored-By: Claude Sonnet" attribution
- Any Claude/Anthropic attribution or links

**Also after committing:**
- Push to remote: `git push`
- Keep FLOW.md and TODO.md in sync with actual progress
- Let user know in summary what was committed

Keep commit messages clean and professional.

## Code Style

- Follow existing code patterns in the project
- Use proper Python typing hints
- Document functions with clear docstrings
- Keep functions focused and modular
- Use Haystack 2.x patterns (Pipeline, Document, ComponentDevice)

## Documentation

- Update FLOW.md when completing significant milestones
- Update TODO.md to track progress
- Keep both files current and accurate
- scripts/README.md documents utility scripts

## Context Management

- Use bash reconnaissance (ls, wc, grep) before reading large files
- Read sample files first to understand structure
- Avoid loading huge datasets into context
- Let the user run heavy processing tasks locally
- For vast.ai issues, check logs/vast_ingestion_*.log

## Communication

- Be direct and concise
- Don't use emojis unless explicitly requested
- Ask clarifying questions when requirements are unclear
- Provide practical examples when explaining concepts

## Common Pitfalls & Fixes

### SSH vs SCP Port Syntax
- **SSH uses `-p` (lowercase)**: `ssh -p 14246 root@ssh8.vast.ai`
- **SCP uses `-P` (uppercase)**: `scp -P 14246 file.txt root@ssh8.vast.ai:/path/`
- **Error if wrong**: `scp: stat local "14246": No such file or directory`

### PyTorch Compatibility
- Vast.ai images may have old PyTorch incompatible with latest transformers
- **Always upgrade first**: `pip install --upgrade torch torchvision torchaudio`
- **Then install**: `pip install sentence-transformers tqdm`

### Vast.ai Instance Selection
- **Don't trust `inet_down`/`inet_up`** (self-reported, often fake)
- **Use `dlperf`** (tested download performance by vast.ai)
- **Sort by `score`** (ML workload performance) not just price
- **Minimum 24GB VRAM** for BGE-M3 with batch_size=32

### SSH Connectivity
- Instance status "running" ≠ SSH ready
- **Always test**: `ssh -p PORT root@HOST 'echo SSH_OK'`
- Wait and retry every 5s until SSH actually responds

### Haystack 2.x API Changes
- Use `haystack.components.writers.DocumentWriter` (not qdrant-specific writer)
- Use `ComponentDevice.from_str("cuda:0")` not string `"cuda"`
- Check qdrant-haystack compatibility (use >=9.5.0 with haystack-ai 2.x)

## Vast.ai Workflow

### File Locations on Instance
```
/workspace/
├── data/
│   └── processed/
│       ├── code_travail_chunks.jsonl
│       └── kali_chunks.jsonl
└── scripts/
    └── embed_chunks.py
```

### Manual Testing
```bash
ssh -p PORT root@HOST
cd /workspace
ls -lh data/processed/  # Check uploads
python scripts/embed_chunks.py  # Run manually
ls -lh data/processed/*.gz  # Verify output
```

### Keep Alive Mode
- `keep_alive=True` in script prevents auto-destroy
- Useful for debugging and testing
- **REMEMBER**: Destroy manually when done: `vastai destroy instance ID`

## Data Pipeline

### Phase 1: Parsing
- Extract articles from Légifrance XML dumps
- Parse KALI collective agreements
- Semantic chunking at article level
- Preserve hierarchy metadata (partie, livre, titre, chapitre)

### Phase 2: Embedding
- Generate BGE-M3 embeddings (BAAI/bge-m3)
- On vast.ai GPU for speed (25,798 chunks × 1024 dims)
- Save back to JSONL with 'embedding' field
- Compress with gzip before transfer

### Phase 3: Indexing
- Load JSONL with pre-computed embeddings
- Detect embeddings automatically (`has_embeddings` flag)
- Skip embedding step if present
- Write directly to Qdrant vector store

## Testing & Development

### Local Development
```bash
make setup          # Install deps + start Qdrant
make parse          # Phase 1 (if raw data available)
make ingest-only    # Phase 2 (with pre-computed embeddings)
make status         # Check pipeline status
```

### Vast.ai Testing
```bash
poetry run python scripts/run_vast_ingestion.py
# Monitors logs/vast_ingestion_TIMESTAMP.log
# Uploads JSONL + script, generates embeddings, downloads .gz files
# Set keep_alive=True for manual testing
```

### Verification
```bash
# Check embeddings in JSONL
head -1 data/processed/code_travail_chunks.jsonl | jq '.embedding | length'
# Should show: 1024

# Check Qdrant
curl http://localhost:6333/collections/code_travail
# View dashboard: http://localhost:6333/dashboard
```

## Dependencies

### Critical Versions
- `haystack-ai ^2.0.0` (framework)
- `qdrant-haystack ^9.5.0` (vector store, compatible with haystack 2.x)
- `sentence-transformers ^3.0.0` (embeddings)
- `tqdm ^4.66.0` (progress bars for embedding script)

### Version Compatibility
- qdrant-haystack 4.x is NOT compatible with haystack-ai 2.x
- PyTorch in vast.ai images may need upgrading
- sentence-transformers requires recent transformers/torch

## Future Enhancements

### Docker Image for Faster Vast.ai
```dockerfile
FROM pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime
RUN pip install sentence-transformers tqdm
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
```
- Pre-downloads 2.7GB BGE-M3 model
- Saves 7+ minutes per vast.ai run
- No pip installs needed

### Production Settings
- Set `keep_alive=False` in vast.ai script for auto-cleanup
- Lower `max_price` if budget-constrained
- Adjust `min_gpu_ram` based on batch size needs
