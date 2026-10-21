"""
datapype.validators
~~~~~~~~~~~~~~~~~~~

Pure, composable validation rules for fields and records.
Validators check constraints and raise FieldValidationError when violated.
"""

from abc import ABC, abstractmethod
import re
from typing import Any, Callable, Collection, Optional, Union

from datapype.exceptions import FieldValidationError


class Validator(ABC):
    """Abstract base class for all validators."""

    name: str = "validator"

    @abstractmethod
    def validate(self, value: Any, field_name: str = "field") -> None:
        """
        Validates the value. Raises FieldValidationError if invalid.

        Args:
            value: The value to validate.
            field_name: The name of the field being validated.
        """
        pass

    def is_valid(self, value: Any) -> bool:
        """Returns True if the value satisfies this validator rule, False otherwise."""
        try:
            self.validate(value)
            return True
        except FieldValidationError:
            return False

    def __call__(self, value: Any, field_name: str = "field") -> None:
        self.validate(value, field_name)


class Required(Validator):
    """
    Ensures that a field is not None and optionally not empty.
    """

    name = "required"

    def __init__(self, allow_empty: bool = False, message: Optional[str] = None) -> None:
        self.allow_empty = allow_empty
        self.custom_message = message

    def validate(self, value: Any, field_name: str = "field") -> None:
        if value is None:
            msg = self.custom_message or "Value is required and cannot be None"
            raise FieldValidationError(field_name, value, self.name, msg)

        if not self.allow_empty:
            if isinstance(value, (str, list, tuple, set, dict)) and len(value) == 0:
                msg = self.custom_message or "Value cannot be empty"
                raise FieldValidationError(field_name, value, self.name, msg)


class Range(Validator):
    """
    Ensures that a numeric value falls within an allowable range.
    """

    name = "range"

    def __init__(
        self,
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None,
        inclusive_min: bool = True,
        inclusive_max: bool = True,
        message: Optional[str] = None,
    ) -> None:
        if min_value is None and max_value is None:
            raise ValueError("Range validator requires at least min_value or max_value")
        if min_value is not None and max_value is not None and min_value > max_value:
            raise ValueError(f"min_value ({min_value}) cannot exceed max_value ({max_value})")

        self.min_value = min_value
        self.max_value = max_value
        self.inclusive_min = inclusive_min
        self.inclusive_max = inclusive_max
        self.custom_message = message

    def validate(self, value: Any, field_name: str = "field") -> None:
        if value is None:
            return  # None handling is deferred to Required validator

        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise FieldValidationError(
                field_name, value, self.name, f"Expected numeric value for range check, got {type(value).__name__}"
            )

        if self.min_value is not None:
            if self.inclusive_min and value < self.min_value:
                msg = self.custom_message or f"Value must be >= {self.min_value}"
                raise FieldValidationError(field_name, value, self.name, msg)
            if not self.inclusive_min and value <= self.min_value:
                msg = self.custom_message or f"Value must be > {self.min_value}"
                raise FieldValidationError(field_name, value, self.name, msg)

        if self.max_value is not None:
            if self.inclusive_max and value > self.max_value:
                msg = self.custom_message or f"Value must be <= {self.max_value}"
                raise FieldValidationError(field_name, value, self.name, msg)
            if not self.inclusive_max and value >= self.max_value:
                msg = self.custom_message or f"Value must be < {self.max_value}"
                raise FieldValidationError(field_name, value, self.name, msg)


class Length(Validator):
    """
    Validates the length of sequences (strings, lists, etc.).
    """

    name = "length"

    def __init__(
        self,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        if min_length is None and max_length is None:
            raise ValueError("Length validator requires at least min_length or max_length")
        if min_length is not None and min_length < 0:
            raise ValueError("min_length cannot be negative")
        if max_length is not None and max_length < 0:
            raise ValueError("max_length cannot be negative")
        if min_length is not None and max_length is not None and min_length > max_length:
            raise ValueError(f"min_length ({min_length}) cannot exceed max_length ({max_length})")

        self.min_length = min_length
        self.max_length = max_length
        self.custom_message = message

    def validate(self, value: Any, field_name: str = "field") -> None:
        if value is None:
            return

        try:
            length = len(value)
        except TypeError:
            raise FieldValidationError(
                field_name, value, self.name, f"Value of type {type(value).__name__} has no length"
            )

        if self.min_length is not None and length < self.min_length:
            msg = self.custom_message or f"Length {length} is less than minimum allowable {self.min_length}"
            raise FieldValidationError(field_name, value, self.name, msg)

        if self.max_length is not None and length > self.max_length:
            msg = self.custom_message or f"Length {length} exceeds maximum allowable {self.max_length}"
            raise FieldValidationError(field_name, value, self.name, msg)


class Regex(Validator):
    """
    Validates a string value against a compiled regular expression.
    """

    name = "regex"

    def __init__(self, pattern: Union[str, re.Pattern], message: Optional[str] = None) -> None:
        self.pattern = re.compile(pattern) if isinstance(pattern, str) else pattern
        self.custom_message = message

    def validate(self, value: Any, field_name: str = "field") -> None:
        if value is None:
            return

        if not isinstance(value, str):
            raise FieldValidationError(
                field_name, value, self.name, f"Regex validator expects string, got {type(value).__name__}"
            )

        if not self.pattern.search(value):
            msg = self.custom_message or f"Value '{value}' does not match pattern '{self.pattern.pattern}'"
            raise FieldValidationError(field_name, value, self.name, msg)


class InChoices(Validator):
    """
    Validates that a value is an element of an allowable collection.
    """

    name = "in_choices"

    def __init__(self, choices: Collection[Any], message: Optional[str] = None) -> None:
        if not choices:
            raise ValueError("choices collection cannot be empty")
        self.choices = set(choices)
        self.custom_message = message

    def validate(self, value: Any, field_name: str = "field") -> None:
        if value is None:
            return

        if value not in self.choices:
            msg = self.custom_message or f"Value {value!r} is not in allowable choices: {sorted(list(self.choices))}"
            raise FieldValidationError(field_name, value, self.name, msg)


class Email(Validator):
    """
    Validates standard email address syntax.
    """

    name = "email"
    EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")

    def __init__(self, message: Optional[str] = None) -> None:
        self.custom_message = message

    def validate(self, value: Any, field_name: str = "field") -> None:
        if value is None:
            return

        if not isinstance(value, str) or not self.EMAIL_REGEX.match(value.strip()):
            msg = self.custom_message or f"Value '{value}' is not a valid email address"
            raise FieldValidationError(field_name, value, self.name, msg)


class Positive(Range):
    """Shortcut validator for strictly positive numbers (> 0)."""

    def __init__(self, message: Optional[str] = None) -> None:
        super().__init__(min_value=0, inclusive_min=False, message=message or "Value must be strictly positive (> 0)")


class NonNegative(Range):
    """Shortcut validator for non-negative numbers (>= 0)."""

    def __init__(self, message: Optional[str] = None) -> None:
        super().__init__(min_value=0, inclusive_min=True, message=message or "Value must be non-negative (>= 0)")


class CustomValidator(Validator):
    """
    Wraps an arbitrary predicate callable (value) -> bool.
    """

    name = "custom"

    def __init__(self, predicate: Callable[[Any], bool], message: str) -> None:
        self.predicate = predicate
        self.message = message

    def validate(self, value: Any, field_name: str = "field") -> None:
        try:
            result = self.predicate(value)
        except Exception as e:
            raise FieldValidationError(
                field_name, value, self.name, f"Custom predicate raised exception: {e}"
            ) from e

        if not result:
            raise FieldValidationError(field_name, value, self.name, self.message)
