# Contributing to Data Quality Sentry

Thank you for taking the time to contribute! We welcome bug reports, feature requests and pull requests. The guidelines below will help you get set up and ensure a smooth development experience.

## Getting started

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/your-username/data-quality-sentry2.git
   cd data-quality-sentry2
   ```

2. **Create a virtual environment and install the project**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   pip install pytest ruff pre-commit
   ```

3. **Install pre‑commit hooks** to automatically format your code and catch common issues before committing:
   ```bash
   pre-commit install
   ```

## Running the pipeline locally

Use the `dqs` CLI (installed from `pyproject.toml`) to run the checks and generate an HTML report:

```bash
dqs run --source data/sample.csv --out reports_demo --viz on --fix
```

See the [README](README.md) for additional options. The report files are written into the `reports_demo/` directory.

## Running tests and linting

- Run the unit tests:
  ```bash
  pytest -q
  ```

- Lint the codebase with [ruff](https://github.com/astral-sh/ruff):
  ```bash
  ruff .
  ```

Our GitHub Actions CI runs both linting and tests. Make sure your contribution passes locally before opening a pull request.

## Adding new checks or fixers

Checks are defined in YAML under `checks/rules.yml`. To add a new rule type:

1. Update `checks/run_checks.py` with logic to evaluate the new rule.
2. Update `summaries/write_summary.py` if you need to visualise the new rule type differently.
3. Create a unit test under `tests/` verifying the rule on a small synthetic dataset.
4. Document the rule in the README.

Fixers live in `checks/fixers.py`. To add a new fixer:

1. Implement a function that takes a DataFrame and modifies values appropriately.
2. Update the pipeline in `checks/run_checks.py` to call the fixer when its corresponding rule is specified.
3. Add a test covering both the detection and the fix.

## Submitting a pull request

1. Make sure your fork is up to date with `main`.
2. Create a new branch (`git checkout -b my-feature`).
3. Commit your changes. Use clear, descriptive commit messages.
4. Push to your fork and open a pull request against the upstream `main` branch.
5. In your PR description, explain **why** the change is needed and link any relevant issues.

We will review your changes as soon as possible. Thank you for helping to improve Data Quality Sentry!