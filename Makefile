.PHONY: demo test lint

# Run the sample dataset through the pipeline and open the report.
demo:
	python3 -m venv .venv && . .venv/bin/activate && pip install -e .
	dqs run --source data/sample.csv --out reports_demo --fix --viz on
	@echo "Open reports_demo directory for the generated HTML report."

# Run unit tests via pytest.
test:
	pytest -q

# Lint the codebase using ruff.
lint:
	ruff .