"""
Contains the model and a loading function to load the config file
"""
from pathlib import Path

from pydantic import BaseModel

from bost.logger import logger
from bost.schema import SchemaType


class Config(BaseModel):
    """
    The config file model
    """

    required_fields: dict[str, list[str]]
    additional_fields: dict[str, dict[str, SchemaType]]


def load_config(path: Path) -> Config:
    """
    Load the config file
    """
    logger.info("Loading config from %s", path)
    return Config.model_validate_json(path.read_text())
