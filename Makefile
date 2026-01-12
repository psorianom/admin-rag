.PHONY: help setup install-deps start-qdrant stop-qdrant parse-code-travail parse-kali parse ingest-code-travail ingest-kali ingest ingest-only all clean clean-qdrant clean-processed status terraform-init terraform-validate terraform-plan terraform-apply terraform-destroy

# Default target
help:
	@echo "Admin RAG - French Labor Law RAG System"
	@echo ""
	@echo "Available targets:"
	@echo "  make setup              - Install dependencies + start Qdrant"
	@echo "  make parse              - Parse Code du travail + KALI (Phase 1)"
	@echo "  make ingest             - Embed and index into Qdrant (Phase 2)"
	@echo "  make ingest-only        - Ingest from existing JSONL files (skip parsing)"
	@echo "  make all                - Run full pipeline (parse + ingest)"
	@echo ""
	@echo "Individual targets:"
	@echo "  make install-deps       - Install Python dependencies with Poetry"
	@echo "  make start-qdrant       - Start Qdrant Docker container"
	@echo "  make stop-qdrant        - Stop Qdrant Docker container"
	@echo "  make parse-code-travail - Parse Code du travail XML only"
	@echo "  make parse-kali         - Parse KALI conventions XML only"
	@echo "  make ingest-code-travail - Ingest Code du travail only"
	@echo "  make ingest-kali        - Ingest KALI conventions only"
	@echo ""
	@echo "Utility targets:"
	@echo "  make status             - Show pipeline status"
	@echo "  make clean-processed    - Remove processed JSONL files"
	@echo "  make clean-qdrant       - Remove Qdrant storage (destructive!)"
	@echo "  make clean              - Clean all generated files"
	@echo ""
	@echo "Infrastructure (Terraform/AWS) targets:"
	@echo "  make terraform-init     - Initialize Terraform workspace"
	@echo "  make terraform-validate - Validate Terraform configuration"
	@echo "  make terraform-plan     - Preview AWS resources to be created"
	@echo "  make terraform-apply    - Deploy infrastructure to AWS"
	@echo "  make terraform-destroy  - Delete all AWS resources (destructive!)"

# Setup
setup: install-deps start-qdrant
	@echo "✅ Setup complete!"
	@echo "   - Dependencies installed"
	@echo "   - Qdrant running at http://localhost:6333"

install-deps:
	@echo "📦 Installing dependencies with Poetry..."
	poetry install

start-qdrant:
	@echo "🚀 Starting Qdrant..."
	@docker ps | grep -q qdrant && echo "   Qdrant already running" || \
		docker start qdrant 2>/dev/null || \
		docker run -d -p 6333:6333 -p 6334:6334 \
			-v $$(pwd)/qdrant_storage:/qdrant/storage:z \
			--name qdrant qdrant/qdrant
	@sleep 2
	@curl -s http://localhost:6333/ > /dev/null && \
		echo "   ✅ Qdrant is running at http://localhost:6333" || \
		echo "   ❌ Qdrant failed to start"

stop-qdrant:
	@echo "🛑 Stopping Qdrant..."
	@docker stop qdrant 2>/dev/null || echo "   Qdrant not running"

# Phase 1: Data Parsing
parse: parse-code-travail parse-kali
	@echo "✅ Phase 1 complete: All data parsed"

parse-code-travail:
	@echo "📖 Parsing Code du travail..."
	@if [ ! -d "data/raw/code_travail_LEGITEXT000006072050" ]; then \
		echo "❌ Error: Code du travail data not found in data/raw/"; \
		echo "   Please download LEGI dataset first"; \
		exit 1; \
	fi
	poetry run python src/ingestion/parse_code_travail.py
	@echo "   ✅ Code du travail parsed → data/processed/code_travail_chunks.jsonl"

parse-kali:
	@echo "📖 Parsing KALI conventions..."
	@if [ ! -d "data/raw/kali/kali/global" ]; then \
		echo "❌ Error: KALI data not found in data/raw/kali/"; \
		echo "   Please download KALI dataset first"; \
		exit 1; \
	fi
	poetry run python src/ingestion/parse_kali.py
	@echo "   ✅ KALI conventions parsed → data/processed/kali_chunks.jsonl"

# Phase 2: Embedding & Indexing
ingest: ingest-code-travail ingest-kali
	@echo "✅ Phase 2 complete: All data ingested into Qdrant"

ingest-code-travail:
	@echo "🔮 Ingesting Code du travail (BGE-M3 embeddings)..."
	@if [ ! -f "data/processed/code_travail_chunks.jsonl" ]; then \
		echo "❌ Error: code_travail_chunks.jsonl not found"; \
		echo "   Run 'make parse-code-travail' first"; \
		exit 1; \
	fi
	poetry run python src/retrieval/ingest_code_travail.py
	@echo "   ✅ Code du travail ingested → Qdrant collection 'code_travail'"

ingest-kali:
	@echo "🔮 Ingesting KALI conventions (BGE-M3 embeddings)..."
	@if [ ! -f "data/processed/kali_chunks.jsonl" ]; then \
		echo "❌ Error: kali_chunks.jsonl not found"; \
		echo "   Run 'make parse-kali' first"; \
		exit 1; \
	fi
	@if [ ! -f "src/retrieval/ingest_kali.py" ]; then \
		echo "❌ Error: ingest_kali.py not yet implemented"; \
		exit 1; \
	fi
	poetry run python src/retrieval/ingest_kali.py
	@echo "   ✅ KALI conventions ingested → Qdrant collection 'kali'"

# Ingest from existing JSONL files (skip parsing)
ingest-only: start-qdrant
	@echo "📦 Ingesting from existing JSONL files..."
	@echo ""
	@if [ ! -f "data/processed/code_travail_chunks.jsonl" ] || [ ! -f "data/processed/kali_chunks.jsonl" ]; then \
		echo "❌ Error: JSONL files not found"; \
		echo "   Expected:"; \
		echo "     - data/processed/code_travail_chunks.jsonl"; \
		echo "     - data/processed/kali_chunks.jsonl"; \
		echo ""; \
		echo "   If you have these files, place them in data/processed/"; \
		echo "   Otherwise, run 'make parse' first"; \
		exit 1; \
	fi
	@echo "✅ Found both JSONL files"
	@echo "   - code_travail_chunks.jsonl ($$(wc -l < data/processed/code_travail_chunks.jsonl) chunks)"
	@echo "   - kali_chunks.jsonl ($$(wc -l < data/processed/kali_chunks.jsonl) chunks)"
	@echo ""
	@make ingest
	@echo ""
	@echo "🎉 Ingestion complete!"

# Full pipeline
all: setup parse ingest
	@echo ""
	@echo "🎉 Full pipeline complete!"
	@echo ""
	@echo "Collections in Qdrant:"
	@echo "  - code_travail: 11,644 chunks"
	@echo "  - kali: 14,154 chunks"
	@echo ""
	@echo "Access Qdrant dashboard: http://localhost:6333/dashboard"

# Status
status:
	@echo "Pipeline Status"
	@echo "==============="
	@echo ""
	@echo "📦 Dependencies:"
	@poetry --version > /dev/null 2>&1 && echo "   ✅ Poetry installed" || echo "   ❌ Poetry not found"
	@echo ""
	@echo "🗄️  Qdrant:"
	@docker ps | grep -q qdrant && echo "   ✅ Running at http://localhost:6333" || echo "   ❌ Not running"
	@echo ""
	@echo "📁 Processed Data:"
	@[ -f "data/processed/code_travail_chunks.jsonl" ] && \
		echo "   ✅ code_travail_chunks.jsonl ($$(wc -l < data/processed/code_travail_chunks.jsonl) chunks)" || \
		echo "   ❌ code_travail_chunks.jsonl not found"
	@[ -f "data/processed/kali_chunks.jsonl" ] && \
		echo "   ✅ kali_chunks.jsonl ($$(wc -l < data/processed/kali_chunks.jsonl) chunks)" || \
		echo "   ❌ kali_chunks.jsonl not found"
	@echo ""
	@echo "🗂️  Qdrant Collections:"
	@curl -s http://localhost:6333/collections 2>/dev/null | grep -q "code_travail" && \
		echo "   ✅ code_travail collection exists" || \
		echo "   ❌ code_travail collection not found"
	@curl -s http://localhost:6333/collections 2>/dev/null | grep -q "kali" && \
		echo "   ✅ kali collection exists" || \
		echo "   ❌ kali collection not found"

# Cleanup
clean-processed:
	@echo "🧹 Removing processed data files..."
	rm -f data/processed/code_travail_articles.jsonl
	rm -f data/processed/code_travail_chunks.jsonl
	rm -f data/processed/kali_articles.jsonl
	rm -f data/processed/kali_chunks.jsonl
	rm -f data/processed/article_to_section_mapping.json
	@echo "   ✅ Processed files removed"

clean-qdrant:
	@echo "⚠️  WARNING: This will delete all Qdrant data!"
	@echo -n "   Continue? [y/N] " && read ans && [ $${ans:-N} = y ]
	@make stop-qdrant
	rm -rf qdrant_storage/
	@echo "   ✅ Qdrant storage removed"

clean: clean-processed
	@echo "🧹 Cleaning Python cache..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "   ✅ Clean complete"

# Terraform / AWS Infrastructure
terraform-init:
	@echo "🚀 Initializing Terraform workspace..."
	cd terraform && terraform init
	@echo "   ✅ Terraform initialized"

terraform-validate:
	@echo "✔️  Validating Terraform configuration..."
	cd terraform && terraform validate
	@echo "   ✅ Configuration is valid"

terraform-plan:
	@echo "📋 Planning AWS resources..."
	cd terraform && terraform plan
	@echo "   ✅ Plan complete - review above"

terraform-apply:
	@echo "🚀 Deploying infrastructure to AWS..."
	@echo "   ⚠️  This will create AWS resources and incur costs"
	cd terraform && terraform apply
	@echo "   ✅ Infrastructure deployed!"
	@echo "   📌 Save the outputs above (API endpoint, ECR URL)"

terraform-destroy:
	@echo "⚠️  WARNING: This will delete ALL AWS resources!"
	@echo "   ⚠️  Confirm you want to proceed..."
	cd terraform && terraform destroy
	@echo "   ✅ Resources destroyed"
