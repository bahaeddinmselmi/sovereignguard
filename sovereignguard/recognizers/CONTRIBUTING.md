# Contributing Country Recognizers

SovereignGuard is designed to grow through locale-aware recognizers contributed by the community.

When adding a new country package:
- Create a new folder under the recognizers package using a short locale code.
- Add focused recognizers for the country's identifiers, phone formats, company identifiers, and address patterns.
- Register the recognizer classes in the central registry.
- Add tests with representative valid and invalid examples.
- Keep confidence scoring conservative for ambiguous formats.

Contribution standard:
- High precision first
- No outbound dependencies required for a basic recognizer
- No raw PII in logs or debug output
- Clear docstrings with examples and edge cases
