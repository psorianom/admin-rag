"""
Automate BGE-M3 embedding ingestion on vast.ai GPU instance.

This script:
1. Provisions a vast.ai GPU instance
2. Uploads JSONL files (40MB)
3. Clones GitHub repo and runs make ingest-only
4. Downloads Qdrant storage back to local machine
5. Destroys instance

Requirements:
- vast.ai CLI: pip install vastai
- vast.ai API key: vastai set api-key YOUR_KEY
- GitHub repo must be public (for cloning)

Cost: ~$0.10-0.20 total
"""

import subprocess
import json
import time
import sys
from pathlib import Path
from typing import Optional, Dict, Any


class VastAIIngestion:
    """Automate ingestion on vast.ai GPU instance."""

    def __init__(self,
                 max_price: float = 0.20,  # Max $/hour
                 min_gpu_ram: int = 12,    # Minimum GPU RAM in GB
                 disk_size: int = 30,      # GB
                 min_download_speed: int = 100,  # Mbps (for downloading BGE-M3 model)
                 min_upload_speed: int = 50):    # Mbps (for uploading results)
        self.max_price = max_price
        self.min_gpu_ram = min_gpu_ram
        self.disk_size = disk_size
        self.min_download_speed = min_download_speed
        self.min_upload_speed = min_upload_speed
        self.instance_id: Optional[int] = None
        self.ssh_host: Optional[str] = None
        self.ssh_port: Optional[int] = None

        # Paths
        self.project_root = Path(__file__).parent.parent
        self.code_travail_jsonl = self.project_root / "data" / "processed" / "code_travail_chunks.jsonl"
        self.kali_jsonl = self.project_root / "data" / "processed" / "kali_chunks.jsonl"
        self.qdrant_storage = self.project_root / "qdrant_storage"

    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met."""
        print("🔍 Checking prerequisites...")

        # Check vast.ai CLI
        try:
            result = subprocess.run(["vastai", "--version"],
                                   capture_output=True, text=True, check=True)
            print(f"   ✅ vast.ai CLI installed: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("   ❌ vast.ai CLI not found")
            print("      Install: pip install vastai")
            return False

        # Check API key
        try:
            subprocess.run(["vastai", "show", "user"],
                          capture_output=True, check=True)
            print("   ✅ vast.ai API key configured")
        except subprocess.CalledProcessError:
            print("   ❌ vast.ai API key not set")
            print("      Set key: vastai set api-key YOUR_KEY")
            print("      Get key from: https://cloud.vast.ai/account/")
            return False

        # Check JSONL files
        if not self.code_travail_jsonl.exists():
            print(f"   ❌ Missing: {self.code_travail_jsonl}")
            return False
        if not self.kali_jsonl.exists():
            print(f"   ❌ Missing: {self.kali_jsonl}")
            return False

        print(f"   ✅ code_travail_chunks.jsonl ({self.code_travail_jsonl.stat().st_size / 1024 / 1024:.1f}MB)")
        print(f"   ✅ kali_chunks.jsonl ({self.kali_jsonl.stat().st_size / 1024 / 1024:.1f}MB)")

        return True

    def search_instances(self) -> Optional[int]:
        """Search for available GPU instances."""
        print(f"\n🔎 Searching for GPU instances...")
        print(f"   Filters:")
        print(f"     - GPU RAM >= {self.min_gpu_ram}GB")
        print(f"     - Price <= ${self.max_price}/hr")
        print(f"     - Download >= {self.min_download_speed} Mbps")
        print(f"     - Upload >= {self.min_upload_speed} Mbps")

        # Search query
        query = (
            f"gpu_ram >= {self.min_gpu_ram} "
            f"reliability > 0.95 "
            f"num_gpus=1 "
            f"dph_total <= {self.max_price} "
            f"cuda_max_good >= 12.0 "
            f"inet_down >= {self.min_download_speed} "
            f"inet_up >= {self.min_upload_speed}"
        )

        try:
            result = subprocess.run(
                ["vastai", "search", "offers", query,
                 "--order", "dph_total", "--raw"],
                capture_output=True, text=True, check=True
            )

            offers = json.loads(result.stdout)

            if not offers:
                print("   ❌ No instances found matching criteria")
                print(f"      Try increasing max_price (current: ${self.max_price}/hr)")
                return None

            # Show top 3 options
            print(f"\n   Found {len(offers)} instances. Top 3:")
            for i, offer in enumerate(offers[:3], 1):
                print(f"   {i}. ${offer['dph_total']:.3f}/hr | "
                      f"{offer['gpu_name']} | "
                      f"{offer['gpu_ram']/1024:.0f}GB VRAM | "
                      f"↓{offer.get('inet_down', 0):.0f}Mbps ↑{offer.get('inet_up', 0):.0f}Mbps | "
                      f"Reliability: {offer.get('reliability2', 0):.1%}")

            # Select cheapest
            best_offer = offers[0]
            print(f"\n   ✅ Selected: {best_offer['gpu_name']} @ ${best_offer['dph_total']:.3f}/hr")

            return best_offer['id']

        except subprocess.CalledProcessError as e:
            print(f"   ❌ Search failed: {e.stderr}")
            return None
        except json.JSONDecodeError as e:
            print(f"   ❌ Failed to parse results: {e}")
            return None

    def create_instance(self, offer_id: int) -> bool:
        """Create instance from offer."""
        print(f"\n🚀 Creating instance...")

        # Use PyTorch image with all dependencies
        image = "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime"

        try:
            result = subprocess.run(
                ["vastai", "create", "instance", str(offer_id),
                 "--image", image,
                 "--disk", str(self.disk_size),
                 "--raw"],
                capture_output=True, text=True, check=True
            )

            response = json.loads(result.stdout)
            self.instance_id = response.get('new_contract')

            if not self.instance_id:
                print(f"   ❌ Failed to create instance: {response}")
                return False

            print(f"   ✅ Instance created: ID {self.instance_id}")
            return True

        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            print(f"   ❌ Creation failed: {e}")
            return False

    def wait_for_instance(self, timeout: int = 300) -> bool:
        """Wait for instance to be ready."""
        print(f"\n⏳ Waiting for instance to be ready (timeout: {timeout}s)...")

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(
                    ["vastai", "show", "instance", str(self.instance_id), "--raw"],
                    capture_output=True, text=True, check=True
                )

                instance = json.loads(result.stdout)
                status = instance.get('actual_status', 'unknown')

                print(f"   Status: {status}", end='\r')

                if status == 'running':
                    # Get SSH details
                    self.ssh_host = instance.get('public_ipaddr')
                    self.ssh_port = instance.get('ssh_port')

                    if self.ssh_host and self.ssh_port:
                        print(f"\n   ✅ Instance running: {self.ssh_host}:{self.ssh_port}")
                        return True

                time.sleep(5)

            except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
                print(f"\n   ❌ Status check failed: {e}")
                time.sleep(5)
                continue

        print(f"\n   ❌ Timeout waiting for instance")
        return False

    def upload_files(self) -> bool:
        """Upload JSONL files to instance."""
        print(f"\n📤 Uploading JSONL files...")

        ssh_target = f"root@{self.ssh_host}"
        ssh_opts = f"-p {self.ssh_port} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

        # Create remote directory
        try:
            subprocess.run(
                f"ssh {ssh_opts} {ssh_target} 'mkdir -p /workspace/data/processed'",
                shell=True, check=True, capture_output=True
            )
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Failed to create directory: {e.stderr.decode()}")
            return False

        # Upload files
        files = [
            (self.code_travail_jsonl, "code_travail_chunks.jsonl"),
            (self.kali_jsonl, "kali_chunks.jsonl")
        ]

        for local_path, filename in files:
            print(f"   Uploading {filename}...")
            try:
                subprocess.run(
                    f"scp {ssh_opts} {local_path} {ssh_target}:/workspace/data/processed/",
                    shell=True, check=True, capture_output=True
                )
                print(f"   ✅ {filename} uploaded")
            except subprocess.CalledProcessError as e:
                print(f"   ❌ Upload failed: {e.stderr.decode()}")
                return False

        return True

    def run_ingestion(self) -> bool:
        """Run ingestion on remote instance."""
        print(f"\n🔮 Running ingestion on vast.ai instance...")

        ssh_target = f"root@{self.ssh_host}"
        ssh_opts = f"-p {self.ssh_port} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

        commands = [
            # Install system dependencies
            "apt-get update -qq && apt-get install -y -qq git curl make docker.io",

            # Install Poetry
            "curl -sSL https://install.python-poetry.org | python3 -",
            "export PATH='/root/.local/bin:$PATH'",

            # Clone repo
            "cd /workspace && git clone https://github.com/psorianom/admin-rag.git",
            "cd /workspace/admin-rag",

            # Copy JSONL files to repo
            "cp /workspace/data/processed/*.jsonl ./data/processed/",

            # Run ingestion
            "/root/.local/bin/poetry install",
            "make start-qdrant",
            "sleep 5",  # Wait for Qdrant to start
            "/root/.local/bin/poetry run python src/retrieval/ingest_code_travail.py",
            "/root/.local/bin/poetry run python src/retrieval/ingest_kali.py",
        ]

        full_command = " && ".join(commands)

        try:
            print("   This will take ~15-20 minutes (downloading model + embedding)...")
            result = subprocess.run(
                f"ssh {ssh_opts} {ssh_target} '{full_command}'",
                shell=True, check=True, text=True, capture_output=False  # Show output
            )
            print(f"\n   ✅ Ingestion completed successfully")
            return True

        except subprocess.CalledProcessError as e:
            print(f"\n   ❌ Ingestion failed")
            return False

    def download_results(self) -> bool:
        """Download Qdrant storage from instance."""
        print(f"\n📥 Downloading Qdrant storage...")

        ssh_target = f"root@{self.ssh_host}"
        ssh_opts = f"-p {self.ssh_port} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

        # Create local directory
        self.qdrant_storage.mkdir(exist_ok=True)

        try:
            subprocess.run(
                f"scp -r {ssh_opts} {ssh_target}:/workspace/admin-rag/qdrant_storage/* {self.qdrant_storage}/",
                shell=True, check=True
            )
            print(f"   ✅ Downloaded to {self.qdrant_storage}")
            return True

        except subprocess.CalledProcessError as e:
            print(f"   ❌ Download failed: {e}")
            return False

    def destroy_instance(self) -> bool:
        """Destroy the instance."""
        if not self.instance_id:
            return True

        print(f"\n🗑️  Destroying instance {self.instance_id}...")

        try:
            subprocess.run(
                ["vastai", "destroy", "instance", str(self.instance_id)],
                check=True, capture_output=True
            )
            print(f"   ✅ Instance destroyed")
            return True

        except subprocess.CalledProcessError as e:
            print(f"   ❌ Destruction failed: {e.stderr.decode()}")
            return False

    def run(self) -> bool:
        """Run the complete workflow."""
        print("="*80)
        print("Vast.ai Automated Ingestion")
        print("="*80)

        try:
            # Prerequisites
            if not self.check_prerequisites():
                return False

            # Search and create
            offer_id = self.search_instances()
            if not offer_id:
                return False

            if not self.create_instance(offer_id):
                return False

            # Wait for ready
            if not self.wait_for_instance():
                self.destroy_instance()
                return False

            # Upload files
            if not self.upload_files():
                self.destroy_instance()
                return False

            # Run ingestion
            if not self.run_ingestion():
                self.destroy_instance()
                return False

            # Download results
            if not self.download_results():
                self.destroy_instance()
                return False

            # Cleanup
            self.destroy_instance()

            # Success!
            print("\n" + "="*80)
            print("✅ SUCCESS!")
            print("="*80)
            print(f"Qdrant storage downloaded to: {self.qdrant_storage}")
            print(f"\nTo use locally:")
            print(f"  make start-qdrant")
            print(f"  # Qdrant will load from {self.qdrant_storage}")
            print(f"\nDashboard: http://localhost:6333/dashboard")

            return True

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            if self.instance_id:
                print("Cleaning up...")
                self.destroy_instance()
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            if self.instance_id:
                print("Cleaning up...")
                self.destroy_instance()
            return False


def main():
    """Main entry point."""
    ingestion = VastAIIngestion(
        max_price=0.25,           # Max $/hour
        min_gpu_ram=12,           # Minimum 12GB VRAM for BGE-M3
        disk_size=30,             # GB
        min_download_speed=100,   # Mbps (for downloading BGE-M3 model ~2GB)
        min_upload_speed=50       # Mbps (for uploading Qdrant storage ~200MB)
    )

    success = ingestion.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
