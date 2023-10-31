"""
This module contains functions that operate on the schema objects.
"""
import re

from more_itertools import first_true

from bost.logger import logger
from bost.schema import AnyOf, Array, Null, Object, Reference, SchemaType


def optional_to_required(optional_field: AnyOf) -> SchemaType:
    """
    Convert an optional field to a required field by removing the Null type.
    If the field is an "AnyOf" field with only one type left (after removing the Null type), the type is reduced to
    the remaining type - i.e. the structure is flattened.
    If the field has a default value of "null", the default value is removed.
    """
    null_type = first_true(optional_field.any_of, pred=lambda item: isinstance(item, Null), default=None)
    assert null_type is not None, f"Expected {optional_field} to contain Null"
    assert "default" in optional_field.__pydantic_fields_set__, f"Expected {optional_field} to have a default"
    optional_field.any_of.remove(null_type)
    if optional_field.default is None and "default" in optional_field.__pydantic_fields_set__:
        optional_field.__pydantic_fields_set__.remove("default")
    if len(optional_field.any_of) == 1:
        # If AnyOf has only one item left, we are reducing the type to that item and copying all relevant data from the
        # AnyOf object
        new_field = optional_field.any_of[0]
        for key in optional_field.__pydantic_fields_set__:
            if hasattr(new_field, key):
                setattr(new_field, key, getattr(optional_field, key))
        return new_field
    return optional_field


def add_additional_property(obj: Object, additional_property: SchemaType, property_name: str) -> Object:
    """
    Add an additional property to an object.
    """
    obj.properties[property_name] = additional_property
    return obj


REF_REGEX = re.compile(r"src/bo4e_schemas/(bo|com|enum)/(\w+)\.json")


def update_reference(field: Reference, own_module: tuple[str, ...]):
    """
    Update a reference to a schema file by replacing a URL reference with a relative path.
    Example of the old reference:
    https://raw.githubusercontent.com/Hochfrequenz/BO4E-Schemas/v0.6.1-rc13/src/bo4e_schemas/enum/AbgabeArt.json
    """
    match = REF_REGEX.search(field.ref)
    if match is None:
        logger.warning("Could not parse reference: %s", field.ref)
        return

    if own_module[0] == match.group(1):
        field.ref = f"{match.group(2)}.json#"
    else:
        field.ref = f"../{match.group(1)}/{match.group(2)}.json#"


def update_references(obj: SchemaType, own_module: tuple[str, ...]):
    """
    Update all references in a schema object. Iterates through the whole structure and calls `update_reference`
    on every Reference object.
    """

    def update_or_iter(_object: SchemaType):
        if isinstance(_object, Object):
            iter_object(_object)
        elif isinstance(_object, AnyOf):
            iter_any_of(_object)
        elif isinstance(_object, Array):
            iter_array(_object)
        elif isinstance(_object, Reference):
            update_reference(_object, own_module)

    def iter_object(_object: Object):
        for prop in _object.properties.values():
            update_or_iter(prop)

    def iter_any_of(_object: AnyOf):
        for item in _object.any_of:
            update_or_iter(item)

    def iter_array(_object: Array):
        update_or_iter(_object.items)

    update_or_iter(obj)
