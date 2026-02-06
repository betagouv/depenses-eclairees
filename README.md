Dépenses éclairées
==================




## Installation

This project uses [Poetry](https://python-poetry.org/) for dependency management.

```bash
# Installer poetry
# https://python-poetry.org/docs/#installing-with-the-official-installer
curl -sSL https://install.python-poetry.org | python3 -

# Installer les dépendances avec Poetry
poetry install
```

Install C libraries


#### macOS

```bash
brew install libmagic  # file detection (python-magic)
brew install tesseract # ocr (pytesseract)
brew install tesseract-lang # install fra language for tesseract
```


## Add dependencies

1. Add the new dependency to the pyproject.toml
2. Update the lock file : `poetry lock`
3. Install new dependency : `poetry install`


## Run tests

```sh
pytest --no-migrations tests

# With coverage
pytest --cov=docia --cov-report html --no-migrations tests
```


## Run linter / formatter

ruff format; ruff check --fix
