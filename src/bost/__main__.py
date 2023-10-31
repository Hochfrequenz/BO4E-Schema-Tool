from pathlib import Path

import click

from bost.config import load_config
from bost.logger import logger
from bost.operations import add_additional_property, optional_to_required, update_references
from bost.pull import resolve_latest_version, schema_iterator
from bost.schema import Object


@click.command()
@click.option(
    "--output",
    "-o",
    help="Output directory to pull the JSON schemas into",
    type=click.Path(file_okay=False, path_type=Path),
    required=True,
)
@click.option(
    "--target-version",
    "-v",
    help="Target BO4E version. Defaults to latest.",
    type=str,
    default="latest",
)
@click.option(
    "--github-token",
    "-t",
    help="The github token to use for the release workflow",
    type=str,
    required=True,
    envvar="GITHUB_TOKEN",
)
@click.option(
    "--config-file",
    "-c",
    help="Path to the config file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
    default=None,
)
@click.option(
    "--update-refs",
    "-r",
    help="Automatically update the references in the schema files",
    is_flag=True,
    default=True,
)
def main_command_line(*args, **kwargs) -> None:
    main(*args, **kwargs)


def main(output: Path, target_version: str, github_token: str, config_file: Path | None, update_refs: bool) -> None:
    if config_file is not None:
        config = load_config(config_file)
    else:
        config = None

    if target_version == "latest":
        target_version = resolve_latest_version(github_token)

    output.mkdir(parents=True, exist_ok=True)
    for schema in schema_iterator(target_version, output):
        if config is not None:
            if schema.class_name in config.required_fields:
                if not isinstance(schema.schema_parsed, Object):
                    raise ValueError(f"Config Error: {schema.class_name} is not an object")
                for field in config.required_fields[schema.class_name]:
                    if field not in schema.schema_parsed.properties:
                        raise ValueError(f"Config Error: Field {field} not found in {schema.class_name}")
                    schema.schema_parsed.properties[field] = optional_to_required(
                        schema.schema_parsed.properties[field]
                    )
            if schema.class_name in config.additional_properties:
                if not isinstance(schema.schema_parsed, Object):
                    raise ValueError(f"Config Error: {schema.class_name} is not an object")
                for field_name, field in config.additional_properties[schema.class_name].items():
                    if field in schema.schema_parsed.properties:
                        raise ValueError(f"Config Error: Field {field} already existent in {schema.class_name}")
                    add_additional_property(schema.schema_parsed, field, field_name)
        if update_refs:
            update_references(schema.schema_parsed, schema.module_path)
        schema.save()
        logger.info("Processed %s", schema)


if __name__ == "__main__":
    main_command_line()
