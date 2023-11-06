from pathlib import Path

from bost.config import load_config
from bost.operations import add_additional_property, optional_to_required, update_reference, update_references
from bost.schema import Object, String


class TestOperations:
    def test_update_reference(self):
        angebot = Object.model_validate_json(
            (Path(__file__).parent / "test_data/bo4e_schemas/bo/Angebot.json").read_text()
        )
        example_ref = angebot.properties["_typ"].any_of[0]
        update_reference(example_ref, ("bo", "Angebot"))

        assert example_ref.ref == "../enum/Typ.json#"

    def test_update_references(self):
        angebot = Object.model_validate_json(
            (Path(__file__).parent / "test_data/bo4e_schemas/bo/Angebot.json").read_text()
        )
        update_references(angebot, ("bo", "Angebot"))

        assert angebot.properties["_typ"].any_of[0].ref == "../enum/Typ.json#"
        assert angebot.properties["angebotsgeber"].any_of[0].ref == "Geschaeftspartner.json#"

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
        add_additional_property(angebot, config.additional_fields["Angebot"]["foo"], "foo")

        assert "foo" in angebot.properties
        assert angebot.properties["foo"] == config.additional_fields["Angebot"]["foo"]
