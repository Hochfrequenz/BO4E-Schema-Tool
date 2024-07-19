"""
Contains the model and a loading function to load the config file
"""

import re
from pathlib import Path
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter, field_validator

from bost.logger import logger
from bost.schema import Reference, SchemaRootObject, SchemaRootStrEnum, SchemaType


class AdditionalField(BaseModel):
    """
    A field that is added to the schema
    """

    pattern: str
    field_name: Annotated[str, Field(alias="fieldName")]
    field_def: Annotated[SchemaType, Field(alias="fieldDef")]

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, pattern):
        """
        Validates if the pattern is compilable as a regular expression
        """
        try:
            re.compile(pattern)
        except re.error as error:
            raise ValueError(f"Invalid regular expression: {pattern}") from error
        return pattern


class AdditionalEnumItem(BaseModel):
    """
    A enum item that is added to the schema
    """

    pattern: str
    items: list[str]

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, pattern):
        """
        Validates if the pattern is compilable as a regular expression
        """
        try:
            re.compile(pattern)
        except re.error as error:
            raise ValueError(f"Invalid regular expression: {pattern}") from error
        return pattern


class AdditionalModel(BaseModel):
    """
    A model that is added to the schema
    """

    module: Literal["bo", "com", "enum"]
    schema_parsed: Annotated[SchemaRootObject | SchemaRootStrEnum | Reference, Field(alias="schema")]


class Config(BaseModel):
    """
    The config file model
    """

    non_nullable_fields: Annotated[list[str], Field(alias="nonNullableFields", default_factory=list)]
    additional_fields: Annotated[
        list[AdditionalField | Reference], Field(alias="additionalFields", default_factory=list)
    ]
    additional_enum_items: Annotated[list[AdditionalEnumItem], Field(alias="additionalEnumItems", default_factory=list)]
    additional_models: Annotated[list[AdditionalModel], Field(alias="additionalModels", default_factory=list)]

    @field_validator("non_nullable_fields")
    @classmethod
    def validate_non_nullable_field_patterns(cls, required_fields):
        """
        Validates if the patterns are compilable as a regular expression
        """
        for pattern in required_fields:
            try:
                re.compile(pattern)
            except re.error as error:
                raise ValueError(f"Invalid regular expression: {pattern}") from error
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

            additional_fields: Union[AdditionalField, list[AdditionalField]] = TypeAdapter(  # type: ignore[assignment]
                Union[AdditionalField, list[AdditionalField]]
            ).validate_json(reference_path.read_text(encoding="utf-8"))
            deletion_list.append(additional_field)
            if isinstance(additional_fields, list):
                config.additional_fields.extend(additional_fields)
            else:
                config.additional_fields.append(additional_fields)
    for additional_field in deletion_list:
        config.additional_fields.remove(additional_field)

    return config
