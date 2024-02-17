import pickle
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
import requests_mock
from click.testing import CliRunner

from bost.__main__ import main, main_command_line
from bost.schema import Object, StrEnum, String

if TYPE_CHECKING:
    from requests_mock import Context, Request


OUTPUT_DIR = Path(__file__).parent / "output/bo4e_schemas"
CACHE_DIR = Path(__file__).parent / "output/bo4e_cache"
CONFIG_FILE = Path(__file__).parent / "config_test.json"
TEST_DATA_DIR = Path(__file__).parent / "test_data"


class TestMain:
    def test_main_help(self):
        """
        If you are modifying the CLI help description, please execute this test and update the README.md by copying
        the output of this test into the README.md.
        """
        cli_runner = CliRunner()
        result = cli_runner.invoke(main_command_line, ["--help"])
        print("\n")
        print(result.output.replace("Usage: main-command-line", "Usage: bost"))
        assert result.exit_code == 0
        assert "Usage: main" in result.output

    def test_main_without_mocks(self):
        pytest.skip("Unmocked test is skipped in CI")
        main(
            output=OUTPUT_DIR,
            target_version="v0.6.1-rc13",
            config_file=None,
            update_refs=True,
            set_default_version=False,
            clear_output=True,
            cache_dir=CACHE_DIR,
        )

    @patch("bost.pull.Github")
    def test_github_tree_query(self, mock_github):
        def new_get_contents(path, ref):  # pylint: disable=unused-argument
            return pickle.load(open(TEST_DATA_DIR / f"contents_{path.replace('/', '_')}.pkl", mode="rb"))

        test_cache = True

        mock_repo = Mock()
        mock_github.return_value.get_repo.return_value = mock_repo
        # pylint: disable=consider-using-with
        mock_repo.get_release.return_value = pickle.load(open(TEST_DATA_DIR / "release.pkl", mode="rb"))
        mock_repo.get_git_tree.return_value = pickle.load(open(TEST_DATA_DIR / "tree.pkl", mode="rb"))
        mock_repo.get_contents = new_get_contents

        mock_response = Mock()
        mock_response.json.return_value = {"tag_name": "v0.6.1-rc13"}
        mock_response.raise_for_status.return_value = None

        if test_cache:
            # Delete the cache dir if present to ensure a dry run at first.
            # Somehow, when creating a release and the cli tests are running, there seems to be cached data.
            # I don't know what's going on there.
            shutil.rmtree(CACHE_DIR, ignore_errors=True)
        with requests_mock.Mocker() as mocker:

            def mock_get_schema(request: "Request", _: "Context") -> str:
                # pylint: disable=protected-access
                match = re.search(r"src/bo4e_schemas/(.*/|)(\w+)\.json", request._request.url)
                assert match is not None
                return (
                    Path(__file__).parent / f"test_data/bo4e_schemas/{match.group(1)}{match.group(2)}.json"
                ).read_text()

            mocker.get(
                re.compile(
                    r"https://raw\.githubusercontent\.com/bo4e/BO4E-Schemas/(?:v0\.6\.1-rc13|[\w\d]+)/src/"
                    r"bo4e_schemas/(.*/|)(\w+)\.json"
                ),
                text=mock_get_schema,
            )

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
