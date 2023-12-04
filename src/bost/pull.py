"""
Contains functions to pull the BO4E-Schemas from GitHub.
"""
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Union

import requests
from pydantic import BaseModel, TypeAdapter, ValidationError
from requests import Response

from bost.config import Config
from bost.logger import logger
from bost.schema import Object, Reference, SchemaRootType, StrEnum

OWNER = "Hochfrequenz"
REPO = "BO4E-Schemas"
TIMEOUT = 10  # in seconds


class SchemaMetadata(BaseModel):
    """
    Metadata about a schema file
    """

    _schema_response: Response | None = None
    _schema: SchemaRootType | None = None
    class_name: str
    download_url: str
    module_path: tuple[str, ...]
    "e.g. ('bo', 'Angebot')"
    file_path: Path

    @property
    def module_name(self) -> str:
        """
        Joined module path. E.g. "bo.Angebot"
        """
        return ".".join(self.module_path)

    @property
    def schema_parsed(self) -> SchemaRootType:
        """
        The parsed schema. Downloads the schema from GitHub if needed.
        """
        if self._schema is None:
            self._schema_response = self._download_schema()
            self._schema = TypeAdapter(SchemaRootType).validate_json(  # type: ignore[assignment]
                self._schema_response.text
            )
        assert self._schema is not None
        return self._schema

    @schema_parsed.setter
    def schema_parsed(self, value: SchemaRootType):
        self._schema = value

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

    def field_paths(self) -> Iterable[tuple[str, str]]:
        """
        Get all field paths of the schema.
        """
        if not isinstance(self.schema_parsed, Object):
            return
        for field_name in self.schema_parsed.properties:
            yield ".".join((self.module_name, field_name)), field_name

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


def schema_iterator(version: str, output: Path) -> Iterable[tuple[str, SchemaMetadata]]:
    """
    Get all files from the BO4E-Schemas repository.
    This generator function yields tuples of class name and SchemaMetadata objects containing various information about
    the schema.
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
            yield SCHEMA_CACHE[module_path].class_name, SCHEMA_CACHE[module_path]


def load_schema(path: Path) -> Object | StrEnum:
    """
    Load a schema from a file.
    """
    try:
        return TypeAdapter(Union[Object, StrEnum]).validate_json(path.read_text())  # type: ignore[return-value]
    except ValidationError as error:
        logger.error("Could not load schema from %s:", path, exc_info=error)
        raise


def additional_schema_iterator(
    config: Config | None, config_path: Path | None, output: Path
) -> Iterable[tuple[str, SchemaMetadata]]:
    """
    Get all additional models from the config file.
    """
    if config is None:
        return
    assert config_path is not None, "Config path must be set if config is set"

    for additional_model in config.additional_models:
        if isinstance(additional_model.schema_parsed, Reference):
            reference_path = Path(additional_model.schema_parsed.ref)
            if not reference_path.is_absolute():
                reference_path = config_path.parent / reference_path
            schema_parsed = load_schema(reference_path)
        else:
            schema_parsed = additional_model.schema_parsed

        if schema_parsed.title == "":
            raise ValueError("Config Error: Title is required for additional models to determine the class name")

        schema_metadata = SchemaMetadata(
            class_name=schema_parsed.title,
            download_url="",
            module_path=(additional_model.module, schema_parsed.title),
            file_path=output / f"{additional_model.module}/{schema_parsed.title}.json",
        )
        schema_metadata.schema_parsed = schema_parsed
        yield schema_metadata.class_name, schema_metadata
