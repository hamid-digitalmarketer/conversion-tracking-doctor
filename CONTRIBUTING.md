# Contributing to Conversion Tracking Doctor

Thank you for contributing to `conversion-tracking-doctor`! We welcome contributions from web analysts, tag management specialists, data engineers, and Python developers.

---

## Local Development Workflow

1. **Clone the repository**:
   ```bash
   git clone https://github.com/hamid-digitalmarketer/conversion-tracking-doctor.git
   cd conversion-tracking-doctor
   ```

2. **Setup virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

---

## Testing & Quality Assurance

Ensure all linting, type checks, and unit tests pass before opening a pull request:

```bash
# Run unit tests
pytest

# Check code formatting & linting
ruff check .

# Run static type checking
mypy src
```

---

## Adding New Analyzers

To contribute an analyzer:
1. Create a module under `src/conversion_tracking_doctor/analyzers/`.
2. Add the corresponding `IssueCategory` to `src/conversion_tracking_doctor/models.py`.
3. Add comprehensive tests under `tests/test_analyzers.py`.
4. Document the failure mode in `docs/tracking_issues.md`.
