from pathlib import Path
from unittest.mock import Mock

from more_itertools import one

from bost.config import AdditionalField, load_config
from bost.operations import add_additional_property, optional_to_required, update_reference, update_references
from bost.pull import SchemaMetadata
from bost.schema import Object, Reference, SchemaRootObject, String


class TestOperations:
    def test_update_reference(self):
        angebot_metadata = Mock(SchemaMetadata)
        angebot_metadata.module_path = ("bo", "Angebot")
        angebot = Object.model_validate_json(
            (Path(__file__).parent / "test_data/bo4e_schemas/bo/Angebot.json").read_text()
        )
        example_ref = angebot.properties["_typ"].any_of[0]
        update_reference(example_ref, angebot_metadata, {}, "v0.6.1-rc13")

        assert example_ref.ref == "../enum/Typ.json#"

    def test_update_references(self):
        angebot_metadata = Mock(SchemaMetadata)
        angebot_metadata.module_path = ("bo", "Angebot")
        angebot = Object.model_validate_json(
            (Path(__file__).parent / "test_data/bo4e_schemas/bo/Angebot.json").read_text()
        )
        angebot_metadata.schema_parsed = angebot
        update_references(angebot_metadata, {}, "v0.6.1-rc13")

        assert angebot.properties["_typ"].any_of[0].ref == "../enum/Typ.json#"
        assert angebot.properties["angebotsgeber"].any_of[0].ref == "Geschaeftspartner.json#"

    def test_update_reference_with_definitions(self):
        foo_schema = SchemaRootObject(properties={"bar": String(type="string")}, type="object")
        bar_schema = SchemaRootObject(
            defs={"Foo": Object(properties={"bar": String(type="string")}, type="object")},
            properties={"foo": Reference(ref="#/$defs/Foo")},
            type="object",
        )
        foo_metadata = Mock(SchemaMetadata)
        foo_metadata.module_path = ("com", "Foo")
        foo_metadata.schema_parsed = foo_schema
        bar_metadata = Mock(SchemaMetadata)
        bar_metadata.module_path = ("bo", "Bar")
        bar_metadata.schema_parsed = bar_schema

        update_references(bar_metadata, {"Foo": foo_metadata, "Bar": bar_metadata}, "")

        assert bar_schema.properties["foo"].ref == "../com/Foo.json#"

    def test_optional_to_required_with_default(self):
        angebot = Object.model_validate_json(
            (Path(__file__).parent / "test_data/bo4e_schemas/bo/Angebot.json").read_text()
        )
        example_field = angebot.properties["_version"]
        new_field = optional_to_required(example_field)

        assert isinstance(new_field, String)
        assert new_field.default == "0.6.1rc13"
        assert example_field.title == new_field.title

    def test_optional_to_required_without_default(self):
        angebot = Object.model_validate_json(
            (Path(__file__).parent / "test_data/bo4e_schemas/bo/Angebot.json").read_text()
        )
        example_field = angebot.properties["angebotsdatum"]
        new_field = optional_to_required(example_field)

        assert isinstance(new_field, String)
        assert new_field.default is None
        assert "default" not in new_field.__pydantic_fields_set__
        assert example_field.title == new_field.title
        assert new_field.format == "date-time"

    def test_add_additional_property(self):
        angebot = Object.model_validate_json(
            (Path(__file__).parent / "test_data/bo4e_schemas/bo/Angebot.json").read_text()
        )
        config = load_config(Path(__file__).parent / "config_test.json")
        angebot_field_foo = one(
            additional_field
            for additional_field in config.additional_fields
            if isinstance(additional_field, AdditionalField) and additional_field.field_name == "foo"
        )
        add_additional_property(angebot, angebot_field_foo.field_def, angebot_field_foo.field_name)

        assert "foo" in angebot.properties
        assert angebot.properties["foo"] == angebot_field_foo.field_def
