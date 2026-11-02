"""
Configuration for the Searchable PDF Generator v2 demo server.

This public build ships without the OCR engine. At startup a read-only demo
session is built from the pre-processed samples under demo_samples/.
"""
import os
from pathlib import Path
from typing import Optional

import yaml


class Config:
    """Application configuration"""

    # Base paths: BASE_DIR is the repository root, SERVER_DIR this folder
    SERVER_DIR = Path(__file__).parent
    BASE_DIR = SERVER_DIR.parent
    DATA_DIR = SERVER_DIR / "data"

    # Data directories (created at startup, ignored by git)
    RAW_DIR = DATA_DIR / "raw"
    PROCESSED_DIR = DATA_DIR / "processed"
    DEBUG_DIR = DATA_DIR / "debug"
    TEMP_DIR = DATA_DIR / "temp"

    # Pre-processed demo samples
    DEMO_SAMPLES_DIR = Path(os.getenv("DEMO_SAMPLES_DIR", str(BASE_DIR / "demo_samples")))

    # Server settings
    BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
    BACKEND_PORT = int(os.getenv("BACKEND_PORT", "5015"))
    CORS_ORIGINS = [
        "http://localhost:5017",
        "http://127.0.0.1:5017",
    ]

    # Default user (single-user demo)
    DEFAULT_USER_ID = "user001"
    DEFAULT_USER_NAME = "사용자"
    DEFAULT_USER_EMAIL = "user@email.com"

    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist"""
        for directory in [cls.RAW_DIR, cls.PROCESSED_DIR, cls.DEBUG_DIR, cls.TEMP_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load_from_yaml(cls, yaml_path: Optional[Path] = None):
        """Load server and demo settings from config.yaml"""
        if yaml_path is None:
            yaml_path = cls.SERVER_DIR / "config.yaml"
        if not yaml_path.exists():
            return

        with open(yaml_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) or {}

        server = config_data.get("server", {})
        if "backend" in server:
            cls.BACKEND_HOST = server["backend"].get("host", cls.BACKEND_HOST)
            cls.BACKEND_PORT = server["backend"].get("port", cls.BACKEND_PORT)
        if "cors_origins" in server:
            cls.CORS_ORIGINS = server["cors_origins"]

        # Environment variables take precedence over config.yaml
        demo = config_data.get("demo", {})
        if "samples_dir" in demo and not os.getenv("DEMO_SAMPLES_DIR"):
            samples_dir = Path(demo["samples_dir"])
            cls.DEMO_SAMPLES_DIR = samples_dir if samples_dir.is_absolute() else cls.BASE_DIR / samples_dir


# Initialize configuration
Config.ensure_directories()
if (Config.SERVER_DIR / "config.yaml").exists():
    Config.load_from_yaml()
