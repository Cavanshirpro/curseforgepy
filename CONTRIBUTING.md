
# Contributing to CurseForgePy

First of all: thank you for considering contributing to **CurseForgePy**! Your help makes this library better and more reliable for everyone.

This document explains how to contribute (reporting bugs, proposing features, coding, tests, style, etc.), so you know what to expect and how to make your contributions as smooth as possible.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)  
2. [Ways to Contribute](#ways-to-contribute)  
   - Bug Reports / Issues  
   - Feature Requests  
   - Pull Requests  
3. [Development Setup](#development-setup)  
   - Requirements  
   - Installing Locally  
   - Running Tests  
4. [Coding Guidelines](#coding-guidelines)  
   - Style  
   - Type Checking  
   - Linting  
5. [Testing](#testing)  
6. [Pull Request Process](#pull-request-process)  
7. [Release Process (for Maintainers)](#release-process)  
8. [Communicating](#communicating)  
9. [License](#license)  

---

## Code of Conduct

By participating in this project, you agree to abide by the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).  
Please follow these guidelines in all your communications and contributions.

---

## Ways to Contribute

There are several ways you can help:

### 🐞 Bug Reports / Issues  
If you find a bug (or think something is behaving incorrectly), please open an **issue**. Try to provide:
- A **clear title**  
- A detailed **description** of what happened  
- Steps to reproduce the problem  
- A minimal **code snippet** (if applicable)  
- The version of CurseForgePy and your Python version  
- Any traceback / error messages

### ✨ Feature Requests  
If you want to suggest a new feature:
- Check if a similar feature has already been proposed  
- If not, open a new issue  
- Describe **why** the feature would be useful and possible use-cases  
- If you want to implement it yourself, feel free to note that in the issue

### 🔧 Pull Requests  
If you're ready to contribute code:
1. Fork the repository  
2. Create a feature branch: `git checkout -b my-feature`  
3. Make your changes (see [Coding Guidelines](#coding-guidelines))  
4. Add / update **tests** for your changes  
5. Run tests locally (`pytest`)  
6. Run lint / type checks  
7. Commit your work with **clear, descriptive commit messages**  
8. Push to your fork and open a PR  
9. Reference any related issues in the PR description (e.g. “Fixes #123”)

---

## Development Setup

To start contributing locally, you’ll want to set up a development environment.

### Requirements

- Python **3.10+** (as the project supports 3.10 and above)  
- `git`  
- (Optional but recommended) `virtualenv` or `venv`

### Installing Locally

```bash
# Clone the repo
git clone https://github.com/Cavanshirpro/curseforgepy.git
cd curseforgepy

# Create & activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package and dev dependencies
pip install --upgrade pip
pip install -e .             # editable install
pip install -r dev-requirements.txt || pip install pytest mypy ruff build
````

### Running Tests

```bash
pytest -q
```

If there are no tests yet, you can still run `pytest` without failure (or add some tests for your feature / bug fix).

---

## Coding Guidelines

To keep the code consistent, please follow these guidelines.

### Style

* Use **PEP 8** style for Python code
* Use **snake_case** for functions and variables
* Use **PascalCase** for classes
* Line length: try to keep it under **88–100 characters**, but readability comes first

### Type Checking

* Use **type hints** wherever possible
* We use **mypy** for type checking — please make sure your contributions type-check without new errors

### Linting

* We use **ruff** for linting
* Run `ruff check src` before submitting code
* You can optionally auto-format with `ruff format src`
* Don’t commit unnecessary formatting-only changes unless they improve readability

---

## Testing

* Write **unit tests** for any new feature or bug fix
* Use **pytest**
* Aim for good test coverage, particularly for API-related code
* If you mock API calls, try to isolate side-effects so tests stay fast and reliable

---

## Pull Request Process

1. Make sure your branch is based on the latest `main` (or `master`)
2. Run tests and lint locally
3. Push your branch to your fork
4. Open a **Pull Request (PR)** against `main` branch of this repo
5. In the PR description:

   * Explain what you changed and why
   * Link to any related issue(s)
   * Add screenshots or logs if this is a bug fix
6. Be open to feedback — maintainers or other contributors may request changes
7. Once approved, a maintainer will merge your PR

---

## Release Process (for Maintainers)

If you're a maintainer and preparing a release:

1. Make sure all tests pass on CI
2. Update version in `pyproject.toml` (or `setup.py`)
3. Create a **git tag** (e.g. `v1.2.0`)
4. Push tags: `git push origin --tags`
5. Build distributions: `python -m build`
6. Upload to PyPI (or internal artifact repo)
7. Update `CHANGELOG.md` / `RELEASE_NOTES.md` as needed

---

## Communicating

* Use **GitHub Issues** to report bugs or request features
* Use **Pull Requests** to contribute code
* For design discussions: start a **draft Pull Request** or open an issue with a “Discussion” label
* Be respectful and patient — open source is a collaborative effort

---

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (check `LICENSE` file in this repository).
Make sure your contributions are compatible with the project license.

---

Thank you for making **CurseForgePy** better! Your time and effort are very much appreciated. 🙏

