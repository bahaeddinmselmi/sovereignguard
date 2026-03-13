"""
Tests for person name and date of birth recognizers.
"""

from sovereignguard.recognizers.universal.person_name import PersonNameRecognizer
from sovereignguard.recognizers.universal.date_of_birth import DateOfBirthRecognizer


# ─── Person Name Tests ─────────────────────────────────────────────

class TestPersonNameRecognizer:

    def setup_method(self):
        self.recognizer = PersonNameRecognizer()

    def test_detects_name_with_title_mr(self):
        results = self.recognizer.analyze("Please contact Mr. Mohamed Ben Ali")
        assert len(results) >= 1
        assert any(r.entity_type == "PERSON_NAME" for r in results)

    def test_detects_name_with_title_dr(self):
        results = self.recognizer.analyze("Dr. Ahmed Nouira is available")
        assert len(results) >= 1
        names = [r for r in results if r.entity_type == "PERSON_NAME"]
        assert any("Ahmed" in r.text for r in names)

    def test_detects_name_with_context_keyword(self):
        results = self.recognizer.analyze("client: Jean Dupont has an account")
        assert len(results) >= 1
        assert any(r.entity_type == "PERSON_NAME" for r in results)

    def test_detects_name_with_from_keyword(self):
        results = self.recognizer.analyze("from: Marie Claire Lefebvre")
        assert len(results) >= 1

    def test_no_false_positive_on_regular_text(self):
        results = self.recognizer.analyze("The weather is nice today in Paris")
        names = [r for r in results if r.entity_type == "PERSON_NAME"]
        assert len(names) == 0

    def test_detects_french_name_with_mme(self):
        results = self.recognizer.analyze("Mme Fatima Zahra est présente")
        assert len(results) >= 1

    def test_score_higher_with_title(self):
        results_title = self.recognizer.analyze("Mr. Ahmed Benkirane")
        results_context = self.recognizer.analyze("name: Ahmed Benkirane")
        if results_title and results_context:
            assert results_title[0].score >= results_context[0].score


# ─── Date of Birth Tests ──────────────────────────────────────────

class TestDateOfBirthRecognizer:

    def setup_method(self):
        self.recognizer = DateOfBirthRecognizer()

    def test_detects_dob_with_keyword_english(self):
        results = self.recognizer.analyze("Date of birth: 15/03/1990")
        assert len(results) == 1
        assert results[0].entity_type == "DATE_OF_BIRTH"
        assert results[0].text == "15/03/1990"

    def test_detects_dob_with_born_on(self):
        results = self.recognizer.analyze("He was born on 1990-03-15")
        assert len(results) == 1
        assert results[0].entity_type == "DATE_OF_BIRTH"

    def test_detects_dob_french_context(self):
        results = self.recognizer.analyze("Date de naissance: 15/03/1990")
        assert len(results) == 1

    def test_ignores_generic_dates(self):
        results = self.recognizer.analyze("The meeting is on 15/03/2024")
        assert len(results) == 0

    def test_detects_textual_date(self):
        results = self.recognizer.analyze("DOB: 15 January 1990")
        assert len(results) == 1
        assert "January" in results[0].text

    def test_detects_dob_abbreviation(self):
        results = self.recognizer.analyze("DOB 01-15-1990")
        assert len(results) == 1

    def test_detects_dob_arabic_context(self):
        results = self.recognizer.analyze("تاريخ الميلاد 15/03/1990")
        assert len(results) == 1
