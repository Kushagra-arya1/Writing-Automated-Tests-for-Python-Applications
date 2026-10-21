"""
tests.test_types
~~~~~~~~~~~~~~~~

Unit tests for datapype.types.
Verifies type coercion, strict mode enforcement, boundary handling, and error raising.
"""

from datetime import datetime
import math
import pytest

from datapype.types import (
    AnyType,
    BooleanType,
    DataType,
    DateTimeType,
    FloatType,
    IntegerType,
    ListType,
    StringType,
)


class TestAnyType:
    """Tests for AnyType."""

    def test_any_type_preserves_values(self):
        t = AnyType()
        assert t.coerce(42) == 42
        assert t.coerce("hello") == "hello"
        assert t.coerce([1, 2, 3]) == [1, 2, 3]
        assert t.coerce(None) is None
        assert t.is_valid(object()) is True
        assert repr(t) == "AnyType()"


class TestIntegerType:
    """Tests for IntegerType."""

    def test_native_integers(self):
        t = IntegerType()
        assert t.coerce(0) == 0
        assert t.coerce(100) == 100
        assert t.coerce(-999) == -999
        assert t.is_valid(42) is True

    @pytest.mark.parametrize(
        "input_str, expected",
        [
            ("42", 42),
            ("-100", -100),
            (" 55 ", 55),
            ("42.0", 42),
            ("0", 0),
        ],
    )
    def test_string_coercion_lenient(self, input_str, expected):
        t = IntegerType()
        assert t.coerce(input_str, strict=False) == expected

    def test_float_coercion_integer_values(self):
        t = IntegerType()
        assert t.coerce(10.0, strict=False) == 10
        assert t.coerce(-5.0, strict=False) == -5

    def test_float_with_fractional_part_raises_value_error(self):
        t = IntegerType()
        with pytest.raises(ValueError, match="fractional part"):
            t.coerce(10.5, strict=False)

    def test_booleans_are_strictly_rejected(self):
        t = IntegerType()
        with pytest.raises(TypeError, match="Boolean"):
            t.coerce(True)
        with pytest.raises(TypeError, match="Boolean"):
            t.coerce(False)
        assert t.is_valid(True) is False
        assert t.is_valid(False) is False

    def test_strict_mode_rejects_strings_and_floats(self):
        t = IntegerType()
        with pytest.raises(TypeError, match="strict mode"):
            t.coerce("42", strict=True)
        with pytest.raises(TypeError, match="strict mode"):
            t.coerce(42.0, strict=True)

    @pytest.mark.parametrize("invalid_input", ["", "   ", "abc", "12.34.56", "NaN", None, [], {}])
    def test_invalid_inputs_raise(self, invalid_input):
        t = IntegerType()
        assert t.is_valid(invalid_input) is False
        with pytest.raises((ValueError, TypeError)):
            t.coerce(invalid_input)


class TestFloatType:
    """Tests for FloatType."""

    def test_native_floats_and_ints(self):
        t = FloatType()
        assert t.coerce(3.1415) == pytest.approx(3.1415)
        assert t.coerce(42) == 42.0
        assert t.coerce(-10) == -10.0

    @pytest.mark.parametrize(
        "input_str, expected",
        [
            ("3.14", 3.14),
            ("-0.05", -0.05),
            (" 100.25 ", 100.25),
            ("1e-3", 0.001),
        ],
    )
    def test_string_coercion_lenient(self, input_str, expected):
        t = FloatType()
        assert t.coerce(input_str, strict=False) == pytest.approx(expected)

    def test_booleans_are_rejected(self):
        t = FloatType()
        with pytest.raises(TypeError, match="Boolean"):
            t.coerce(True)
        with pytest.raises(TypeError, match="Boolean"):
            t.coerce(False)

    def test_strict_mode_rejects_strings(self):
        t = FloatType()
        with pytest.raises(TypeError, match="strict=True"):
            t.coerce("3.14", strict=True)

    def test_nan_disallowed_by_default(self):
        t = FloatType(allow_nan=False)
        with pytest.raises(ValueError, match="NaN"):
            t.coerce(float("nan"))

    def test_nan_allowed_when_configured(self):
        t = FloatType(allow_nan=True)
        val = t.coerce(float("nan"))
        assert math.isnan(val)

    def test_inf_disallowed_by_default(self):
        t = FloatType(allow_inf=False)
        with pytest.raises(ValueError, match="Infinity"):
            t.coerce(float("inf"))
        with pytest.raises(ValueError, match="Infinity"):
            t.coerce(float("-inf"))

    def test_inf_allowed_when_configured(self):
        t = FloatType(allow_inf=True)
        assert math.isinf(t.coerce(float("inf")))

    @pytest.mark.parametrize("invalid_input", ["", "   ", "not_a_number", None, [1.0]])
    def test_invalid_float_inputs_raise(self, invalid_input):
        t = FloatType()
        with pytest.raises((ValueError, TypeError)):
            t.coerce(invalid_input)


class TestStringType:
    """Tests for StringType."""

    def test_native_strings(self):
        t = StringType()
        assert t.coerce("hello world") == "hello world"

    def test_strip_whitespace_option(self):
        t = StringType(strip_whitespace=True)
        assert t.coerce("  surrounded by space  ") == "surrounded by space"

    def test_lenient_coercion_of_other_types(self):
        t = StringType()
        assert t.coerce(12345, strict=False) == "12345"
        assert t.coerce(True, strict=False) == "True"

    def test_strict_mode_rejects_non_strings(self):
        t = StringType()
        with pytest.raises(TypeError, match="Expected str"):
            t.coerce(123, strict=True)


class TestBooleanType:
    """Tests for BooleanType."""

    def test_native_booleans(self):
        t = BooleanType()
        assert t.coerce(True) is True
        assert t.coerce(False) is False

    @pytest.mark.parametrize("truthy", ["true", "True", "TRUE", "1", "yes", "YES", "y", "t", "on"])
    def test_lenient_truthy_strings(self, truthy):
        t = BooleanType()
        assert t.coerce(truthy, strict=False) is True

    @pytest.mark.parametrize("falsy", ["false", "False", "FALSE", "0", "no", "NO", "n", "f", "off"])
    def test_lenient_falsy_strings(self, falsy):
        t = BooleanType()
        assert t.coerce(falsy, strict=False) is False

    def test_numeric_integers_one_and_zero(self):
        t = BooleanType()
        assert t.coerce(1, strict=False) is True
        assert t.coerce(0, strict=False) is False

    @pytest.mark.parametrize("ambiguous_num", [2, -1, 100, 0.5])
    def test_ambiguous_numbers_raise_value_error(self, ambiguous_num):
        t = BooleanType()
        with pytest.raises(ValueError, match="unambiguously"):
            t.coerce(ambiguous_num, strict=False)

    def test_strict_mode_rejects_strings_and_numbers(self):
        t = BooleanType()
        with pytest.raises(TypeError, match="Expected bool"):
            t.coerce("true", strict=True)
        with pytest.raises(TypeError, match="Expected bool"):
            t.coerce(1, strict=True)

    @pytest.mark.parametrize("invalid_val", ["maybe", "null", "", "undefined", None, []])
    def test_invalid_values_raise(self, invalid_val):
        t = BooleanType()
        with pytest.raises((ValueError, TypeError)):
            t.coerce(invalid_val)


class TestDateTimeType:
    """Tests for DateTimeType."""

    def test_preserves_datetime_instance(self):
        t = DateTimeType()
        now = datetime.now()
        assert t.coerce(now) == now

    def test_iso_string_parsing(self):
        t = DateTimeType()
        dt = t.coerce("2023-07-15T14:30:00")
        assert dt == datetime(2023, 7, 15, 14, 30, 0)

    def test_custom_format_parsing(self):
        t = DateTimeType(date_format="%d/%m/%Y")
        dt = t.coerce("25/12/2024")
        assert dt == datetime(2024, 12, 25)

    def test_custom_format_mismatch_raises(self):
        t = DateTimeType(date_format="%Y-%m-%d")
        with pytest.raises(ValueError, match="does not match format"):
            t.coerce("25/12/2024")

    def test_fallback_common_patterns(self):
        t = DateTimeType()
        assert t.coerce("2023-01-05") == datetime(2023, 1, 5)
        assert t.coerce("2023-01-05 10:20:30") == datetime(2023, 1, 5, 10, 20, 30)

    def test_strict_mode_rejects_strings(self):
        t = DateTimeType()
        with pytest.raises(TypeError, match="strict mode"):
            t.coerce("2023-01-05", strict=True)

    def test_empty_string_and_invalid_date_raise(self):
        t = DateTimeType()
        with pytest.raises(ValueError, match="empty string"):
            t.coerce("")
        with pytest.raises(ValueError):
            t.coerce("not-a-valid-date")


class TestListType:
    """Tests for ListType."""

    def test_native_lists(self):
        t = ListType()
        assert t.coerce([1, 2, 3]) == [1, 2, 3]

    def test_tuples_and_sets_coerced_to_list(self):
        t = ListType()
        assert t.coerce((1, 2, 3)) == [1, 2, 3]
        assert sorted(t.coerce({1, 2})) == [1, 2]

    def test_comma_delimited_string_coercion(self):
        t = ListType()
        assert t.coerce("apple, banana, cherry", strict=False) == ["apple", "banana", "cherry"]

    def test_custom_delimiter(self):
        t = ListType(delimiter=";")
        assert t.coerce("a;b;c", strict=False) == ["a", "b", "c"]

    def test_inner_item_type_coercion(self):
        t = ListType(item_type=IntegerType())
        assert t.coerce("1, 2, 3", strict=False) == [1, 2, 3]
        assert t.coerce(["10", 20, "30"], strict=False) == [10, 20, 30]

    def test_inner_item_type_failure_raises(self):
        t = ListType(item_type=IntegerType())
        with pytest.raises(ValueError):
            t.coerce("1, two, 3", strict=False)

    def test_strict_mode_rejects_strings(self):
        t = ListType()
        with pytest.raises(TypeError):
            t.coerce("1,2,3", strict=True)
