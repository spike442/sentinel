import os
from pathlib import Path

import yaml

CONFIG_FILES = ("logging.yaml", "s3.yaml", "spark.yml")


def load_config() -> dict:
    directory = Path(os.environ.get("SENTINEL_CONFIG_DIR", "/etc/sentinel"))
    config = {}
    for name in CONFIG_FILES:
        path = directory / name
        loaded = yaml.safe_load(path.read_text())
        config.update(loaded)
    return config
