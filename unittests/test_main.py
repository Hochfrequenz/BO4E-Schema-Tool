import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
import requests_mock
from pydantic import parse_obj_as, TypeAdapter

from bost.__main__ import main
from bost.pull import get_github_repo_info, SchemaInFileTree, _github_tree_query
from bost.schema import Object, StrEnum, String

if TYPE_CHECKING:
    from requests_mock import Context, Request


OUTPUT_DIR = Path(__file__).parent / "output/bo4e_schemas"
CACHE_DIR = Path(__file__).parent / "output/bo4e_cache"
CONFIG_FILE = Path(__file__).parent / "config_test.json"

def side_effect(url, ref):
    bo_models = TypeAdapter(list[SchemaInFileTree]).validate_json(
        (Path(__file__).parent / f"test_data/tree_query_response_bo.json").read_text())
    com_models = TypeAdapter(list[SchemaInFileTree]).validate_json(
        (Path(__file__).parent / f"test_data/tree_query_response_com.json").read_text())
    enum_models = TypeAdapter(list[SchemaInFileTree]).validate_json(
        (Path(__file__).parent / f"test_data/tree_query_response_enum.json").read_text())
    values = {("src/bo4e_schemas/bo", "version"): [model for model in bo_models],
              ("src/bo4e_schemas/com", "version"): [model for model in com_models],
              ("src/bo4e_schemas/com", "version"): [model for model in enum_models]}
    return values[(url, ref)]

class TestMain:
    def test_main_without_mocks(self):
        #pytest.skip("Unmocked test is skipped in CI")
        main(
            output=OUTPUT_DIR,
            target_version="v0.6.1-rc13",
            config_file=None,
            update_refs=True,
            set_default_version=False,
            clear_output=True,
            cache_dir=None,
        )

    @patch('bost.pull.Github')
    def test_github_tree_query(self, mock_github):
        # Mock the Github object and its methods
        mock_repo = Mock()
        mock_github.return_value.get_repo.return_value = mock_repo

        bo_models = TypeAdapter(list[SchemaInFileTree]).validate_json((Path(__file__).parent / f"test_data/tree_query_response_bo.json").read_text())
        mock_repo.get_contents.side_effect = side_effect

        # Call the function under test
        result = _github_tree_query('bo', 'version')

        # Assert that the Github object and its methods were called with the correct arguments
        mock_github.assert_called_once()


    def test_main_with_mocks(self):
        test_cache = True
        # Mock request URLs
        with requests_mock.Mocker() as mocker:
            for pkg in ["bo", "com", "enum"]:
                mocker.get(
                    "https://api.github.com/repos/Hochfrequenz/BO4E-Schemas/contents/src/"
                    f"bo4e_schemas/{pkg}?ref=v0.6.1-rc13",
                    text=(Path(__file__).parent / f"test_data/tree_query_response_{pkg}.json").read_text(),
                )

            def mock_get_schema(request: "Request", _: "Context") -> str:
                # pylint: disable=protected-access
                match = re.search(r"src/bo4e_schemas/(bo|com|enum)/(\w+)\.json", request._request.url)
                assert match is not None
                return (
                    Path(__file__).parent / f"test_data/bo4e_schemas/{match.group(1)}/{match.group(2)}.json"
                ).read_text()

            mocker.get(
                re.compile(
                    r"https://raw\.githubusercontent\.com/Hochfrequenz/BO4E-Schemas/v0\.6\.1-rc13/src/"
                    r"bo4e_schemas/(bo|com|enum)/(\w+)\.json"
                ),
                text=mock_get_schema,
            )

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
            additional_model_schema = Object.model_validate_json(
                (OUTPUT_DIR / "bo" / "AdditionalModel.json").read_text()
            )
            assert additional_model_schema.title == "AdditionalModel"
            assert additional_model_schema.properties["_version"].default == "v0.6.1-rc13"
            assert isinstance(additional_model_schema.properties["_version"], String)

            typ_schema = StrEnum.model_validate_json((OUTPUT_DIR / "enum" / "Typ.json").read_text())
            assert typ_schema.title == "Typ"
            assert "foo" in typ_schema.enum
            assert "bar" in typ_schema.enum
