from sovereignguard.engine.semantic_restorer import SemanticRestorer
from sovereignguard.engine.mapping import MappingStore


def test_semantic_restorer_exact_and_fuzzy_variants(engine):
    session_id = engine.new_session()
    text = "Contact Mohamed at +216 98 765 432"

    masked = engine.mask(text, session_id)

    # Extract generated tokens from masked text
    parts = masked.masked_text.split()
    name_token = next(p for p in parts if p.startswith("{{SG_PERSON_NAME_"))
    phone_token = next(p for p in parts if p.startswith("{{SG_TN_PHONE_"))

    # Simulate LLM reformatting
    name_suffix = name_token.replace("{{SG_PERSON_NAME_", "").replace("}}", "")
    phone_suffix = phone_token.replace("{{SG_TN_PHONE_", "").replace("}}", "")

    llm_response = (
        f"I reached out to SG PERSON NAME {name_suffix} "
        f"using [SG TN PHONE {phone_suffix}]"
    )

    restored = engine.restore(llm_response, session_id)

    assert "Mohamed" in restored.restored_text
    assert "+216 98 765 432" in restored.restored_text

    engine.end_session(session_id)


def test_semantic_restorer_completeness_tracking():
    mapping_store = MappingStore()
    session_id = "test-session-completeness"
    mapping_store.create_session(session_id)

    token = "{{SG_EMAIL_deadbeef}}"
    mapping_store.store(session_id, token, "user@example.com", "EMAIL")

    restorer = SemanticRestorer(mapping_store)
    result = restorer.restore(
        text="Please contact SG EMAIL deadbeef soon.",
        session_id=session_id,
        tokens_sent={token, "{{SG_PHONE_feedface}}"},
    )

    assert result.tokens_restored == 1
    assert result.tokens_sent == 2
    assert result.restoration_completeness == 0.5
    assert "{{SG_PHONE_feedface}}" in result.unreplaced_tokens
