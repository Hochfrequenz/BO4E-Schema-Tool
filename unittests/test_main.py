import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import requests_mock

from bost.__main__ import main
from bost.schema import Object

if TYPE_CHECKING:
    from requests_mock import Context, Request


OUTPUT_DIR = Path(__file__).parent / "output/bo4e_schemas"
CONFIG_FILE = Path(__file__).parent / "config_test.json"


class TestMain:
    def test_main_without_mocks(self):
        pytest.skip("Unmocked test is skipped in CI")
        main(output=OUTPUT_DIR, target_version="v0.6.1-rc13", config_file=None, update_refs=False)

    def test_main_with_mocks(self):
        # Mock request URLs
        with requests_mock.Mocker() as mocker:
            for pkg in ["bo", "com", "enum"]:
                mocker.get(
                    "https://api.github.com/repos/Hochfrequenz/BO4E-Schemas/contents/src/"
                    f"bo4e_schemas/{pkg}?ref=v0.6.1-rc13",
                    text=(Path(__file__).parent / f"test_data/tree_query_response_{pkg}.json").read_text(),
                )

            def mock_get_schema(request: "Request", _: "Context") -> str:
                match = re.search(r"src/bo4e_schemas/(bo|com|enum)/(\w+)\.json", request.path)
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

            main(output=OUTPUT_DIR, target_version="v0.6.1-rc13", config_file=CONFIG_FILE, update_refs=True)

            assert (OUTPUT_DIR / "bo" / "Angebot.json").exists()
            assert (OUTPUT_DIR / "com" / "COM.json").exists()
            assert (OUTPUT_DIR / "enum" / "Typ.json").exists()
            assert Object.model_validate_json((OUTPUT_DIR / "bo" / "Angebot.json").read_text()).title == "Angebot"
