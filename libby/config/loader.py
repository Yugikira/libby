"""Configuration loading."""

import os
from pathlib import Path

import yaml

from libby.config.defaults import DEFAULT_CONFIG_PATH, DEFAULT_CONFIG_YAML
from libby.models.config import (
    LibbyConfig, CitekeyConfig, RetryConfig,
    AIExtractorConfig, SerpapiConfig, SemanticScholarConfig, UnpaywallConfig
)


def load_config(config_path: Path | None = None) -> LibbyConfig:
    """Load configuration from file.

    Priority:
    1. CLI --config path (config_path argument)
    2. LIBBY_CONFIG environment variable
    3. Default ~/.libby/config.yaml
    """
    # Determine config path
    if config_path:
        path = config_path
    elif os.getenv("LIBBY_CONFIG"):
        path = Path(os.getenv("LIBBY_CONFIG"))
    else:
        path = DEFAULT_CONFIG_PATH

    # Load YAML
    if path.exists():
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    # Merge with defaults
    return LibbyConfig(
        lib_dir=Path(data.get("lib_dir", "~/.lib")).expanduser(),
        citekey=CitekeyConfig(**data.get("citekey", {})),
        retry=RetryConfig(**data.get("retry", {})),
        serpapi=SerpapiConfig(**data.get("serpapi", {})),
        semantic_scholar=SemanticScholarConfig(**data.get("semantic_scholar", {})),
        unpaywall=UnpaywallConfig(**data.get("unpaywall", {})),
        ai_extractor=AIExtractorConfig(**data.get("ai_extractor", {})),
        config_path=path,
    )