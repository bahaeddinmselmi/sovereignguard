"""
Basic usage example for SovereignGuard.
"""

from openai import OpenAI

client = OpenAI(
    api_key="any-string",
    base_url="http://localhost:8000",
)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {
            "role": "user",
            "content": "Draft an email to customer alice@example.com about invoice INV-204 with phone +216 98 765 432.",
        }
    ],
)

print(response.choices[0].message.content)
