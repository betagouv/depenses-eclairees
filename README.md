Dépenses éclairées
==================




## Installation

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
# Installer uv
# https://docs.astral.sh/uv/getting-started/installation/
curl -LsSf https://astral.sh/uv/install.sh | sh

# Installer les dépendances avec uv
uv sync
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
2. Update the lock file : `uv lock`
3. Install new dependency : `uv sync`

## Run tests

```sh
uv run pytest --no-migrations tests

# With coverage
uv run pytest --cov=docia --cov-report html --no-migrations tests
```


## Run linter / formatter

ruff format; ruff check --fix
