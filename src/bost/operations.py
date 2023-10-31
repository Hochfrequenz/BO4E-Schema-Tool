import re

from more_itertools import first_true, one

from bost.logger import logger
from bost.schema import AnyOf, Array, Null, Object, Reference, TypeDefinition


def optional_to_required(optional_field: AnyOf) -> TypeDefinition:
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


def add_additional_property(object: Object, additional_property: TypeDefinition, property_name: str) -> Object:
    object.properties[property_name] = additional_property
    return object


REF_REGEX = re.compile(r"src/bo4e_schemas/(bo|com|enum)/(\w+)\.json")


def update_reference(field: Reference, own_module: tuple[str, ...]):
    match = REF_REGEX.search(field.ref)
    if match is None:
        logger.warning(f"Could not parse reference: {field.ref}")
        return

    if own_module[0] == match.group(1):
        field.ref = f"{match.group(2)}.json#"
    else:
        field.ref = f"../{match.group(1)}/{match.group(2)}.json#"


def update_references(obj: TypeDefinition, own_module: tuple[str, ...]):
    def update_or_iter(_object: TypeDefinition):
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
