def test_restoration_replaces_tokens(engine):
    session_id = engine.new_session()
    text = "Client CIN 12345678 and phone +216 98 765 432"

    masked = engine.mask(text, session_id)
    restored = engine.restore(masked.masked_text, session_id)

    assert restored.restored_text == text
    assert restored.tokens_restored >= 2

    engine.end_session(session_id)


def test_restoration_handles_missing_token(engine):
    session_id = engine.new_session()
    restored = engine.restore("Unknown token {{SG_EMAIL_deadbeef}}", session_id)

    assert restored.tokens_restored == 0
    assert restored.tokens_not_found == 1

    engine.end_session(session_id)
