"""
This module contains functions that operate on the schema objects.
"""

import re

from more_itertools import first_true

from bost.logger import logger
from bost.pull import OWNER, REPO, SchemaMetadata
from bost.schema import AllOf, AnyOf, Array, Null, Object, Reference, SchemaRootObject, SchemaType, StrEnum


def field_to_non_nullable(schema_parsed: SchemaRootObject, field_name: str):
    """
    Convert a field which can be null to a field which can't, by removing the Null type.
    If the field is an "AnyOf" field with only one type left (after removing the Null type), the type is reduced to
    the remaining type - i.e. the structure is flattened.
    If the field has a default value of "null", the default value is removed.
    """
    field_with_null_type = schema_parsed.properties[field_name]
    assert isinstance(
        field_with_null_type, AnyOf
    ), f"Internal error: Expected field to be of type AnyOf but got {type(field_with_null_type)}"
    null_type = first_true(field_with_null_type.any_of, pred=lambda item: isinstance(item, Null), default=None)
    assert null_type is not None, f"Expected {field_with_null_type} to contain Null"
    assert (
        "default" in field_with_null_type.__pydantic_fields_set__
    ), f"Expected {field_with_null_type} to have a default"
    field_with_null_type.any_of.remove(null_type)
    if field_with_null_type.default is None and "default" in field_with_null_type.__pydantic_fields_set__:
        field_with_null_type.__pydantic_fields_set__.remove("default")
        if field_name not in schema_parsed.required:
            schema_parsed.__pydantic_fields_set__.add("required")
            schema_parsed.required.append(field_name)
    if len(field_with_null_type.any_of) == 1:
        # If AnyOf has only one item left, we are reducing the type to that item and copying all relevant data from the
        # AnyOf object
        new_field = field_with_null_type.any_of[0]
        for key in field_with_null_type.__pydantic_fields_set__:
            if hasattr(new_field, key):
                setattr(new_field, key, getattr(field_with_null_type, key))
        schema_parsed.properties[field_name] = new_field


def add_additional_property(obj: Object, additional_property: SchemaType, property_name: str) -> Object:
    """
    Add an additional property to an object.
    """
    obj.properties[property_name] = additional_property
    return obj


def add_additional_enum_items(obj: StrEnum, additional_items: list[str]) -> StrEnum:
    """
    Add an additional item to an enum.
    """
    obj.enum.extend(additional_items)
    return obj


# GH_VERSION_REGEX = re.compile(r"^v(\d+\.\d+\.\d+)(-rc\d+)?$")
REF_ONLINE_REGEX = re.compile(
    rf"^https://raw\.githubusercontent\.com/(?:{OWNER.upper()}|{OWNER.lower()}|Hochfrequenz)/{REPO}/"
    r"(?P<version>v\d+\.\d+\.\d+(?:-rc\d+)?)/"
    r"src/bo4e_schemas/(?P<sub_path>(?:\w+/)*)(?P<model>\w+)\.json#?$"
)
# e.g. https://raw.githubusercontent.com/BO4E/BO4E-Schemas/v202401.1.0-rc1/src/bo4e_schemas/bo/Angebot.json
REF_DEFS_REGEX = re.compile(r"^#/\$(?:defs|definitions)/(?P<model>\w+)$")


def update_reference(field: Reference, schema: SchemaMetadata, schemas: dict[str, SchemaMetadata], version: str):
    """
    Update a reference to a schema file by replacing a URL reference or reference to definitions with a relative path
    to the schema file. If using references to definitions, the schema file must be in the namespace.
    Example of online reference:
    https://raw.githubusercontent.com/BO4E/BO4E-Schemas/v202401.1.0-rc1/src/bo4e_schemas/bo/Angebot.json
    Example of reference to definitions:
    #/$defs/Angebot
    """
    match = REF_ONLINE_REGEX.search(field.ref)
    if match is not None:
        logger.debug("Matched online reference: %s", field.ref)
        if match.group("version") != version:
            raise ValueError(
                "Version mismatch: References across different versions of BO4E are not allowed. "
                f"{match.group('version')} does not match {version} for reference {field.ref}"
            )
        if match.group("sub_path") is not None:
            reference_module_path = [*match.group("sub_path").split("/")[:-1], match.group("model")]
        else:
            reference_module_path = [match.group("model")]
    else:
        match = REF_DEFS_REGEX.search(field.ref)
        if match is not None:
            logger.debug("Matched reference to definitions: %s", field.ref)
            if match.group("model") not in schemas:
                raise ValueError(
                    f"Could not find schema for reference {field.ref} in namespace "
                    f"{set(schema_el.module_path for schema_el in schemas.values())}"
                )
            reference_module_path = list(schemas[match.group("model")].module_path)
        else:
            logger.info("Reference unchanged. Could not parse reference: %s", field.ref)
            return

    relative_ref = "#"
    for ind, (part, own_part) in enumerate(zip(reference_module_path, schema.module_path)):
        if part != own_part:
            relative_ref = (
                "../" * (len(schema.module_path) - ind - 1) + "/".join(reference_module_path[ind:]) + ".json#"
            )
            break

    logger.debug("Updated reference %s to: %s", field.ref, relative_ref)
    field.ref = relative_ref


def update_references(schema: SchemaMetadata, schemas: dict[str, SchemaMetadata], version: str):
    """
    Update all references in a schema object. Iterates through the whole structure and calls `update_reference`
    on every Reference object.
    """

    def update_or_iter(_object: SchemaType):
        if isinstance(_object, Object):
            iter_object(_object)
        elif isinstance(_object, AnyOf):
            iter_any_of(_object)
        elif isinstance(_object, AllOf):
            iter_all_of(_object)
        elif isinstance(_object, Array):
            iter_array(_object)
        elif isinstance(_object, Reference):
            update_reference(_object, schema, schemas, version)

    def iter_object(_object: Object):
        for prop in _object.properties.values():
            update_or_iter(prop)

    def iter_any_of(_object: AnyOf):
        for item in _object.any_of:
            update_or_iter(item)

    def iter_all_of(_object: AllOf):
        for item in _object.all_of:
            update_or_iter(item)

    def iter_array(_object: Array):
        update_or_iter(_object.items)

    update_or_iter(schema.schema_parsed)
