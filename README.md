# Admin RAG - French Labor Law Assistant

Agentic RAG system for French labor law using Code du travail and KALI corpus.

## Structure

```
data/
├── raw/           # Original XML from Legifrance
├── processed/     # Cleaned, chunked documents
└── eval/          # Evaluation datasets

src/
├── ingestion/     # Data extraction & processing
├── retrieval/     # RAG components
├── agents/        # Agentic layer
└── evaluation/    # Quality assessment

notebooks/         # Exploration & testing
configs/           # Configuration files
tests/             # Unit tests
```

## Setup

```bash
poetry install
```

## Phases

1. Data Pipeline - Extract and chunk legal documents
2. Retrieval Foundation - Vector store and basic RAG
3. Agentic Layer - Multi-step reasoning
4. Iteration & Quality - Evaluation and tuning
