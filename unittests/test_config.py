from pathlib import Path

from bost.config import Config, load_config


class TestConfig:
    def test_load_config(self):
        _ = load_config(Path(__file__).parent / "config_test.json")

    def test_config_optional_fields(self):
        _ = Config.model_validate({})
