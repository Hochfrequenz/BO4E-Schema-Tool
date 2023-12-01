"""
Contains the model and a loading function to load the config file
"""
import re
from pathlib import Path
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from bost.logger import logger
from bost.schema import Object, Reference, SchemaType, StrEnum


class AdditionalField(BaseModel):
    """
    A field that is added to the schema
    """

    pattern: str
    field_name: Annotated[str, Field(alias="fieldName")]
    field_def: Annotated[SchemaType, Field(alias="fieldDef")]

    @field_validator("pattern")
    def validate_pattern(cls, pattern):
        try:
            re.compile(pattern)
        except re.error:
            raise ValueError(f"Invalid regular expression: {pattern}")
        return pattern


class AdditionalEnumItem(BaseModel):
    """
    A enum item that is added to the schema
    """

    pattern: str
    items: list[str]

    @field_validator("pattern")
    def validate_pattern(cls, pattern):
        try:
            re.compile(pattern)
        except re.error:
            raise ValueError(f"Invalid regular expression: {pattern}")
        return pattern


class AdditionalModel(BaseModel):
    """
    A model that is added to the schema
    """

    module: Literal["bo", "com", "enum"]
    schema_parsed: Annotated[Object | StrEnum | Reference, Field(alias="schema")]

    @property
    def class_name(self):
        """
        The class name of the schema
        """
        if isinstance(self.schema_parsed, Object):
            return self.schema_parsed.title
        elif isinstance(self.schema_parsed, StrEnum):
            return self.schema_parsed.title
        elif isinstance(self.schema_parsed, Reference):
            return self.schema_parsed.ref.split("/")[-1].split(".")[0]
        else:
            raise ValueError(f"Unknown schema type: {self.schema_parsed}")


class Config(BaseModel):
    """
    The config file model
    """

    required_fields: Annotated[list[str], Field(alias="requiredFields")] = []
    additional_fields: Annotated[list[AdditionalField | Reference], Field(alias="additionalFields")] = []
    additional_enum_items: Annotated[list[AdditionalEnumItem], Field(alias="additionalEnumItems")] = []
    additional_models: Annotated[list[AdditionalModel], Field(alias="additionalModels")] = []

    @field_validator("required_fields")
    def validate_required_field_patterns(cls, required_fields):
        for pattern in required_fields:
            try:
                re.compile(pattern)
            except re.error:
                raise ValueError(f"Invalid regular expression: {pattern}")
        return required_fields


def load_config(path: Path) -> Config:
    """
    Load the config file
    """
    logger.info("Loading config from %s", path)
    config = Config.model_validate_json(path.read_text())

    deletion_list = []
    for additional_field in config.additional_fields:
        if isinstance(additional_field, Reference):
            reference_path = Path(additional_field.ref)
            if not reference_path.is_absolute():
                reference_path = path.parent / reference_path

            additional_fields = TypeAdapter(Union[AdditionalField, list[AdditionalField]]).validate_json(
                reference_path.read_text()
            )
            deletion_list.append(additional_field)
            if isinstance(additional_fields, list):
                config.additional_fields.extend(additional_fields)
            else:
                config.additional_fields.append(additional_fields)
    for additional_field in deletion_list:
        config.additional_fields.remove(additional_field)

    return config
