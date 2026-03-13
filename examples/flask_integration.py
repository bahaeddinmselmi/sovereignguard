"""
Flask integration example.
"""

from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key="placeholder", base_url="http://localhost:8000")


@app.post("/draft")
def draft_message():
    payload = request.get_json(force=True)
    prompt = payload.get("prompt", "")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    return jsonify({"result": response.choices[0].message.content})


if __name__ == "__main__":
    app.run(port=5000, debug=True)
