import re


def test_masker_detects_and_masks_tunisian_pii(engine):
    session_id = engine.new_session()
    text = "My name is Mohamed, CIN 12345678, phone +216 98 765 432"

    result = engine.mask(text, session_id)

    assert result.had_pii is True
    assert result.entity_count >= 2
    assert "{{SG_TN_NATIONAL_ID_" in result.masked_text
    assert "{{SG_TN_PHONE_" in result.masked_text

    engine.end_session(session_id)


def test_masker_deduplicates_same_value(engine):
    session_id = engine.new_session()
    text = "Call me at +216 98 765 432. Backup phone is +216 98 765 432."

    result = engine.mask(text, session_id)

    tokens = re.findall(r'\{\{SG_[A-Z_]+_[a-f0-9]{6,12}\}\}', result.masked_text)
    assert len(tokens) == 2
    assert tokens[0] == tokens[1]

    engine.end_session(session_id)
