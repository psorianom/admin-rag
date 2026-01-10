# Scripts

Utility scripts for the admin-rag project.

## run_vast_ingestion.py

Automates BGE-M3 embedding ingestion on vast.ai GPU instances.

### What it does

1. **Provisions** a cheap GPU instance on vast.ai (<$0.25/hr)
2. **Uploads** your JSONL files (40MB)
3. **Clones** GitHub repo and runs `make ingest-only`
4. **Downloads** Qdrant storage (~150-200MB) back to your PC
5. **Destroys** instance automatically

**Total cost**: ~$0.10-0.20

### Prerequisites

```bash
# 1. Install vast.ai CLI
pip install vastai

# 2. Get API key from https://cloud.vast.ai/account/
vastai set api-key YOUR_API_KEY_HERE

# 3. Ensure GitHub repo is public (for cloning)
```

### Usage

```bash
# Run from project root
poetry run python scripts/run_vast_ingestion.py
```

**The script will:**
- Search for the cheapest GPU with ≥12GB VRAM
- Show you the top 3 options and select the cheapest
- Provision, run ingestion (~15-20 min), download results, destroy instance
- Leave you with `qdrant_storage/` containing all embeddings

**Then locally:**
```bash
make start-qdrant
# Qdrant loads from ./qdrant_storage automatically
# Access dashboard: http://localhost:6333/dashboard
```

### Configuration

Edit `main()` in the script to adjust:
```python
VastAIIngestion(
    max_price=0.25,      # Max $/hour (increase if no instances found)
    min_gpu_ram=12,      # Minimum GPU RAM in GB
    disk_size=30         # Instance disk size in GB
)
```

### Error handling

The script:
- ✅ Checks prerequisites before spending money
- ✅ Destroys instance on errors (no runaway costs)
- ✅ Handles Ctrl+C gracefully (cleanup on interrupt)
- ✅ Shows real-time progress

### Troubleshooting

**"No instances found"**
- Increase `max_price` parameter
- Try different times of day (prices fluctuate)

**"API key not set"**
```bash
vastai set api-key YOUR_KEY
```

**"Upload failed"**
- Check your JSONL files exist in `data/processed/`
- Check network connection

**Instance stuck in "loading"**
- Script waits up to 5 minutes
- If timeout, instance is destroyed automatically

### Alternative: Manual vast.ai workflow

If you prefer manual control:

```bash
# 1. Search instances
vastai search offers 'gpu_ram >= 12 reliability > 0.95' --order dph_total

# 2. Rent instance (replace ID)
vastai create instance INSTANCE_ID --image pytorch/pytorch:latest --disk 30

# 3. SSH details
vastai ssh-url INSTANCE_ID

# 4. Upload files
scp -P PORT data/processed/*.jsonl root@HOST:/workspace/

# 5. SSH and run
ssh -p PORT root@HOST
cd /workspace
git clone https://github.com/psorianom/admin-rag.git
cd admin-rag
mv /workspace/*.jsonl data/processed/
make setup
make ingest-only

# 6. Download results
scp -r -P PORT root@HOST:/workspace/admin-rag/qdrant_storage ./

# 7. Destroy instance
vastai destroy instance INSTANCE_ID
```

## explore_agentpublic_dataset.py

Explores the AgentPublic/legi HuggingFace dataset to understand their Code du travail coverage and chunking strategy.

### Usage

```bash
# Quick sample (10K records)
poetry run python scripts/explore_agentpublic_dataset.py 10000

# Full scan (1.26M records - takes a few minutes)
poetry run python scripts/explore_agentpublic_dataset.py
```

Shows:
- Code du travail chunk count
- Categories in dataset
- Sample records
- Comparison with our processing approach
