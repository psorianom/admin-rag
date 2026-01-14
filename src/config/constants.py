"""
Configuration constants loaded from environment variables.

Usage:
    from src.config.constants import QDRANT_CONFIG, LLM_CONFIG

    # Access Qdrant configuration
    config = QDRANT_CONFIG
    if config["type"] == "cloud":
        url = config["cloud"]["url"]
        api_key = config["cloud"]["api_key"]

    # Access LLM configuration
    llm_config = LLM_CONFIG
    provider = llm_config["provider"]
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


# Export Qdrant configuration
QDRANT_CONFIG = get_qdrant_config()


def get_llm_config() -> dict:
    """
    Get LLM configuration from environment variables.

    Returns:
        dict: Configuration with provider and API settings
    """
    provider = os.getenv("LLM_PROVIDER", "openai")

    config = {
        "provider": provider,
        "openai": {
            "api_key": os.getenv("OPENAI_API_KEY"),
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        }
    }

    return config


# Export LLM configuration
LLM_CONFIG = get_llm_config()
