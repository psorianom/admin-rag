"""
Configuration constants loaded from environment variables.

Usage:
    from src.config.constants import QDRANT_CONFIG

    # Access configuration
    config = QDRANT_CONFIG
    if config["type"] == "cloud":
        url = config["cloud"]["url"]
        api_key = config["cloud"]["api_key"]
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
project_root = Path(__file__).parent.parent.parent
dotenv_path = project_root / ".env"
load_dotenv(dotenv_path)


def get_qdrant_config() -> dict:
    """
    Get Qdrant configuration from environment variables.

    Returns:
        dict: Configuration with cloud and local settings
    """
    qdrant_type = os.getenv("QDRANT_TYPE", "local")

    config = {
        "type": qdrant_type,
        "cloud": {
            "url": os.getenv("QDRANT_CLOUD_URL"),
            "api_key": os.getenv("QDRANT_CLOUD_API_KEY"),
        },
        "local": {
            "url": os.getenv("QDRANT_LOCAL_URL", "http://localhost:6333"),
            "api_key": None,
        }
    }

    return config


# Export configuration
QDRANT_CONFIG = get_qdrant_config()
