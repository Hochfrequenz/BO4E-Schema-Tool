from pathlib import Path

from pydantic import BaseModel

from bost.logger import logger
from bost.schema import TypeDefinition


class Config(BaseModel):
    required_fields: dict[str, list[str]]
    additional_fields: dict[str, dict[str, TypeDefinition]]


def load_config(path: Path) -> Config:
    logger.info("Loading config from %s", path)
    return Config.model_validate_json(path.read_text())
