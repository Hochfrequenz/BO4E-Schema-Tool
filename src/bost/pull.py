"""
Contains functions to pull the BO4E-Schemas from GitHub.
"""
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import requests
from pydantic import BaseModel, TypeAdapter, computed_field
from requests import Response

from bost.logger import logger
from bost.schema import SchemaType

OWNER = "Hochfrequenz"
REPO = "BO4E-Schemas"
TIMEOUT = 10


class SchemaMetadata(BaseModel):
    """
    Metadata about a schema file
    """

    _schema_response: Response | None = None
    _schema: SchemaType | None = None
    class_name: str
    download_url: str
    module_path: tuple[str, ...]
    "e.g. ('bo', 'Angebot')"
    file_path: Path

    @computed_field
    @property
    def module_name(self) -> str:
        """
        Joined module path. E.g. "bo.Angebot"
        """
        return ".".join(self.module_path)

    @property
    def schema_parsed(self) -> SchemaType:
        """
        The parsed schema. Downloads the schema from GitHub if needed.
        """
        if self._schema is None:
            self._schema_response = self._download_schema()
            self._schema = TypeAdapter(SchemaType).validate_json(self._schema_response.text)
        return self._schema

    def _download_schema(self) -> Response:
        """
        Download the schema from GitHub. Returns the response object.
        """
        response = requests.get(self.download_url, timeout=TIMEOUT)
        if response.status_code != 200:
            raise ValueError(f"Could not download schema from {self.download_url}: {response.text}")
        logger.info("Downloaded %s", self.download_url)
        return response

    def save(self):
        """
        Save the parsed schema to the file defined by `file_path`. Creates parent directories if needed.
        """
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(self.schema_parsed.model_dump_json(indent=2, exclude_unset=True, by_alias=True))

    def __str__(self):
        return self.module_name


@lru_cache(maxsize=None)
def _github_tree_query(pkg: str, version: str) -> Response:
    """
    Query the github tree api for a specific package and version.
    """
    return requests.get(
        f"https://api.github.com/repos/{OWNER}/{REPO}/contents/src/bo4e_schemas/{pkg}?ref={version}", timeout=TIMEOUT
    )


@lru_cache(maxsize=1)
def resolve_latest_version() -> str:
    """
    Resolve the latest BO4E version from the github api.
    """
    response = requests.get(f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest", timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()["tag_name"]


SCHEMA_CACHE: dict[tuple[str, ...], SchemaMetadata] = {}


def schema_iterator(version: str, output: Path) -> Iterable[SchemaMetadata]:
    """
    Get all files from the BO4E-Schemas repository.
    This generator function yields SchemaMetadata objects containing various information about the schema.
    """
    for pkg in ("bo", "com", "enum"):
        response = _github_tree_query(pkg, version)
        for file in response.json():
            if not file["name"].endswith(".json"):
                continue
            relative_path = Path(file["path"]).relative_to("src/bo4e_schemas")
            module_path = (*relative_path.parent.parts, relative_path.stem)
            if module_path not in SCHEMA_CACHE:
                SCHEMA_CACHE[module_path] = SchemaMetadata(
                    class_name=relative_path.stem,
                    download_url=file["download_url"],
                    module_path=module_path,
                    file_path=output / relative_path,
                )
            yield SCHEMA_CACHE[module_path]
