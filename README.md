# BO4E-Schema-Tool

![Unittests status badge](https://github.com/Hochfrequenz/BO4E-Schema-Tool/workflows/Unittests/badge.svg)
![Coverage status badge](https://github.com/Hochfrequenz/BO4E-Schema-Tool/workflows/Coverage/badge.svg)
![Linting status badge](https://github.com/Hochfrequenz/BO4E-Schema-Tool/workflows/Linting/badge.svg)
![Black status badge](https://github.com/Hochfrequenz/BO4E-Schema-Tool/workflows/Formatting/badge.svg)

This little command line tool enables you to conveniently pull BO4E-Schemas of arbitrary versions.
Additionally, it supports some features to edit those schemas which can be defined by config values.

## Features
### Overview

- Pull BO4E-Schemas of arbitrary versions
  - references in `$ref` will be replaced by relative paths
- Edit schemas:
  - Define required properties
  - Add additional properties (keep in mind that you should avoid this if possible)
  - Add additional models (keep in mind that you should avoid this if possible)
  - All features also apply to Enums

## Usage

This tool is a command line tool. You can use it by installing `BO4E-Schema-Tool` via
```bash
pip install BO4E-Schema-Tool
```
and then running:
```bash
> bost --help
Usage: bost [OPTIONS]

  Entry point for the bost command line interface.

Options:
  -o, --output DIRECTORY          Output directory to pull the JSON schemas into
                                  [required]
  -t, --target-version TEXT       Target BO4E version. Defaults to latest.
  -c, --config-file FILE          Path to the config file
  -r, --update-refs / -R, --no-update-refs
                                  Automatically update the references in the
                                  schema files - github URLs are replaced with
                                  relative paths
  -d, --set-default-version / -D, --no-set-default-version
                                  Automatically set or overrides the default
                                  version for '_version' fields with --target-
                                  version. This is especially useful if you want
                                  to define additional models which should
                                  always have the correct version.
  --clear-output                  Clear the output directory before saving the
                                  schemas
  --cache-dir DIRECTORY           Path to the optional cache dir. If not set the
                                  cache is disabled. It will cache the raw
                                  schema files downloaded from github.
  --token TEXT                    A GitHub Access token to authenticate with the
                                  GitHub API. Use this if you have problems with
                                  the rate limit. Alternatively, you can set the
                                  environment variable GITHUB_ACCESS_TOKEN.
  --version                       Show the version and exit.
  --help                          Show this message and exit.
```
Alternatively, you can run the code from your python code by calling `bost.main()` with the same arguments as above.

### Config-File

The config file is a JSON file which can be used to customize the BO4E-Schemas. The config file is optional.

Here is a complex example of a config file:

```json
{
  "required_fields": [
    "bo\\.Angebot\\.angebotspreis",
    "(bo|com)\\.\\w+\\._typ",
    "\\w+\\.\\w+\\._id"
  ],
  "additional_fields": [
    {
        "pattern": "bo\\.Angebot",
        "field_name": "foo",
        "field_def": {
            "type": "number"
        }
    },
    {
      "$ref": "./models/bo/Geschaeftspartner_extension.json"
    }
  ],
  "additional_enum_items": [
    {
      "pattern": "enum\\.BoTyp",
      "items": [
        "Bilanzierung",
        "Dokument"
      ]
    }
  ],
  "additional_models": [
    {
      "module": "bo",
      "schema": {
        "$ref": "models/bo/Bilanzierung.json"
      }
    },
    {
      "module": "bo",
      "schema": {
        "additionalProperties": true,
        "title": "Dokument",
        "type": "object",
        "description": "A generic document reference like for bills, order confirmations and cancellations",
        "properties": {
          "boTyp": {
            "allOf": [
              {
                "$ref": "../enum/BoTyp.json#"
              }
            ],
            "title": "BoTyp",
            "default": "Dokument"
          },
          "erstellungsdatum": {
            "format": "date-time",
            "title": "Erstellungsdatum",
            "type": "string"
          }
        },
        "required": [
          "erstellungsdatum"
        ]
      }
    }
  ]
}
```

The config file can contain the following keys:
- `required_fields`: A list of regex patterns which will be used to define required fields.
  The regex pattern will be (full-)matched to the path of each the field.
  An example of such a path would be `bo.Angebot.angebotspreis`. If the pattern matches, the field will be required.
- `additional_fields`: A list of additional fields which will be added to the schema.
  - `pattern`: A regex pattern which will be used to match the path of the schema (e.g. `bo.Angebot`).
    The field will be added to each schema to which the pattern matches.
  - `field_name`: The name of the field which will be added.
  - `field_def`: The definition of the field which will be added.
- `additional_enum_items`: A list of additional enum items which will be added to the schema.
  - `pattern`: A regex pattern which will be used to match the path of the enum (e.g. `enum.BoTyp`).
    The items will be added to each enum to which the pattern matches.
  - `items`: A list of items which will be added to the enum.
- `additional_models`: A list of additional models which will be added to the schema.
  - `module`: The module to which the schema will be added.
  - `schema`: The schema definition which will be added.

Note: For all config keys (except `required_fields`), you can alternatively use the `"$ref"` key to reference to a file.
This is useful to keep the config file small and to reuse definitions.
If the path is relative it will be applied to the path of the directory where the config file is stored in.
But, you can define absolute paths if you want.

As a little extra feature for `additional_fields`: If you want to define multiple fields in one external file,
you can define a list of fields instead of a single field. The reference in the `"$ref"` key is the same.

Example of `./models/bo/Geschaeftspartner_extension.json`:
```json
[
  {
    "pattern": "bo\\.Geschaeftspartner",
    "field_name": "foo",
    "field_def": {
      "type": "number"
    }
  },
  {
    "pattern": "bo\\.Geschaeftspartner",
    "field_name": "bar",
    "field_def": {
      "type": "string"
    }
  }
]
```

### Update References

The schemas from the repository `BO4E-Schemas` contain online references to each other
(e.g. `"$ref": "https://raw.githubusercontent.com/BO4E/BO4E-Schemas/v202401.0.1/src/bo4e_schemas/bo/Angebot.json#"`).
This is not very convenient if you want to work with the schemas offline. And if you need to edit the schemas using
the config file, this would be a problem.

To solve this problem, you can use the `--update-refs` flag. This will replace the online references with
relative paths. It will also try to replace references introduced by the config file. But note that if the
software can't match the reference to the pattern of an online reference, it will not replace it but instead
log a warning.

### Set Default Version

All BO4E-Schemas contain a field `_version` which defines the used BO4E version. All schemas which are pulled
from the repository `BO4E-Schemas` will have the `_version` fields default value set to the respective version.
But if you introduce additional models, it might be a bit cumbersome to set the `_version` field to the correct
version each time you upgrade the BO4E version.

To solve this problem, you can use the `--set-default-version` flag. It will automatically set or override the default
value for `_version` fields with the `--target-version`.

### GitHub Access Token

If you have problems with the rate limit of the GitHub API, you can specify a GitHub Access token with the
`--token` flag. For more information, please refer to the
[GitHub documentation](https://docs.github.com/de/rest/using-the-rest-api/rate-limits-for-the-rest-api).

If you don't want to specify the token in the parameter list, you can also set the environment variable
`GITHUB_ACCESS_TOKEN`.

### Clear Output

If you want to pull the schemas into a directory which already contains schemas, you can use the `--clear-output` flag.
This will clear the output directory entirely before saving the schemas. This is useful if a new version of the schemas
doesn't contain some schemas anymore which were present in the previous version.

### Cache

If you specify a cache directory with the `--cache-dir` flag, the tool will cache the raw schema files downloaded from
GitHub. This cache is version specific and will be overridden if you want to download another version.
This is useful if you want to execute the tool multiple times with the same version. It will save you some time during
development.

## How to use this Repository on Your Machine

Follow the instructions in our [Python template repository](https://github.com/Hochfrequenz/python_template_repository#how-to-use-this-repository-on-your-machine).

## Contribute

You are very welcome to contribute to this repository by opening a pull request against the main branch.

### GitHub Actions

- Dependabot auto-approve / -merge:
  - If the actor is the Dependabot bot (i.e. on every commit by Dependabot)
    the pull request is automatically approved and auto merge gets activated
    (using squash merge).
