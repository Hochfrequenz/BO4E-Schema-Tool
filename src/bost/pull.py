"""
Contains functions to pull the BO4E-Schemas from GitHub.
"""
from functools import lru_cache
from pathlib import Path
from typing import Annotated, ItemsView, Iterable, KeysView, Union, ValuesView

import requests
from github import Github
from pydantic import BaseModel, Field, RootModel, TypeAdapter, ValidationError
from requests import Response

from bost.cache import CACHE_FILE_NAME, CacheData, get_cached_file, get_cached_file_tree, save_cache
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

    _schema: SchemaRootType | None = None
    class_name: str
    download_url: str
    module_path: tuple[str, ...]
    """ e.g. ('bo', 'Angebot') or ('ZusatzAttribut',)"""
    file_path: Path
    cached_path: Path | None

    @property
    def module_name(self) -> str:
        """
        Joined module path. E.g. "bo.Angebot" or "ZusatzAttribut"
        """
        return ".".join(self.module_path)

    @property
    def schema_parsed(self) -> SchemaRootType:
        """
        The parsed schema. Downloads the schema from GitHub if needed.
        """
        if self._schema is None:
            if self.cached_path is not None and self.cached_path.exists():
                self._schema = TypeAdapter(SchemaRootType).validate_json(  # type: ignore[assignment]
                    self.cached_path.read_text()
                )
                logger.info("Loaded %s from cache", self.cached_path)
            else:
                schema_response = self._download_schema()
                self._schema = TypeAdapter(SchemaRootType).validate_json(  # type: ignore[assignment]
                    schema_response.text
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
        if self.cached_path is not None:
            self.cached_path.parent.mkdir(parents=True, exist_ok=True)
            self.cached_path.write_text(response.text)
            logger.debug("Cached %s", self.cached_path)
        return response

    def save(self):
        """
        Save the parsed schema to the file defined by `file_path`. Creates parent directories if needed.
        """
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text(
            self.schema_parsed.model_dump_json(indent=2, exclude_unset=True, by_alias=True), encoding="utf-8"
        )

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


class SchemaInFileTree(BaseModel):
    """
    A schema in the file tree returned by the GitHub API. Only contains the relevant information.
    """

    name: str
    path: str
    module_path: tuple[str, ...]
    download_url: str


class SchemaTree(RootModel):
    """
    This model represents a file tree of `SchemaInFileTree` objects.
    You can use path indices to access the tree. The class will handle those paths and splits them
    into separate indices.
    """

    root: Annotated[dict[str, Union["SchemaTree", SchemaInFileTree]], Field(default_factory=dict)]

    @staticmethod
    def resolve_path(path: str) -> list[str]:
        """
        Splits a path into its parts.
        """
        return path.split("/")

    def __setitem__(self, key, value):
        parts = self.resolve_path(key)
        current = self.root
        for part in parts[:-1]:
            try:
                current = current[part]
            except KeyError:
                current[part] = self.__class__()
                current = current[part]
        current[parts[-1]] = value

    def __getitem__(self, key):
        parts = self.resolve_path(key)
        current = self.root
        for part in parts:
            try:
                current = current[part]
            except KeyError:
                current[part] = self.__class__()
                current = current[part]
        return current

    def __contains__(self, path):
        parts = self.resolve_path(path)
        current = self.root
        for part in parts:
            if part not in current:
                return False
            current = current[part]
        return True

    def __iter__(self):
        return iter(self.root)

    def __len__(self):
        return len(self.root)

    def keys(self) -> KeysView[str]:
        """Get all keys of the root."""
        return self.root.keys()

    def values(self) -> ValuesView[Union["SchemaTree", SchemaInFileTree]]:
        """Get all values of the root."""
        return self.root.values()

    def items(self) -> ItemsView[str, Union["SchemaTree", SchemaInFileTree]]:
        """Get all items of the root."""
        return self.root.items()

    def all_files(self) -> Iterable[SchemaInFileTree]:
        """Get all files in the schema tree."""
        for value in self.values():
            if isinstance(value, SchemaInFileTree):
                yield value
            else:
                yield from value.all_files()


SchemaTree.model_rebuild()
CacheData.model_rebuild()


@lru_cache(maxsize=None)
def _github_tree_query(version: str) -> SchemaTree:
    """
    Query the github tree api for a specific package and version.
    """
    repo = Github().get_repo(f"{OWNER}/{REPO}")
    release = repo.get_release(version)
    tree = repo.get_git_tree(release.target_commitish, recursive=True)
    schema_tree = SchemaTree({})

    for tree_element in tree.tree:
        if not tree_element.path.startswith("src/bo4e_schemas"):
            continue
        if tree_element.path.endswith(".json"):
            # We could send a `get_contents` request for each file, but instead we send a request
            # for the respective parent directory. This way we only need one request per directory.
            continue
        contents = repo.get_contents(tree_element.path, ref=release.target_commitish)
        if not isinstance(contents, list):
            contents = [contents]
        for file_or_dir in contents:
            if file_or_dir.name.endswith(".json"):
                relative_path = Path(file_or_dir.path).relative_to("src/bo4e_schemas").with_suffix("")
                schema = SchemaInFileTree(
                    name=file_or_dir.name,
                    path=file_or_dir.path,
                    module_path=relative_path.parts,
                    download_url=file_or_dir.download_url,
                )
                schema_tree[str(relative_path)] = schema
    return schema_tree


@lru_cache(maxsize=1)
def resolve_latest_version() -> str:
    """
    Resolve the latest BO4E version from the github api.
    """
    repo = Github().get_repo(f"{OWNER}/{REPO}")
    latest_release = repo.get_latest_release().title
    return latest_release


def get_schema_list(version: str, cache_dir: Path | None) -> SchemaTree:
    """
    Get all files metadata from the BO4E-Schemas repository or from cache.
    """
    if cache_dir is not None:
        possible_schemas = get_cached_file_tree(cache_dir)
        if possible_schemas is not None:
            return possible_schemas

    schemas = _github_tree_query(version)
    if cache_dir is not None:
        save_cache(cache_dir / CACHE_FILE_NAME, version=version, file_tree=schemas)

    return schemas


SCHEMA_CACHE: dict[tuple[str, ...], SchemaMetadata] = {}


def schema_iterator(version: str, output: Path, cache_dir: Path | None) -> Iterable[tuple[str, SchemaMetadata]]:
    """
    Get all files from the BO4E-Schemas repository.
    This generator function yields tuples of class name and SchemaMetadata objects containing various information about
    the schema.
    """
    schemas = get_schema_list(version, cache_dir)
    for file in schemas.all_files():
        if not file.name.endswith(".json"):
            continue
        relative_path = Path(file.path).relative_to("src/bo4e_schemas")
        module_path = file.module_path
        if module_path not in SCHEMA_CACHE:
            SCHEMA_CACHE[module_path] = SchemaMetadata(
                class_name=relative_path.stem,
                download_url=file.download_url,
                module_path=module_path,
                file_path=output / relative_path,
                cached_path=get_cached_file(relative_path, cache_dir),
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
            cached_path=None,
        )
        schema_metadata.schema_parsed = schema_parsed
        yield schema_metadata.class_name, schema_metadata
