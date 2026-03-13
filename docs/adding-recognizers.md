# Adding Recognizers

Recognizers are the core extension point of SovereignGuard. They define how the gateway detects PII before tokenization.

This guide explains the structure, expectations, and workflow for adding a new recognizer safely.

## Recognizer Contract

All recognizers inherit from `BaseRecognizer` and must provide:

1. `entity_types`: the PII classes returned by the recognizer
2. `locale`: the recognizer locale such as `universal`, `tn`, `fr`, or `ma`
3. `priority`: ordering hint for registry execution
4. `analyze(text)`: returns a list of `RecognizerResult`

Each `RecognizerResult` must include:

- `entity_type`
- `start`
- `end`
- `score`
- `text`
- `locale`

## Where to Put New Recognizers

### Universal Pattern

Use `sovereignguard/recognizers/universal/` when the pattern is not country-specific.

Examples:

- email
- IBAN
- credit card
- IP address

### Locale-Specific Pattern

Use `sovereignguard/recognizers/<locale>/` when the pattern depends on local formats or local contextual language.

Examples:

- Tunisian national ID
- French NIR
- Moroccan ICE

## Step-by-Step Workflow

### 1. Create the Recognizer Module

Create a file under the correct locale package.

Example path:

```text
sovereignguard/recognizers/universal/passport.py
```

### 2. Implement the Recognizer

Example skeleton:

```python
from typing import List

from sovereignguard.recognizers.base import BaseRecognizer, RecognizerResult


class PassportRecognizer(BaseRecognizer):
	@property
	def entity_types(self) -> List[str]:
		return ["PASSPORT"]

	@property
	def locale(self) -> str:
		return "universal"

	@property
	def priority(self) -> int:
		return 50

	def analyze(self, text: str) -> List[RecognizerResult]:
		return self._regex_analyze(
			text,
			[
				(r"\b[A-Z]{2}\d{7}\b", "PASSPORT", 0.85),
			],
		)
```

### 3. Register the Recognizer

Add it to the registry in [sovereignguard/recognizers/registry.py](../sovereignguard/recognizers/registry.py).

If it is universal, add it to the `universal` recognizer list. If it is locale-specific, add it to that locale list.

### 4. Add Tests

Minimum test coverage should include:

1. valid positive examples
2. invalid negative examples
3. edge cases near neighboring punctuation or whitespace
4. locale-specific variations if relevant

### 5. Validate End-to-End

Run the recognizer tests and at least one masking engine integration test to ensure the entity is actually tokenized and restored correctly.

## Design Guidelines

### Prefer Precision Over Recall

A recognizer that misses rare edge cases is usually safer than a recognizer that masks normal business text incorrectly.

### Use Context for Ambiguous Data

Fields like names, dates, and account references are often ambiguous. Add contextual keywords or formatting expectations so the recognizer does not over-mask unrelated text.

### Keep Offsets Correct

`start` and `end` must point into the original input string. Do not rewrite, normalize, or mutate the input before computing offsets unless you can map the offsets back correctly.

### Respect Priority

Locale-specific recognizers should generally have a higher priority than broad universal recognizers so they win overlap resolution when both match the same text.

### Do Not Log Raw PII

Recognizer code must never emit sensitive values into logs.

## Scoring Guidance

Recognizer scores should be meaningful because they interact with `CONFIDENCE_THRESHOLD`.

Typical guidance:

- `0.9 - 1.0`: explicit identifiers with rigid structure and checksum-like confidence
- `0.8 - 0.9`: highly structured identifiers or strong contextual clues
- `0.7 - 0.8`: useful but somewhat ambiguous patterns
- below `0.7`: generally avoid unless you want operators to lower the threshold intentionally

## Common Mistakes

Avoid these failures:

1. returning overlapping matches with inconsistent scores
2. matching generic numbers or dates without context
3. using patterns that capture surrounding punctuation unnecessarily
4. forgetting to register the recognizer in the registry
5. adding a recognizer without negative tests

## When to Create a Custom Recognizer

Create a custom recognizer when your domain includes identifiers that general privacy tooling will miss.

Examples:

- internal customer numbers
- contract references
- invoice IDs
- healthcare record IDs
- local governmental formats not yet covered by the project
