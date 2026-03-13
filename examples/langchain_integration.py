"""
LangChain integration example.
"""

from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key="placeholder",
    base_url="http://localhost:8000",
)

response = llm.invoke(
    "Summarize this support note for customer alice@example.com with callback +33 6 12 34 56 78."
)

print(response.content)
