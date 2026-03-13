# Contributing to SovereignGuard

Thank you for your interest in contributing to SovereignGuard! This guide covers
the development workflow for all aspects of the project.

## Getting Started

### Prerequisites
- Python 3.11+
- pip or Poetry

### Setup

```bash
git clone https://github.com/your-org/sovereignguard.git
cd sovereignguard
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Running Tests

```bash
# All tests
make test

# With coverage
make test-cov

# Specific test file
pytest tests/test_masker.py -v
```

### Running the Gateway Locally

```bash
# Create a .env file from the example
cp .env.example .env

# Edit .env with your API key
# Then start the server
make dev
```

## Code Style

- Follow PEP 8
- Use type hints for function signatures
- Keep functions focused and under 50 lines
- Use descriptive variable names

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Add tests for new functionality
5. Run the full test suite: `make test`
6. Commit with a descriptive message
7. Push and open a Pull Request

### PR Requirements

- All tests must pass
- New code should have test coverage
- Security-sensitive changes need extra review
- Update `CHANGELOG.md` for user-facing changes

## Adding a New Recognizer

See [docs/adding-recognizers.md](docs/adding-recognizers.md) for the full guide.

Quick summary:
1. Create a new file in `sovereignguard/recognizers/{locale}/`
2. Inherit from `BaseRecognizer`
3. Implement `entity_types`, `locale`, and `analyze()`
4. Register in `sovereignguard/recognizers/registry.py`
5. Add tests in `tests/test_recognizers.py`

## Adding a New LLM Provider

1. Create an adapter class in `sovereignguard/proxy/providers.py`
2. Inherit from `BaseProviderAdapter`
3. Register in `get_provider_adapter()`
4. Add tests in `tests/test_providers.py`

## Security

- **Never log actual PII values** — only token references and entity types
- **Never disable authentication** in production
- Review [SECURITY.md](SECURITY.md) before making security-related changes
- Report vulnerabilities privately — see SECURITY.md for details

## License

By contributing, you agree that your contributions will be licensed under
the Apache License 2.0.
