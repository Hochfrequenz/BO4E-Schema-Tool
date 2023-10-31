"""
This module contains classes to model json files which are formatted as "json schema validation":
https://json-schema.org/draft/2019-09/json-schema-validation
Note that this actually supports mainly our BO4E-Schemas, but not necessarily the full json schema validation standard.
"""
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class TypeBase(BaseModel):
    """
    This pydantic class models the base of a type definition in a json schema validation file.
    """

    description: str = ""
    title: str = ""
    type: str = ""
    default: Any = None

    model_config = ConfigDict(populate_by_name=True)


class Object(TypeBase):
    """
    This pydantic class models the root of a json schema validation file.
    """

    additional_properties: Annotated[Literal[True], Field(alias="additionalProperties")]
    properties: dict[str, "TypeDefinition"]
    type: Literal["object"]


class StrEnum(TypeBase):
    """
    This pydantic class models the "enum" keyword in a json schema validation file.
    """

    enum: list[str]
    type: Literal["string"]


class Array(TypeBase):
    """
    This pydantic class models the "array" type in a json schema validation file.
    """

    items: "TypeDefinition"
    type: Literal["array"]


class AnyOf(TypeBase):
    """
    This pydantic class models the "anyOf" keyword in a json schema validation file.
    """

    any_of: Annotated[list["TypeDefinition"], Field(alias="anyOf")]


class String(TypeBase):
    """
    This pydantic class models the "string" type in a json schema validation file.
    """

    type: Literal["string"]
    format: Optional[
        Literal[
            "date-time",
            "date",
            "time",
            "email",
            "hostname",
            "ipv4",
            "ipv6",
            "uri",
            "uri-reference",
            "iri",
            "iri-reference",
            "uuid",
            "json-pointer",
            "relative-json-pointer",
            "regex",
            "idn-email",
            "idn-hostname",
        ]
    ] = None


class Number(TypeBase):
    """
    This pydantic class models the "number" type in a json schema validation file.
    """

    type: Literal["number"]


class Integer(TypeBase):
    """
    This pydantic class models the "integer" type in a json schema validation file.
    """

    type: Literal["integer"]


class Boolean(TypeBase):
    """
    This pydantic class models the "boolean" type in a json schema validation file.
    """

    type: Literal["boolean"]


class Null(TypeBase):
    """
    This pydantic class models the "null" type in a json schema validation file.
    """

    type: Literal["null"]


class Reference(TypeBase):
    """
    This pydantic class models the "$ref" keyword in a json schema validation file.
    """

    ref: Annotated[str, Field(alias="$ref")]


TypeDefinition = Union[Object, StrEnum, Array, AnyOf, String, Number, Integer, Boolean, Null, Reference]
