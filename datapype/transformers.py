"""
datapype.transformers
~~~~~~~~~~~~~~~~~~~~~

Data cleaning and transformation primitives.
Transformers are pure, deterministic functions that normalize and reshape data.
"""

from abc import ABC, abstractmethod
from datetime import datetime
import re
from typing import Any, Callable, Dict, List, Optional, Union

from datapype.exceptions import TransformationError


class Transformer(ABC):
    """Abstract base class for all data transformers."""

    name: str = "transformer"

    @abstractmethod
    def transform(self, value: Any, field_name: Optional[str] = None) -> Any:
        """
        Transforms the given value.

        Args:
            value: The input value.
            field_name: Optional name of the field for context/error reporting.

        Returns:
            The transformed value.

        Raises:
            TransformationError: If the transformation cannot be performed.
        """
        pass

    def __call__(self, value: Any, field_name: Optional[str] = None) -> Any:
        return self.transform(value, field_name)


class Trim(Transformer):
    """Strips leading and trailing whitespace from string values."""

    name = "trim"

    def __init__(self, chars: Optional[str] = None) -> None:
        self.chars = chars

    def transform(self, value: Any, field_name: Optional[str] = None) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        return value.strip(self.chars)


class ToUpperCase(Transformer):
    """Converts string values to uppercase."""

    name = "to_upper_case"

    def transform(self, value: Any, field_name: Optional[str] = None) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TransformationError(self.name, field_name, value, f"Expected str, got {type(value).__name__}")
        return value.upper()


class ToLowerCase(Transformer):
    """Converts string values to lowercase."""

    name = "to_lower_case"

    def transform(self, value: Any, field_name: Optional[str] = None) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TransformationError(self.name, field_name, value, f"Expected str, got {type(value).__name__}")
        return value.lower()


class ToTitleCase(Transformer):
    """Converts string values to title case."""

    name = "to_title_case"

    def transform(self, value: Any, field_name: Optional[str] = None) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TransformationError(self.name, field_name, value, f"Expected str, got {type(value).__name__}")
        return value.title()


class Replace(Transformer):
    """Replaces occurrences of a substring or pattern."""

    name = "replace"

    def __init__(self, pattern: Union[str, re.Pattern], replacement: str) -> None:
        self.pattern = re.compile(pattern) if isinstance(pattern, str) else pattern
        self.replacement = replacement

    def transform(self, value: Any, field_name: Optional[str] = None) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            raise TransformationError(self.name, field_name, value, f"Expected str, got {type(value).__name__}")
        return self.pattern.sub(self.replacement, value)


class RoundNumber(Transformer):
    """Rounds numeric values to a specified number of decimal places."""

    name = "round_number"

    def __init__(self, decimals: int = 2) -> None:
        if decimals < 0:
            raise ValueError("Decimals cannot be negative")
        self.decimals = decimals

    def transform(self, value: Any, field_name: Optional[str] = None) -> Any:
        if value is None:
            return None
        if isinstance(value, bool):
            raise TransformationError(self.name, field_name, value, f"Expected numeric value, got bool")
        if isinstance(value, (int, float)):
            return round(float(value), self.decimals)
        if isinstance(value, str):
            val_clean = value.strip()
            if not val_clean:
                raise TransformationError(self.name, field_name, value, "Cannot round empty string")
            try:
                return round(float(val_clean), self.decimals)
            except ValueError as e:
                raise TransformationError(self.name, field_name, value, f"Cannot round non-numeric string {value!r}") from e
        raise TransformationError(self.name, field_name, value, f"Expected numeric value, got {type(value).__name__}")


class DefaultIfNull(Transformer):
    """Supplies a default fallback value if the input value is None or empty."""

    name = "default_if_null"

    def __init__(self, default_value: Any, treat_empty_as_null: bool = False) -> None:
        self.default_value = default_value
        self.treat_empty_as_null = treat_empty_as_null

    def transform(self, value: Any, field_name: Optional[str] = None) -> Any:
        if value is None:
            return self.default_value
        if self.treat_empty_as_null and isinstance(value, (str, list, tuple, dict, set)) and len(value) == 0:
            return self.default_value
        return value


class MapValues(Transformer):
    """Maps values using a lookup dictionary with an optional default fallback."""

    name = "map_values"

    def __init__(self, mapping: Dict[Any, Any], default: Any = None, strict: bool = False) -> None:
        self.mapping = mapping
        self.default = default
        self.strict = strict

    def transform(self, value: Any, field_name: Optional[str] = None) -> Any:
        if value in self.mapping:
            return self.mapping[value]
        if self.strict:
            raise TransformationError(self.name, field_name, value, f"Value {value!r} not in mapping")
        return self.default if self.default is not None else value


class DateFormat(Transformer):
    """Formats a datetime object or parseable date string into a target string format."""

    name = "date_format"

    def __init__(self, output_format: str, input_format: Optional[str] = None) -> None:
        self.output_format = output_format
        self.input_format = input_format

    def transform(self, value: Any, field_name: Optional[str] = None) -> Any:
        if value is None:
            return None

        dt: Optional[datetime] = None
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            clean = value.strip()
            if not clean:
                return None
            if self.input_format:
                try:
                    dt = datetime.strptime(clean, self.input_format)
                except ValueError as e:
                    raise TransformationError(
                        self.name, field_name, value, f"String does not match input format '{self.input_format}'"
                    ) from e
            else:
                try:
                    dt = datetime.fromisoformat(clean)
                except ValueError as e:
                    raise TransformationError(self.name, field_name, value, f"Cannot parse ISO datetime: {e}") from e
        else:
            raise TransformationError(
                self.name, field_name, value, f"Expected datetime or str, got {type(value).__name__}"
            )

        return dt.strftime(self.output_format)


class CustomTransformer(Transformer):
    """Wraps an arbitrary callable (value) -> transformed_value."""

    name = "custom"

    def __init__(self, func: Callable[[Any], Any], name: Optional[str] = None) -> None:
        self.func = func
        if name:
            self.name = name

    def transform(self, value: Any, field_name: Optional[str] = None) -> Any:
        try:
            return self.func(value)
        except Exception as e:
            raise TransformationError(self.name, field_name, value, f"Custom transformer error: {e}") from e


class ChainedTransformer(Transformer):
    """Applies a sequence of transformers in order."""

    name = "chained"

    def __init__(self, transformers: List[Transformer]) -> None:
        self.transformers = list(transformers)

    def transform(self, value: Any, field_name: Optional[str] = None) -> Any:
        current = value
        for t in self.transformers:
            current = t.transform(current, field_name)
        return current
