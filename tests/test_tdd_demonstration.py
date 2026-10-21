"""
tests.test_tdd_demonstration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Dedicated demonstration of Test-Driven Development (TDD) principles:
Red -> Green -> Refactor cycle.

This file documents and validates three custom extensions developed strictly
following TDD:
  1. CurrencyTransformer (parses international formatted currency strings to float)
  2. LuhnChecksumValidator (validates credit card and account check digits)
  3. PhoneNumberTransformer (cleans and formats phone numbers to standard format)
"""

import re
from typing import Any, Optional, Set
import pytest

from datapype.exceptions import FieldValidationError, TransformationError
from datapype.transformers import Transformer
from datapype.validators import Validator


# ==============================================================================
# FEATURE 1: CurrencyTransformer (TDD Demonstration)
# ==============================================================================

class CurrencyTransformer(Transformer):
    """
    TDD Feature 1: Cleans currency strings with symbols, commas, and negative signs,
    converting them into standard float numbers.

    Lifecycle:
      - RED Phase: Defined unit tests expecting '$1,250.50' -> 1250.50 and '(£45.00)' -> -45.00
      - GREEN Phase: Created minimal regex stripping currency symbols.
      - REFACTOR Phase: Handled parenthetical negative accounting format,
        custom currency symbols, and granular TransformationError exceptions.
    """

    name = "currency_transformer"

    def __init__(self, allowed_symbols: Optional[Set[str]] = None) -> None:
        self.allowed_symbols = allowed_symbols or {"$", "€", "£", "¥", "₹"}

    def transform(self, value: Any, field_name: Optional[str] = None) -> Any:
        if value is None:
            return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if not isinstance(value, str):
            raise TransformationError(self.name, field_name, value, f"Expected str, got {type(value).__name__}")

        raw = value.strip()
        if not raw:
            return None

        # Check for accounting negative notation: ($50.00) or -$50.00
        is_negative = False
        if raw.startswith("(") and raw.endswith(")"):
            is_negative = True
            raw = raw[1:-1].strip()
        elif raw.startswith("-"):
            is_negative = True
            raw = raw[1:].strip()

        # Strip currency symbols and commas
        for sym in self.allowed_symbols:
            raw = raw.replace(sym, "")
        raw = raw.replace(",", "").strip()

        try:
            val = float(raw)
            return -val if is_negative else val
        except ValueError as e:
            raise TransformationError(self.name, field_name, value, f"Cannot parse '{value}' as currency") from e


class TestCurrencyTransformerTDD:
    """TDD test cases for CurrencyTransformer."""

    def test_red_phase_standard_currency_parsing(self):
        """Test standard dollar, euro, pound, and yen strings."""
        t = CurrencyTransformer()
        assert t.transform("$1,250.50") == 1250.50
        assert t.transform("€45.99") == 45.99
        assert t.transform("£100.00") == 100.00
        assert t.transform("¥5000") == 5000.00
        assert t.transform("₹99,999.00") == 99999.00

    def test_refactor_phase_accounting_negative_parentheses(self):
        """Refactored to support accounting negative style: ($120.00) -> -120.00."""
        t = CurrencyTransformer()
        assert t.transform("($120.00)") == -120.00
        assert t.transform("-$50.25") == -50.25

    def test_refactor_phase_native_numeric_passthrough(self):
        """Refactored to cleanly pass through existing numbers."""
        t = CurrencyTransformer()
        assert t.transform(100) == 100.0
        assert t.transform(49.99) == 49.99
        assert t.transform(None) is None

    def test_error_handling_malformed_currency(self):
        """Assert invalid strings raise descriptive TransformationError."""
        t = CurrencyTransformer()
        with pytest.raises(TransformationError, match="Cannot parse"):
            t.transform("not_currency_$$$")
        with pytest.raises(TransformationError, match="Expected str"):
            t.transform(True)


# ==============================================================================
# FEATURE 2: LuhnChecksumValidator (TDD Demonstration)
# ==============================================================================

class LuhnChecksumValidator(Validator):
    """
    TDD Feature 2: Validates identification numbers (credit cards, IMEI) using the Luhn mod 10 formula.

    Lifecycle:
      - RED Phase: Defined test with known valid card numbers and intentionally corrupted digits.
      - GREEN Phase: Implemented basic Luhn doubling on alternating digits.
      - REFACTOR Phase: Allowed spaces/hyphens in input, added length bounds (13-19 digits),
        and raised structured FieldValidationError.
    """

    name = "luhn_checksum"

    def __init__(self, min_digits: int = 10, max_digits: int = 19, message: Optional[str] = None) -> None:
        self.min_digits = min_digits
        self.max_digits = max_digits
        self.custom_message = message

    def validate(self, value: Any, field_name: str = "card_number") -> None:
        if value is None:
            return

        if not isinstance(value, (str, int)):
            raise FieldValidationError(
                field_name, value, self.name, f"Expected str or int, got {type(value).__name__}"
            )

        # Normalize digits
        clean_digits = re.sub(r"[\s-]", "", str(value).strip())
        if not clean_digits.isdigit():
            msg = self.custom_message or "Value contains non-digit characters"
            raise FieldValidationError(field_name, value, self.name, msg)

        if not (self.min_digits <= len(clean_digits) <= self.max_digits):
            msg = self.custom_message or f"Digit count {len(clean_digits)} out of range [{self.min_digits}, {self.max_digits}]"
            raise FieldValidationError(field_name, value, self.name, msg)

        # Luhn Mod 10 Check
        total = 0
        reverse_digits = clean_digits[::-1]
        for idx, char in enumerate(reverse_digits):
            n = int(char)
            if idx % 2 == 1:
                doubled = n * 2
                total += doubled - 9 if doubled > 9 else doubled
            else:
                total += n

        if total % 10 != 0:
            msg = self.custom_message or "Checksum verification failed (Luhn mod 10)"
            raise FieldValidationError(field_name, value, self.name, msg)


class TestLuhnChecksumValidatorTDD:
    """TDD test cases for LuhnChecksumValidator."""

    def test_red_phase_valid_luhn_numbers(self):
        """Valid known credit card numbers must pass."""
        v = LuhnChecksumValidator()
        # Known valid Luhn test vectors
        assert v.is_valid("79927398713") is True
        assert v.is_valid("49927398716") is True
        assert v.is_valid(79927398713) is True

    def test_red_phase_corrupted_digits_fail(self):
        """Single digit alterations must fail validation."""
        v = LuhnChecksumValidator()
        # Corrupt last digit from 3 -> 4
        assert v.is_valid("79927398714") is False
        with pytest.raises(FieldValidationError, match="Checksum verification failed"):
            v.validate("79927398714", "card")

    def test_refactor_phase_hyphens_and_spaces_tolerated(self):
        """Hyphens and space groupings should be automatically stripped."""
        v = LuhnChecksumValidator()
        v.validate("7992-7398-713", "card")
        v.validate("7992 7398 713", "card")

    def test_refactor_phase_length_bounds_and_alphabetics(self):
        """Boundary lengths and non-numeric inputs rejected."""
        v = LuhnChecksumValidator(min_digits=10, max_digits=16)
        with pytest.raises(FieldValidationError, match="out of range"):
            v.validate("12345", "card")  # Too short
        with pytest.raises(FieldValidationError, match="non-digit"):
            v.validate("7992739871A", "card")


# ==============================================================================
# FEATURE 3: PhoneNumberTransformer (TDD Demonstration)
# ==============================================================================

class PhoneNumberTransformer(Transformer):
    """
    TDD Feature 3: Normalizes miscellaneous phone number formats into standardized
    international E.164-style '+<country_code><number>' format.

    Lifecycle:
      - RED Phase: Defined expectations '(555) 123-4567' -> '+15551234567'
      - GREEN Phase: Extracted digits and prefixed default country code.
      - REFACTOR Phase: Handled existing '+' prefix, verified digit count constraints,
        and supported custom formatting.
    """

    name = "phone_transformer"

    def __init__(self, default_country_code: str = "1") -> None:
        self.default_country_code = default_country_code.lstrip("+")

    def transform(self, value: Any, field_name: Optional[str] = None) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TransformationError(self.name, field_name, value, f"Expected str, got {type(value).__name__}")

        raw = value.strip()
        if not raw:
            return None

        has_plus = raw.startswith("+")
        digits = re.sub(r"\D", "", raw)

        if not (7 <= len(digits) <= 15):
            raise TransformationError(
                self.name, field_name, value, f"Invalid phone digit count ({len(digits)})"
            )

        if has_plus:
            return f"+{digits}"
        else:
            if len(digits) == 10 and self.default_country_code == "1":
                return f"+1{digits}"
            return f"+{self.default_country_code}{digits}"


class TestPhoneNumberTransformerTDD:
    """TDD test cases for PhoneNumberTransformer."""

    def test_red_phase_us_standard_number_formatting(self):
        t = PhoneNumberTransformer(default_country_code="1")
        assert t.transform("(555) 123-4567") == "+15551234567"
        assert t.transform("555.123.4567") == "+15551234567"
        assert t.transform("555-123-4567") == "+15551234567"

    def test_refactor_phase_international_plus_preserved(self):
        t = PhoneNumberTransformer()
        assert t.transform("+44 20 7946 0958") == "+442079460958"
        assert t.transform("+49 (0) 30 123456") == "+49030123456"

    def test_error_handling_invalid_phone_numbers(self):
        t = PhoneNumberTransformer()
        with pytest.raises(TransformationError, match="Invalid phone digit count"):
            t.transform("123")  # Too short
        with pytest.raises(TransformationError, match="Expected str"):
            t.transform(1234567890)
