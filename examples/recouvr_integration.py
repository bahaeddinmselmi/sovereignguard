"""
Recouvr AI × SovereignGuard Integration Example

This is the reference implementation showing how Recouvr AI uses
SovereignGuard to process B2B invoice and client data compliantly.

Client financial data (names, phone numbers, national IDs, amounts)
is masked before reaching the LLM, then restored in the response.
"""

from openai import OpenAI

# Drop-in replacement — only base_url changes
client = OpenAI(
    api_key="recouvr-internal",
    base_url="http://localhost:8000",
)


def generate_recovery_message(
    debtor_name: str,
    debtor_phone: str,
    invoice_number: str,
    amount: float,
    days_overdue: int,
    company_name: str,
    tone: str = "professional",
) -> str:
    """
    Generate a personalized debt recovery message.

    PII (debtor_name, debtor_phone) is automatically masked by SovereignGuard
    before reaching the provider. The response comes back with the real values
    restored locally.
    """
    tone_instructions = {
        "formal": "Use formal French. Address as Monsieur/Madame. Très professionnel.",
        "professional": "Use professional but warm French. Direct and respectful.",
        "friendly": "Use friendly, understanding tone. Acknowledge difficulties.",
    }

    prompt = f"""
    Generate a debt recovery message in French for:

    Debtor: {debtor_name}
    Phone: {debtor_phone}
    Invoice: {invoice_number}
    Amount due: {amount} DT
    Days overdue: {days_overdue}
    Creditor company: {company_name}

    Tone: {tone_instructions.get(tone, tone_instructions['professional'])}

    Requirements:
    - Include a payment link placeholder: [LIEN_PAIEMENT]
    - Keep under 150 words
    - Do not threaten legal action on first contact
    - End with a clear call to action
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are Recouvr AI, an expert in B2B debt recovery communication.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.7,
        max_tokens=300,
    )

    return response.choices[0].message.content


def analyze_debtor_risk(client_history: dict) -> dict:
    """
    Analyze debtor payment history and generate a risk assessment.
    Financial data is masked in transit.
    """
    history_text = f"""
    Client: {client_history['name']}
    ID: {client_history['national_id']}
    Payment history (last 12 months):
    - Average payment delay: {client_history['avg_delay_days']} days
    - Invoices paid on time: {client_history['on_time_pct']}%
    - Last payment date: {client_history['last_payment_date']}
    - Total outstanding: {client_history['total_outstanding']} DT
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a credit risk analyst. Assess debtor risk and recommend recovery strategy. Respond in JSON.",
            },
            {
                "role": "user",
                "content": (
                    "Analyze this debtor profile:\n"
                    f"{history_text}\n\n"
                    "Return JSON with: risk_score (0-100), risk_level (low/medium/high/critical), "
                    "recommended_channel, recommended_tone, escalation_threshold_days"
                ),
            },
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    import json
    return json.loads(response.choices[0].message.content)


if __name__ == "__main__":
    message = generate_recovery_message(
        debtor_name="Mohamed Ben Ali",
        debtor_phone="+216 98 765 432",
        invoice_number="INV-2024-0891",
        amount=340.00,
        days_overdue=67,
        company_name="Recouvr Client SARL",
        tone="professional",
    )

    print("Generated Message:")
    print(message)
    print()

    risk = analyze_debtor_risk({
        "name": "Trans Rapide SARL",
        "national_id": "12345678",
        "avg_delay_days": 45,
        "on_time_pct": 34,
        "last_payment_date": "2024-09-15",
        "total_outstanding": 1840.00,
    })

    print("Risk Analysis:")
    print(risk)
