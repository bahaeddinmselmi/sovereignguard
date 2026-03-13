"""
Recognizer Registry — discovers and loads all recognizers by locale.
"""

import logging
from typing import List, Dict

from sovereignguard.recognizers.base import BaseRecognizer

logger = logging.getLogger(__name__)

# All available recognizer classes, keyed by locale
_RECOGNIZER_MAP: Dict[str, List[type]] = {}


def _build_recognizer_map() -> Dict[str, List[type]]:
    """Build the mapping of locale -> recognizer classes."""
    from sovereignguard.recognizers.universal.email import EmailRecognizer
    from sovereignguard.recognizers.universal.phone_generic import GenericPhoneRecognizer
    from sovereignguard.recognizers.universal.credit_card import CreditCardRecognizer
    from sovereignguard.recognizers.universal.iban import IBANRecognizer
    from sovereignguard.recognizers.universal.ip_address import IPAddressRecognizer
    from sovereignguard.recognizers.universal.person_name import PersonNameRecognizer
    from sovereignguard.recognizers.universal.date_of_birth import DateOfBirthRecognizer

    from sovereignguard.recognizers.tn.national_id import TunisianNationalIDRecognizer
    from sovereignguard.recognizers.tn.phone import TunisianPhoneRecognizer
    from sovereignguard.recognizers.tn.company_id import TunisianMatriculeFiscaleRecognizer
    from sovereignguard.recognizers.tn.address import TunisianAddressRecognizer

    from sovereignguard.recognizers.fr.nir import FrenchNIRRecognizer
    from sovereignguard.recognizers.fr.siret import FrenchSIRETRecognizer
    from sovereignguard.recognizers.fr.phone import FrenchPhoneRecognizer
    from sovereignguard.recognizers.fr.address import FrenchAddressRecognizer

    from sovereignguard.recognizers.ma.cin import MoroccanCINRecognizer
    from sovereignguard.recognizers.ma.phone import MoroccanPhoneRecognizer
    from sovereignguard.recognizers.ma.ice import MoroccanICERecognizer

    return {
        "universal": [
            EmailRecognizer,
            GenericPhoneRecognizer,
            CreditCardRecognizer,
            IBANRecognizer,
            IPAddressRecognizer,
            PersonNameRecognizer,
            DateOfBirthRecognizer,
        ],
        "tn": [
            TunisianNationalIDRecognizer,
            TunisianPhoneRecognizer,
            TunisianMatriculeFiscaleRecognizer,
            TunisianAddressRecognizer,
        ],
        "fr": [
            FrenchNIRRecognizer,
            FrenchSIRETRecognizer,
            FrenchPhoneRecognizer,
            FrenchAddressRecognizer,
        ],
        "ma": [
            MoroccanCINRecognizer,
            MoroccanPhoneRecognizer,
            MoroccanICERecognizer,
        ],
    }


class RecognizerRegistry:
    """Manages all loaded PII recognizers."""

    def __init__(self):
        self.recognizers: List[BaseRecognizer] = []

    def load_for_locales(self, locales: List[str]):
        """Load recognizers for the given locales."""
        global _RECOGNIZER_MAP
        if not _RECOGNIZER_MAP:
            _RECOGNIZER_MAP = _build_recognizer_map()

        self.recognizers = []
        for locale in locales:
            classes = _RECOGNIZER_MAP.get(locale, [])
            if not classes:
                logger.warning(f"No recognizers found for locale: {locale}")
                continue
            for cls in classes:
                instance = cls()
                self.recognizers.append(instance)
                logger.debug(
                    f"Loaded recognizer: {cls.__name__} "
                    f"(locale={instance.locale}, types={instance.entity_types})"
                )

        logger.info(f"Loaded {len(self.recognizers)} recognizers for locales: {locales}")

    def get_sorted_recognizers(self) -> List[BaseRecognizer]:
        """Return recognizers sorted by priority (highest first)."""
        return sorted(self.recognizers, key=lambda r: r.priority, reverse=True)

    def count(self) -> int:
        return len(self.recognizers)
