# BO4E-Schema-Tool

![Unittests status badge](https://github.com/Hochfrequenz/BO4E-Schema-Tool/workflows/Unittests/badge.svg)
![Coverage status badge](https://github.com/Hochfrequenz/BO4E-Schema-Tool/workflows/Coverage/badge.svg)
![Linting status badge](https://github.com/Hochfrequenz/BO4E-Schema-Tool/workflows/Linting/badge.svg)
![Black status badge](https://github.com/Hochfrequenz/BO4E-Schema-Tool/workflows/Formatting/badge.svg)

This little command line tool enables you to conveniently pull BO4E-Schemas of arbitrary versions.
Additionally, it supports some features to edit those schemas which can be defined by config values.

## Features

- Pull BO4E-Schemas of arbitrary versions
- Edit schemas:
  - Define required properties
  - Add additional properties (keep in mind that you should avoid this if possible)
  - Maybe future support for basic validation of the schemas

## How to use this Repository on Your Machine

Follow the instructions in our [Python template repository](https://github.com/Hochfrequenz/python_template_repository#how-to-use-this-repository-on-your-machine).

## Contribute

You are very welcome to contribute to this repository by opening a pull request against the main branch.

### GitHub Actions

- Dependabot auto-approve / -merge:
  - If the actor is the Dependabot bot (i.e. on every commit by Dependabot)
    the pull request is automatically approved and auto merge gets activated
    (using squash merge).
