"""
tests.test_validators
~~~~~~~~~~~~~~~~~~~~~

Unit tests for datapype.validators.
Tests validation rules, boundary conditions, custom messages, and error diagnostics.
"""

import re
import pytest

from datapype.exceptions import FieldValidationError
from datapype.validators import (
    CustomValidator,
    Email,
    InChoices,
    Length,
    NonNegative,
    Positive,
    Range,
    Regex,
    Required,
)


class TestRequiredValidator:
    """Tests for Required validator."""

    def test_valid_present_values(self):
        v = Required()
        v.validate("hello", "username")
        v.validate(123, "count")
        v.validate([1], "items")
        assert v.is_valid("hello") is True

    def test_none_value_raises_field_validation_error(self):
        v = Required()
        with pytest.raises(FieldValidationError) as exc_info:
            v.validate(None, "username")
        err = exc_info.value
        assert err.field == "username"
        assert err.rule == "required"
        assert err.value is None

    @pytest.mark.parametrize("empty_val", ["", [], {}, set(), ()])
    def test_empty_values_rejected_by_default(self, empty_val):
        v = Required(allow_empty=False)
        assert v.is_valid(empty_val) is False
        with pytest.raises(FieldValidationError):
            v.validate(empty_val, "field")

    @pytest.mark.parametrize("empty_val", ["", [], {}, set(), ()])
    def test_empty_values_allowed_when_configured(self, empty_val):
        v = Required(allow_empty=True)
        v.validate(empty_val, "field")
        assert v.is_valid(empty_val) is True

    def test_custom_message(self):
        v = Required(message="Custom mandatory message")
        with pytest.raises(FieldValidationError, match="Custom mandatory message"):
            v.validate(None, "user")


class TestRangeValidator:
    """Tests for Range validator."""

    def test_init_validations(self):
        with pytest.raises(ValueError, match="requires at least min_value or max_value"):
            Range()
        with pytest.raises(ValueError, match="cannot exceed"):
            Range(min_value=10, max_value=5)

    def test_inclusive_boundaries(self):
        v = Range(min_value=10, max_value=20, inclusive_min=True, inclusive_max=True)
        v.validate(10, "num")
        v.validate(15, "num")
        v.validate(20, "num")
        assert v.is_valid(10) is True
        assert v.is_valid(20) is True

        with pytest.raises(FieldValidationError):
            v.validate(9.99, "num")
        with pytest.raises(FieldValidationError):
            v.validate(20.01, "num")

    def test_exclusive_boundaries(self):
        v = Range(min_value=10, max_value=20, inclusive_min=False, inclusive_max=False)
        v.validate(10.01, "num")
        v.validate(19.99, "num")

        with pytest.raises(FieldValidationError):
            v.validate(10, "num")
        with pytest.raises(FieldValidationError):
            v.validate(20, "num")

    def test_one_sided_bounds(self):
        v_min_only = Range(min_value=0)
        v_min_only.validate(0, "num")
        v_min_only.validate(1000, "num")
        with pytest.raises(FieldValidationError):
            v_min_only.validate(-1, "num")

        v_max_only = Range(max_value=100)
        v_max_only.validate(-500, "num")
        v_max_only.validate(100, "num")
        with pytest.raises(FieldValidationError):
            v_max_only.validate(101, "num")

    def test_non_numeric_type_raises(self):
        v = Range(min_value=0, max_value=10)
        with pytest.raises(FieldValidationError, match="numeric"):
            v.validate("10", "num")
        with pytest.raises(FieldValidationError, match="numeric"):
            v.validate(True, "num")  # bools must not pass as numbers

    def test_none_is_ignored(self):
        v = Range(min_value=0, max_value=10)
        v.validate(None, "num")  # Deferred to Required


class TestLengthValidator:
    """Tests for Length validator."""

    def test_init_validations(self):
        with pytest.raises(ValueError):
            Length()
        with pytest.raises(ValueError):
            Length(min_length=-1)
        with pytest.raises(ValueError):
            Length(min_length=10, max_length=5)

    def test_string_length_boundaries(self):
        v = Length(min_length=3, max_length=5)
        v.validate("abc", "str")
        v.validate("abcd", "str")
        v.validate("abcde", "str")

        with pytest.raises(FieldValidationError, match="less than minimum"):
            v.validate("ab", "str")
        with pytest.raises(FieldValidationError, match="exceeds maximum"):
            v.validate("abcdef", "str")

    def test_collection_length(self):
        v = Length(min_length=1, max_length=2)
        v.validate([1], "list")
        v.validate([1, 2], "list")
        with pytest.raises(FieldValidationError):
            v.validate([1, 2, 3], "list")

    def test_unsupported_type_raises(self):
        v = Length(min_length=1)
        with pytest.raises(FieldValidationError, match="has no length"):
            v.validate(12345, "number")


class TestRegexValidator:
    """Tests for Regex validator."""

    def test_string_pattern_and_compiled_regex(self):
        v_str = Regex(r"^\d{3}-\d{2}-\d{4}$")
        v_compiled = Regex(re.compile(r"^\d{3}-\d{2}-\d{4}$"))

        v_str.validate("123-45-6789", "ssn")
        v_compiled.validate("123-45-6789", "ssn")

        with pytest.raises(FieldValidationError):
            v_str.validate("12-345-6789", "ssn")

    def test_non_string_type_raises(self):
        v = Regex(r"\d+")
        with pytest.raises(FieldValidationError, match="expects string"):
            v.validate(123, "val")


class TestInChoicesValidator:
    """Tests for InChoices validator."""

    def test_empty_choices_raises_on_init(self):
        with pytest.raises(ValueError):
            InChoices([])

    def test_choice_membership(self):
        v = InChoices(["pending", "completed", "failed"])
        v.validate("completed", "status")
        v.validate("pending", "status")

        with pytest.raises(FieldValidationError, match="allowable choices"):
            v.validate("in_progress", "status")


class TestEmailValidator:
    """Tests for Email validator."""

    @pytest.mark.parametrize(
        "valid_email",
        [
            "test@example.com",
            "first.last@company.org",
            "user+filter@sub.domain.co.uk",
            "name_123@host.net",
        ],
    )
    def test_valid_emails(self, valid_email):
        v = Email()
        v.validate(valid_email, "email")
        assert v.is_valid(valid_email) is True

    @pytest.mark.parametrize(
        "invalid_email",
        [
            "plainaddress",
            "@missinguser.com",
            "missingdomain@",
            "user@.com",
            "user@domain..com",
            12345,
        ],
    )
    def test_invalid_emails(self, invalid_email):
        v = Email()
        assert v.is_valid(invalid_email) is False
        with pytest.raises(FieldValidationError):
            v.validate(invalid_email, "email")


class TestPositiveAndNonNegative:
    """Tests for Positive and NonNegative shortcuts."""

    def test_positive(self):
        v = Positive()
        v.validate(0.001, "num")
        v.validate(100, "num")
        with pytest.raises(FieldValidationError):
            v.validate(0, "num")
        with pytest.raises(FieldValidationError):
            v.validate(-5, "num")

    def test_non_negative(self):
        v = NonNegative()
        v.validate(0, "num")
        v.validate(100, "num")
        with pytest.raises(FieldValidationError):
            v.validate(-0.01, "num")


class TestCustomValidator:
    """Tests for CustomValidator."""

    def test_custom_predicate_passing_and_failing(self):
        v = CustomValidator(lambda x: x % 2 == 0, message="Number must be even")
        v.validate(4, "even_num")
        assert v.is_valid(4) is True

        with pytest.raises(FieldValidationError, match="Number must be even"):
            v.validate(5, "even_num")

    def test_predicate_raising_exception_is_wrapped(self):
        def bad_predicate(x):
            raise KeyError("Key missing inside predicate")

        v = CustomValidator(bad_predicate, message="Invalid")
        with pytest.raises(FieldValidationError, match="Custom predicate raised exception"):
            v.validate("anything", "test_field")
