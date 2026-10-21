"""
tests.test_transformers
~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for datapype.transformers.
Validates pure data cleansing, string normalization, math rounding, date formatting,
and chained pipeline transformations.
"""

from datetime import datetime
import pytest

from datapype.exceptions import TransformationError
from datapype.transformers import (
    ChainedTransformer,
    CustomTransformer,
    DateFormat,
    DefaultIfNull,
    MapValues,
    Replace,
    RoundNumber,
    ToLowerCase,
    ToTitleCase,
    ToUpperCase,
    Trim,
)


class TestTrimTransformer:
    """Tests for Trim transformer."""

    def test_strip_whitespace(self):
        t = Trim()
        assert t.transform("  padded string   ") == "padded string"
        assert t.transform("\tnewline and tabs\n") == "newline and tabs"

    def test_custom_strip_characters(self):
        t = Trim(chars="xyz")
        assert t.transform("xyzhellozyx") == "hello"

    def test_none_and_non_strings(self):
        t = Trim()
        assert t.transform(None) is None
        assert t.transform(12345) == 12345


class TestCasingTransformers:
    """Tests for ToUpperCase, ToLowerCase, and ToTitleCase."""

    def test_to_upper_case(self):
        t = ToUpperCase()
        assert t.transform("hello world") == "HELLO WORLD"
        assert t.transform(None) is None
        with pytest.raises(TransformationError, match="Expected str"):
            t.transform(123)

    def test_to_lower_case(self):
        t = ToLowerCase()
        assert t.transform("ALICE@EXAMPLE.COM") == "alice@example.com"
        assert t.transform(None) is None
        with pytest.raises(TransformationError, match="Expected str"):
            t.transform(True)

    def test_to_title_case(self):
        t = ToTitleCase()
        assert t.transform("jane doe smith") == "Jane Doe Smith"
        assert t.transform(None) is None
        with pytest.raises(TransformationError):
            t.transform([1, 2, 3])


class TestReplaceTransformer:
    """Tests for Replace transformer."""

    def test_substring_replacement(self):
        t = Replace("-", "/")
        assert t.transform("2023-05-10") == "2023/05/10"

    def test_regex_replacement(self):
        t = Replace(r"\s+", " ")
        assert t.transform("Multiple   spaces    here") == "Multiple spaces here"

    def test_none_and_type_check(self):
        t = Replace("a", "b")
        assert t.transform(None) is None
        with pytest.raises(TransformationError):
            t.transform(42)


class TestRoundNumberTransformer:
    """Tests for RoundNumber transformer."""

    def test_init_validation(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            RoundNumber(decimals=-1)

    def test_rounding_precision(self):
        t2 = RoundNumber(decimals=2)
        assert t2.transform(3.14159) == 3.14
        assert t2.transform(10.556) == 10.56
        assert t2.transform(10) == 10.0

        t0 = RoundNumber(decimals=0)
        assert t0.transform(45.7) == 46.0

    def test_none_and_invalid_types(self):
        t = RoundNumber(decimals=2)
        assert t.transform(None) is None
        with pytest.raises(TransformationError, match="Cannot round non-numeric string"):
            t.transform("not_a_number")
        with pytest.raises(TransformationError, match="Expected numeric"):
            t.transform(True)


class TestDefaultIfNullTransformer:
    """Tests for DefaultIfNull transformer."""

    def test_default_on_none(self):
        t = DefaultIfNull(default_value="N/A")
        assert t.transform(None) == "N/A"
        assert t.transform("Actual Value") == "Actual Value"

    def test_treat_empty_as_null(self):
        t = DefaultIfNull(default_value="UNKNOWN", treat_empty_as_null=True)
        assert t.transform("") == "UNKNOWN"
        assert t.transform([]) == "UNKNOWN"
        assert t.transform({}) == "UNKNOWN"
        assert t.transform("Valid") == "Valid"


class TestMapValuesTransformer:
    """Tests for MapValues transformer."""

    def test_mapping_lookup(self):
        t = MapValues({"A": "Active", "I": "Inactive", "P": "Pending"}, default="Unknown")
        assert t.transform("A") == "Active"
        assert t.transform("I") == "Inactive"
        assert t.transform("X") == "Unknown"

    def test_strict_mode_unmapped_raises(self):
        t = MapValues({"A": "Active"}, strict=True)
        with pytest.raises(TransformationError, match="not in mapping"):
            t.transform("Z")


class TestDateFormatTransformer:
    """Tests for DateFormat transformer."""

    def test_format_datetime_object(self):
        t = DateFormat(output_format="%d-%b-%Y")
        dt = datetime(2023, 10, 25)
        assert t.transform(dt) == "25-Oct-2023"

    def test_format_iso_string(self):
        t = DateFormat(output_format="%Y/%m/%d")
        assert t.transform("2023-12-31T23:59:59") == "2023/12/31"

    def test_format_with_input_format(self):
        t = DateFormat(output_format="%Y-%m-%d", input_format="%d/%m/%Y")
        assert t.transform("15/08/2024") == "2024-08-15"

    def test_invalid_date_raises(self):
        t = DateFormat(output_format="%Y-%m-%d", input_format="%Y-%m-%d")
        with pytest.raises(TransformationError):
            t.transform("not-a-date")

    def test_none_returns_none(self):
        t = DateFormat(output_format="%Y-%m-%d")
        assert t.transform(None) is None


class TestCustomAndChainedTransformers:
    """Tests for CustomTransformer and ChainedTransformer."""

    def test_custom_transformer(self):
        double_it = CustomTransformer(lambda x: x * 2, name="double")
        assert double_it.transform(21) == 42
        assert double_it.transform("abc") == "abcabc"

    def test_custom_transformer_error_handling(self):
        faulty = CustomTransformer(lambda x: x / 0)
        with pytest.raises(TransformationError, match="Custom transformer error"):
            faulty.transform(10)

    def test_chained_transformer(self):
        pipeline = ChainedTransformer([
            Trim(),
            ToLowerCase(),
            Replace(r"\s+", "_"),
        ])
        assert pipeline.transform("   User Account Name   ") == "user_account_name"
