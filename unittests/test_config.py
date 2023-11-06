from pathlib import Path

from bost.config import load_config


class TestConfig:
    def test_load_config(self):
        _ = load_config(Path(__file__).parent / "config_test.json")
