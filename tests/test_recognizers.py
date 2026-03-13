from sovereignguard.recognizers.tn.national_id import TunisianNationalIDRecognizer
from sovereignguard.recognizers.tn.phone import TunisianPhoneRecognizer
from sovereignguard.recognizers.fr.nir import FrenchNIRRecognizer
from sovereignguard.recognizers.universal.email import EmailRecognizer
from sovereignguard.recognizers.ma.cin import MoroccanCINRecognizer


def test_tunisian_national_id_recognizer():
    recognizer = TunisianNationalIDRecognizer()
    text = "CIN 12345678"
    results = recognizer.analyze(text)
    assert len(results) == 1
    assert results[0].entity_type == "TN_NATIONAL_ID"
    assert results[0].text == "12345678"
    assert results[0].score >= 0.9


def test_tunisian_phone_recognizer():
    recognizer = TunisianPhoneRecognizer()
    text = "Contact: +216 98 765 432"
    results = recognizer.analyze(text)
    assert len(results) == 1
    assert results[0].entity_type == "TN_PHONE"


def test_email_recognizer():
    recognizer = EmailRecognizer()
    text = "Email me at test@example.com"
    results = recognizer.analyze(text)
    assert len(results) == 1
    assert results[0].entity_type == "EMAIL"


def test_moroccan_cin_recognizer():
    recognizer = MoroccanCINRecognizer()
    text = "CIN AB123456"
    results = recognizer.analyze(text)
    assert len(results) == 1
    assert results[0].entity_type == "MA_CIN"


def test_french_nir_recognizer_handles_compact_format():
    recognizer = FrenchNIRRecognizer()
    text = "Numero de securite sociale 185057800608436"
    results = recognizer.analyze(text)
    assert len(results) == 1
    assert results[0].entity_type == "FR_NIR"
