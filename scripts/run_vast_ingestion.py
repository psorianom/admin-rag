"""
Automate BGE-M3 embedding generation on vast.ai GPU instance.

This script:
1. Provisions a vast.ai GPU instance
2. Uploads JSONL files (40MB) and embedding script
3. Generates BGE-M3 embeddings on GPU
4. Downloads embedded JSONL files back to local machine (gzipped)
5. Destroys instance

Requirements:
- vast.ai CLI: pip install vastai
- vast.ai API key: vastai set api-key YOUR_KEY

Cost: ~$0.10-0.20 total

After download:
1. Decompress: gunzip data/processed/*.jsonl.gz
2. Index locally: make ingest-only
"""

import subprocess
import json
import time
import sys
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


def setup_logging() -> logging.Logger:
    """Setup logging to file and console."""
    # Create logs directory
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    # Log file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"vast_ingestion_{timestamp}.log"

    # Configure logging
    logger = logging.getLogger("VastAIIngestion")
    logger.setLevel(logging.DEBUG)

    # File handler (DEBUG level - everything)
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)

    # Console handler (INFO level - important stuff)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info(f"Logging to: {log_file}")

    return logger


class VastAIIngestion:
    """Automate ingestion on vast.ai GPU instance."""

    def __init__(self,
                 max_price: float = 0.20,  # Max $/hour
                 min_gpu_ram: int = 12,    # Minimum GPU RAM in GB
                 disk_size: int = 30,      # GB
                 min_download_speed: int = 100,  # Mbps (for downloading BGE-M3 model)
                 min_upload_speed: int = 50,     # Mbps (for uploading results)
                 keep_alive: bool = False):      # Keep instance running after completion
        self.max_price = max_price
        self.min_gpu_ram = min_gpu_ram
        self.disk_size = disk_size
        self.min_download_speed = min_download_speed
        self.min_upload_speed = min_upload_speed
        self.keep_alive = keep_alive
        self.instance_id: Optional[int] = None
        self.ssh_host: Optional[str] = None
        self.ssh_port: Optional[int] = None

        # Paths
        self.project_root = Path(__file__).parent.parent
        self.code_travail_jsonl = self.project_root / "data" / "processed" / "code_travail_chunks.jsonl"
        self.kali_jsonl = self.project_root / "data" / "processed" / "kali_chunks.jsonl"

        # Setup logging
        self.logger = setup_logging()

    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met."""
        print("🔍 Checking prerequisites...")
        self.logger.info("Starting prerequisite checks")

        # Check vast.ai CLI
        try:
            result = subprocess.run(["vastai", "--version"],
                                   capture_output=True, text=True, check=True)
            version = result.stdout.strip()
            print(f"   ✅ vast.ai CLI installed: {version}")
            self.logger.info(f"vast.ai CLI version: {version}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print("   ❌ vast.ai CLI not found")
            print("      Install: pip install vastai")
            self.logger.error(f"vast.ai CLI not found: {e}")
            return False

        # Check API key
        try:
            subprocess.run(["vastai", "show", "user"],
                          capture_output=True, check=True)
            print("   ✅ vast.ai API key configured")
            self.logger.info("vast.ai API key is configured")
        except subprocess.CalledProcessError as e:
            print("   ❌ vast.ai API key not set")
            print("      Set key: vastai set api-key YOUR_KEY")
            print("      Get key from: https://cloud.vast.ai/account/")
            self.logger.error(f"vast.ai API key not set: {e}")
            return False

        # Check JSONL files
        if not self.code_travail_jsonl.exists():
            print(f"   ❌ Missing: {self.code_travail_jsonl}")
            self.logger.error(f"Missing file: {self.code_travail_jsonl}")
            return False
        if not self.kali_jsonl.exists():
            print(f"   ❌ Missing: {self.kali_jsonl}")
            self.logger.error(f"Missing file: {self.kali_jsonl}")
            return False

        code_travail_size = self.code_travail_jsonl.stat().st_size / 1024 / 1024
        kali_size = self.kali_jsonl.stat().st_size / 1024 / 1024
        print(f"   ✅ code_travail_chunks.jsonl ({code_travail_size:.1f}MB)")
        print(f"   ✅ kali_chunks.jsonl ({kali_size:.1f}MB)")
        self.logger.info(f"JSONL files found: code_travail={code_travail_size:.1f}MB, kali={kali_size:.1f}MB")

        self.logger.info("All prerequisites met")
        return True

    def search_instances(self) -> Optional[int]:
        """Search for available GPU instances."""
        print(f"\n🔎 Searching for GPU instances...")
        print(f"   Filters:")
        print(f"     - GPU RAM >= {self.min_gpu_ram}GB")
        print(f"     - Price <= ${self.max_price}/hr")
        print(f"     - Download perf >= {self.min_download_speed} Mbps")
        print(f"     - Reliability > 0.95")

        # Search query - using dlperf (tested) instead of inet_down (self-reported)
        query = (
            f"gpu_ram >= {self.min_gpu_ram} "
            f"reliability > 0.95 "
            f"num_gpus=1 "
            f"dph_total <= {self.max_price} "
            f"cuda_max_good >= 12.0 "
            f"dlperf >= {self.min_download_speed} "  # Actual tested download performance
            f"disk_space >= {self.disk_size}"
        )

        self.logger.info(f"Searching instances with query: {query}")

        try:
            # Sort by score (ML workload performance) then price
            # Score considers: reliability, bandwidth, compute capability
            result = subprocess.run(
                ["vastai", "search", "offers", query,
                 "--order", "score-", "--raw"],  # Sort by score descending (best first)
                capture_output=True, text=True, check=True
            )

            offers = json.loads(result.stdout)

            if not offers:
                print("   ❌ No instances found matching criteria")
                print(f"      Try increasing max_price (current: ${self.max_price}/hr)")
                print(f"      Or lowering min_download_speed (current: {self.min_download_speed} Mbps)")
                self.logger.warning(f"No instances found with criteria: max_price=${self.max_price}/hr, dlperf>={self.min_download_speed}")
                return None

            self.logger.info(f"Found {len(offers)} matching instances")

            # Show top 3 options
            print(f"\n   Found {len(offers)} instances. Top 3 (by score):")
            for i, offer in enumerate(offers[:3], 1):
                dlperf = offer.get('dlperf', 0)
                score = offer.get('score', 0)
                print(f"   {i}. ${offer['dph_total']:.3f}/hr | "
                      f"{offer['gpu_name']} | "
                      f"{offer['gpu_ram']/1024:.0f}GB VRAM | "
                      f"DL: {dlperf:.0f}Mbps | "
                      f"Score: {score:.1f} | "
                      f"Reliability: {offer.get('reliability2', 0):.1%}")
                self.logger.debug(f"Option {i}: {offer}")

            # Select best score
            best_offer = offers[0]
            print(f"\n   ✅ Selected: {best_offer['gpu_name']} @ ${best_offer['dph_total']:.3f}/hr (score: {best_offer.get('score', 0):.1f})")
            self.logger.info(f"Selected instance {best_offer['id']}: {best_offer['gpu_name']}, "
                           f"${best_offer['dph_total']:.3f}/hr, "
                           f"dlperf={best_offer.get('dlperf', 0):.0f}Mbps, score={best_offer.get('score', 0):.1f}")

            return best_offer['id']

        except subprocess.CalledProcessError as e:
            print(f"   ❌ Search failed: {e.stderr}")
            self.logger.error(f"Instance search failed: {e.stderr}")
            return None
        except json.JSONDecodeError as e:
            print(f"   ❌ Failed to parse results: {e}")
            self.logger.error(f"Failed to parse search results: {e}")
            return None

    def create_instance(self, offer_id: int) -> bool:
        """Create instance from offer."""
        print(f"\n🚀 Creating instance...")
        self.logger.info(f"Creating instance from offer {offer_id}")

        # Use PyTorch image with all dependencies
        image = "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime"
        self.logger.debug(f"Using Docker image: {image}")

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
                self.logger.error(f"Instance creation failed: {response}")
                return False

            print(f"   ✅ Instance created: ID {self.instance_id}")
            self.logger.info(f"Instance created successfully: ID {self.instance_id}")
            return True

        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            print(f"   ❌ Creation failed: {e}")
            self.logger.error(f"Instance creation failed: {e}")
            return False

    def wait_for_instance(self, timeout: int = 300) -> bool:
        """Wait for instance to be ready and SSH to be available."""
        print(f"\n⏳ Waiting for instance to be ready (timeout: {timeout}s)...")
        self.logger.info(f"Waiting for instance {self.instance_id} to be ready (timeout: {timeout}s)")

        start_time = time.time()
        ssh_ready = False

        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(
                    ["vastai", "show", "instance", str(self.instance_id), "--raw"],
                    capture_output=True, text=True, check=True
                )

                instance = json.loads(result.stdout)
                status = instance.get('actual_status', 'unknown')

                print(f"   Status: {status}", end='\r')
                elapsed = int(time.time() - start_time)
                self.logger.debug(f"Instance status: {status} (elapsed: {elapsed}s)")

                if status == 'running' and not ssh_ready:
                    # Get SSH details - vast.ai uses SSH gateway
                    self.ssh_host = instance.get('ssh_host', 'ssh2.vast.ai')  # Gateway host
                    self.ssh_port = instance.get('ssh_port')  # Port on gateway

                    if self.ssh_host and self.ssh_port:
                        print(f"\n   Instance running: {self.ssh_host}:{self.ssh_port}")
                        print(f"   Testing SSH connectivity...")
                        self.logger.info(f"Instance running, testing SSH: {self.ssh_host}:{self.ssh_port}")

                        # Test SSH connectivity
                        ssh_target = f"root@{self.ssh_host}"
                        ssh_opts = f"-p {self.ssh_port} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10"

                        try:
                            subprocess.run(
                                f"ssh {ssh_opts} {ssh_target} 'echo SSH_OK'",
                                shell=True, check=True, capture_output=True, timeout=15
                            )
                            print(f"   ✅ SSH ready!")
                            self.logger.info(f"SSH connectivity confirmed: {self.ssh_host}:{self.ssh_port}")
                            return True
                        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as ssh_error:
                            print(f"   SSH not ready yet, waiting...", end='\r')
                            self.logger.debug(f"SSH test failed (will retry): {ssh_error}")
                            ssh_ready = False

                time.sleep(5)

            except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
                print(f"\n   ❌ Status check failed: {e}")
                self.logger.warning(f"Status check failed: {e}")
                time.sleep(5)
                continue

        print(f"\n   ❌ Timeout waiting for instance")
        self.logger.error(f"Timeout waiting for instance after {timeout}s")
        return False

    def upload_files(self) -> bool:
        """Upload JSONL files and embedding script to instance."""
        print(f"\n📤 Uploading files...")
        self.logger.info(f"Starting file uploads to {self.ssh_host}:{self.ssh_port}")

        ssh_target = f"root@{self.ssh_host}"
        # Note: ssh uses -p (lowercase), scp uses -P (uppercase)
        ssh_opts = f"-p {self.ssh_port} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
        scp_opts = f"-P {self.ssh_port} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

        # Create remote directories
        try:
            self.logger.debug("Creating remote directories")
            subprocess.run(
                f"ssh {ssh_opts} {ssh_target} 'mkdir -p /workspace/data/processed /workspace/scripts'",
                shell=True, check=True, capture_output=True
            )
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Failed to create directories: {e.stderr.decode()}")
            self.logger.error(f"Failed to create remote directories: {e.stderr.decode()}")
            return False

        # Upload files
        embed_script = self.project_root / "scripts" / "embed_chunks.py"
        files = [
            (self.code_travail_jsonl, "/workspace/data/processed/", "code_travail_chunks.jsonl"),
            (self.kali_jsonl, "/workspace/data/processed/", "kali_chunks.jsonl"),
            (embed_script, "/workspace/scripts/", "embed_chunks.py")
        ]

        for local_path, remote_dir, filename in files:
            print(f"   Uploading {filename}...")
            size_mb = local_path.stat().st_size / 1024 / 1024
            self.logger.info(f"Uploading {filename} ({size_mb:.1f}MB)")

            start_time = time.time()
            try:
                subprocess.run(
                    f"scp {scp_opts} {local_path} {ssh_target}:{remote_dir}",
                    shell=True, check=True, capture_output=True
                )
                elapsed = time.time() - start_time
                speed_mbps = (size_mb * 8) / elapsed if elapsed > 0 else 0
                print(f"   ✅ {filename} uploaded ({elapsed:.1f}s, ~{speed_mbps:.0f} Mbps)")
                self.logger.info(f"{filename} uploaded: {elapsed:.1f}s, ~{speed_mbps:.0f} Mbps")
            except subprocess.CalledProcessError as e:
                print(f"   ❌ Upload failed: {e.stderr.decode()}")
                self.logger.error(f"Upload failed for {filename}: {e.stderr.decode()}")
                return False

        self.logger.info("All files uploaded successfully")
        return True

    def run_ingestion(self) -> bool:
        """Run embedding generation on remote instance."""
        print(f"\n🔮 Generating embeddings on vast.ai instance...")
        self.logger.info("Starting remote embedding generation")

        ssh_target = f"root@{self.ssh_host}"
        ssh_opts = f"-p {self.ssh_port} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

        commands = [
            # Upgrade PyTorch and install dependencies (fix compatibility)
            "pip install -q --upgrade torch torchvision torchaudio",
            "pip install -q sentence-transformers tqdm",

            # Run embedding script
            "cd /workspace && python scripts/embed_chunks.py",

            # Compress output files
            "gzip data/processed/code_travail_chunks.jsonl",
            "gzip data/processed/kali_chunks.jsonl",
        ]

        full_command = " && ".join(commands)
        self.logger.debug(f"Remote command: {full_command}")

        try:
            print("   This will take ~15-20 minutes (downloading model + embedding)...")
            self.logger.info("Running embedding generation (this will take 15-20 minutes)")

            start_time = time.time()
            result = subprocess.run(
                f"ssh {ssh_opts} {ssh_target} '{full_command}'",
                shell=True, check=True, text=True, capture_output=False  # Show output
            )
            elapsed = time.time() - start_time

            print(f"\n   ✅ Embedding generation completed successfully")
            self.logger.info(f"Embedding generation completed successfully in {elapsed/60:.1f} minutes")
            return True

        except subprocess.CalledProcessError as e:
            print(f"\n   ❌ Embedding generation failed")
            self.logger.error(f"Embedding generation failed: {e}")
            return False

    def download_results(self) -> bool:
        """Download embedded JSONL files from instance."""
        print(f"\n📥 Downloading embedded JSONL files...")
        self.logger.info(f"Downloading embedded JSONL files")

        ssh_target = f"root@{self.ssh_host}"
        # Note: scp uses -P (uppercase) for port
        scp_opts = f"-P {self.ssh_port} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

        # Download directory
        download_dir = self.project_root / "data" / "processed"
        download_dir.mkdir(exist_ok=True, parents=True)

        files_to_download = [
            "code_travail_chunks.jsonl.gz",
            "kali_chunks.jsonl.gz"
        ]

        try:
            for filename in files_to_download:
                print(f"   Downloading {filename}...")
                start_time = time.time()

                subprocess.run(
                    f"scp {scp_opts} {ssh_target}:/workspace/data/processed/{filename} {download_dir}/",
                    shell=True, check=True
                )

                elapsed = time.time() - start_time
                # Get file size for speed calculation
                local_file = download_dir / filename
                size_mb = local_file.stat().st_size / 1024 / 1024
                speed_mbps = (size_mb * 8) / elapsed if elapsed > 0 else 0

                print(f"   ✅ {filename} downloaded ({size_mb:.1f}MB, {elapsed:.1f}s, ~{speed_mbps:.0f} Mbps)")
                self.logger.info(f"{filename} downloaded: {size_mb:.1f}MB, {elapsed:.1f}s, ~{speed_mbps:.0f} Mbps")

            print(f"\n   📦 Files saved to: {download_dir}/")
            print(f"   Next steps:")
            print(f"     1. Decompress: gunzip {download_dir}/*.jsonl.gz")
            print(f"     2. Index locally: make ingest-only")
            self.logger.info("All files downloaded successfully")
            return True

        except subprocess.CalledProcessError as e:
            print(f"   ❌ Download failed: {e}")
            self.logger.error(f"Download failed: {e}")
            return False

    def destroy_instance(self) -> bool:
        """Destroy the instance."""
        if not self.instance_id:
            return True

        print(f"\n🗑️  Destroying instance {self.instance_id}...")
        self.logger.info(f"Destroying instance {self.instance_id}")

        try:
            subprocess.run(
                ["vastai", "destroy", "instance", str(self.instance_id)],
                check=True, capture_output=True
            )
            print(f"   ✅ Instance destroyed")
            self.logger.info(f"Instance {self.instance_id} destroyed successfully")
            return True

        except subprocess.CalledProcessError as e:
            print(f"   ❌ Destruction failed: {e.stderr.decode()}")
            self.logger.error(f"Instance destruction failed: {e.stderr.decode()}")
            return False

    def run(self) -> bool:
        """Run the complete workflow."""
        print("="*80)
        print("Vast.ai Automated Ingestion")
        print("="*80)

        self.logger.info("="*60)
        self.logger.info("Starting Vast.ai Automated Ingestion")
        self.logger.info("="*60)

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
                if not self.keep_alive:
                    self.destroy_instance()
                return False

            # Upload files
            if not self.upload_files():
                if not self.keep_alive:
                    self.destroy_instance()
                return False

            # Run ingestion
            if not self.run_ingestion():
                if not self.keep_alive:
                    self.destroy_instance()
                return False

            # Download results
            if not self.download_results():
                if not self.keep_alive:
                    self.destroy_instance()
                return False

            # Cleanup
            if self.keep_alive:
                print("\n" + "="*80)
                print("⚠️  Instance kept alive for testing")
                print("="*80)
                print(f"Instance ID: {self.instance_id}")
                print(f"SSH: ssh -p {self.ssh_port} root@{self.ssh_host}")
                print(f"\n⚠️  REMEMBER TO DESTROY MANUALLY:")
                print(f"  vastai destroy instance {self.instance_id}")
                self.logger.warning(f"Instance {self.instance_id} kept alive - destroy manually!")
            else:
                self.destroy_instance()

            # Success!
            print("\n" + "="*80)
            print("✅ SUCCESS!")
            print("="*80)
            print(f"Files downloaded to: data/processed/*.jsonl.gz")
            print(f"\nNext steps:")
            print(f"  1. Decompress: gunzip data/processed/*.jsonl.gz")
            print(f"  2. Index locally: make ingest-only")

            self.logger.info("="*60)
            self.logger.info("Ingestion workflow completed successfully!")
            self.logger.info("="*60)

            return True

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            self.logger.warning("Workflow interrupted by user")
            if self.instance_id and not self.keep_alive:
                print("Cleaning up...")
                self.destroy_instance()
            elif self.instance_id and self.keep_alive:
                print(f"\n⚠️  Instance {self.instance_id} kept alive")
                print(f"Destroy manually: vastai destroy instance {self.instance_id}")
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            self.logger.exception(f"Unexpected error: {e}")
            if self.instance_id and not self.keep_alive:
                print("Cleaning up...")
                self.destroy_instance()
            elif self.instance_id and self.keep_alive:
                print(f"\n⚠️  Instance {self.instance_id} kept alive")
                print(f"Destroy manually: vastai destroy instance {self.instance_id}")
            return False


def main():
    """Main entry point."""
    ingestion = VastAIIngestion(
        max_price=0.50,           # Max $/hour
        min_gpu_ram=24,           # Minimum 24GB VRAM for BGE-M3 with batch processing
        disk_size=30,             # GB
        min_download_speed=100,   # Mbps (for downloading BGE-M3 model ~2.7GB)
        min_upload_speed=50,      # Mbps (for uploading results ~50-70MB)
        keep_alive=True           # Keep instance running for testing (destroy manually)
    )

    success = ingestion.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
