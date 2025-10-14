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
brew install poppler   # ocr (pdf2image)
brew install tesseract # ocr (pytesseract)
```


## Add dependencies

1. Add the new dependency to the pyproject.toml
2. Update the lock file : `poetry lock`
3. Install new dependency : `poetry install`


## Run tests

pytest --no-migrations docia


## Run linter / formatter

ruff format docia; ruff check --fix docia
