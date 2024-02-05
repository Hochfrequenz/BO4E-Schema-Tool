import shutil
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from pydantic import TypeAdapter

from bost.__main__ import main
from bost.pull import SchemaInFileTree
from bost.schema import Object, StrEnum, String

if TYPE_CHECKING:
    from requests_mock import Context, Request


OUTPUT_DIR = Path(__file__).parent / "output/bo4e_schemas"
CACHE_DIR = Path(__file__).parent / "output/bo4e_cache"
CONFIG_FILE = Path(__file__).parent / "config_test.json"


class TestMain:
    def test_main_without_mocks(self):
        pytest.skip("Unmocked test is skipped in CI")
        main(
            output=OUTPUT_DIR,
            target_version="v0.6.1-rc13",
            config_file=None,
            update_refs=True,
            set_default_version=False,
            clear_output=True,
            cache_dir=None,
        )

    @patch("bost.pull.Github")
    def test_github_tree_query(self, mock_github):
        def mock_get_schema(url, ref):
            values = {}
            for pkg in ("bo", "com", "enum"):
                models = TypeAdapter(list[SchemaInFileTree]).validate_json(
                    (Path(__file__).parent / f"test_data/tree_query_response_{pkg}.json").read_text()
                )
                values[(f"src/bo4e_schemas/{pkg}", "v0.6.1-rc13")] = list(models)
            return values[(url, ref)]

        test_cache = True

        mock_repo = Mock()
        mock_github.return_value.get_repo.return_value = mock_repo
        mock_repo.get_contents.side_effect = mock_get_schema

        mock_response = Mock()
        mock_response.json.return_value = {"tag_name": "v0.6.1-rc13"}
        mock_response.raise_for_status.return_value = None

        if test_cache:
            # Delete the cache dir if present to ensure a dry run at first.
            # Somehow, when creating a release and the cli tests are running, there seems to be cached data.
            # I don't know what's going on there.
            shutil.rmtree(CACHE_DIR, ignore_errors=True)
        main(
            output=OUTPUT_DIR,
            target_version="v0.6.1-rc13",
            config_file=CONFIG_FILE,
            update_refs=True,
            set_default_version=True,
            clear_output=True,
            cache_dir=CACHE_DIR,
        )
        if test_cache:
            # This tests other parts of the cache implementation
            main(
                output=OUTPUT_DIR,
                target_version="v0.6.1-rc13",
                config_file=CONFIG_FILE,
                update_refs=True,
                set_default_version=True,
                clear_output=True,
                cache_dir=CACHE_DIR,
            )

        assert (OUTPUT_DIR / "bo" / "Angebot.json").exists()
        assert (OUTPUT_DIR / "com" / "COM.json").exists()
        assert (OUTPUT_DIR / "enum" / "Typ.json").exists()
        assert (OUTPUT_DIR / "bo" / "AdditionalModel.json").exists()

        angebot_schema = Object.model_validate_json((OUTPUT_DIR / "bo" / "Angebot.json").read_text())
        assert angebot_schema.title == "Angebot"
        assert "foo" in angebot_schema.properties
        additional_model_schema = Object.model_validate_json((OUTPUT_DIR / "bo" / "AdditionalModel.json").read_text())
        assert additional_model_schema.title == "AdditionalModel"
        assert additional_model_schema.properties["_version"].default == "v0.6.1-rc13"
        assert isinstance(additional_model_schema.properties["_version"], String)

        typ_schema = StrEnum.model_validate_json((OUTPUT_DIR / "enum" / "Typ.json").read_text())
        assert typ_schema.title == "Typ"
        assert "foo" in typ_schema.enum
        assert "bar" in typ_schema.enum
