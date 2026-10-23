import os
from pathlib import Path

import yaml

CONFIG_FILES = ("logging.yaml", "s3.yaml", "storage.yaml")


def load_config() -> dict:
    directory = Path(os.environ.get("STONKS_CONFIG_DIR", "/etc/stonks"))
    config = {}
    for name in CONFIG_FILES:
        path = directory / name
        loaded = yaml.safe_load(path.read_text())
        config.update(loaded)
    return config
