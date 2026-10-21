"""
datapype.types
~~~~~~~~~~~~~~

Type definitions, coercions, and casting utilities for datapype.
Supports strict mode and lenient coercion modes for robust data ingestion.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, List, Optional, Set, Union


class DataType(ABC):
    """Abstract base class for all datapype data types."""

    name: str = "any"

    @abstractmethod
    def coerce(self, value: Any, strict: bool = False) -> Any:
        """
        Coerces or validates the value against the data type.

        Args:
            value: The input value to coerce.
            strict: If True, disallows lossy or implicit string conversions.

        Returns:
            The coerced or validated value.

        Raises:
            TypeError or ValueError: If the value cannot be coerced or validated.
        """
        pass

    def is_valid(self, value: Any, strict: bool = False) -> bool:
        """Checks if a value is valid according to this data type."""
        try:
            self.coerce(value, strict=strict)
            return True
        except (TypeError, ValueError):
            return False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, self.__class__)


class AnyType(DataType):
    """Allows any value without type coercion or rejection."""

    name = "any"

    def coerce(self, value: Any, strict: bool = False) -> Any:
        return value


class IntegerType(DataType):
    """
    Validates or coerces values into integers.

    In strict mode, booleans are rejected even though bool is a subclass of int in Python.
    In non-strict mode, float values with zero fractional part (e.g. 42.0) and
    valid integer strings (e.g. "42", "-10") are coerced to int.
    """

    name = "integer"

    def coerce(self, value: Any, strict: bool = False) -> int:
        if isinstance(value, bool):
            raise TypeError("Boolean value cannot be treated as integer")

        if isinstance(value, int):
            return value

        if strict:
            raise TypeError(f"Expected integer in strict mode, got {type(value).__name__}")

        if isinstance(value, float):
            if value.is_integer():
                return int(value)
            raise ValueError(f"Cannot losslessly convert float {value} with fractional part to integer")

        if isinstance(value, str):
            val_clean = value.strip()
            if not val_clean:
                raise ValueError("Cannot coerce empty string to integer")
            try:
                return int(val_clean)
            except ValueError:
                # Check if it was formatted like a float integer string e.g. "42.0"
                try:
                    f = float(val_clean)
                    if f.is_integer():
                        return int(f)
                except ValueError:
                    pass
                raise ValueError(f"Cannot coerce string '{value}' to integer")

        raise TypeError(f"Unsupported type {type(value).__name__} for integer coercion")


class FloatType(DataType):
    """
    Validates or coerces values into floating-point numbers.
    """

    name = "float"

    def __init__(self, allow_nan: bool = False, allow_inf: bool = False) -> None:
        self.allow_nan = allow_nan
        self.allow_inf = allow_inf

    def coerce(self, value: Any, strict: bool = False) -> float:
        if isinstance(value, bool):
            raise TypeError("Boolean value cannot be treated as float")

        if isinstance(value, (int, float)):
            f_val = float(value)
        elif not strict and isinstance(value, str):
            val_clean = value.strip()
            if not val_clean:
                raise ValueError("Cannot coerce empty string to float")
            try:
                f_val = float(val_clean)
            except ValueError as e:
                raise ValueError(f"Cannot coerce string '{value}' to float") from e
        else:
            raise TypeError(f"Cannot coerce {type(value).__name__} to float (strict={strict})")

        import math
        if math.isnan(f_val) and not self.allow_nan:
            raise ValueError("NaN values are not allowed for this FloatType")
        if math.isinf(f_val) and not self.allow_inf:
            raise ValueError("Infinity values are not allowed for this FloatType")

        return f_val


class StringType(DataType):
    """
    Validates or coerces values into strings.
    """

    name = "string"

    def __init__(self, strip_whitespace: bool = False) -> None:
        self.strip_whitespace = strip_whitespace

    def coerce(self, value: Any, strict: bool = False) -> str:
        if strict and not isinstance(value, str):
            raise TypeError(f"Expected str in strict mode, got {type(value).__name__}")

        res = str(value) if not isinstance(value, str) else value
        if self.strip_whitespace:
            res = res.strip()
        return res


class BooleanType(DataType):
    """
    Validates or coerces values into booleans.
    Supports customary string truth values:
      True:  {"true", "1", "yes", "y", "t", "on"}
      False: {"false", "0", "no", "n", "f", "off"}
    """

    name = "boolean"

    TRUE_STRINGS: Set[str] = {"true", "1", "yes", "y", "t", "on"}
    FALSE_STRINGS: Set[str] = {"false", "0", "no", "n", "f", "off"}

    def coerce(self, value: Any, strict: bool = False) -> bool:
        if isinstance(value, bool):
            return value

        if strict:
            raise TypeError(f"Expected bool in strict mode, got {type(value).__name__}")

        if isinstance(value, (int, float)):
            if value == 1:
                return True
            if value == 0:
                return False
            raise ValueError(f"Numeric value {value} cannot be unambiguously coerced to boolean")

        if isinstance(value, str):
            val_lower = value.strip().lower()
            if val_lower in self.TRUE_STRINGS:
                return True
            if val_lower in self.FALSE_STRINGS:
                return False
            raise ValueError(f"String '{value}' is not a recognized boolean representation")

        raise TypeError(f"Unsupported type {type(value).__name__} for boolean coercion")


class DateTimeType(DataType):
    """
    Validates or coerces strings/timestamps into datetime objects.
    Supports ISO format and optional custom strptime format patterns.
    """

    name = "datetime"

    def __init__(self, date_format: Optional[str] = None) -> None:
        self.date_format = date_format

    def coerce(self, value: Any, strict: bool = False) -> datetime:
        if isinstance(value, datetime):
            return value

        if strict:
            raise TypeError(f"Expected datetime in strict mode, got {type(value).__name__}")

        if isinstance(value, str):
            val_clean = value.strip()
            if not val_clean:
                raise ValueError("Cannot coerce empty string to datetime")

            if self.date_format:
                try:
                    return datetime.strptime(val_clean, self.date_format)
                except ValueError as e:
                    raise ValueError(f"Date string '{val_clean}' does not match format '{self.date_format}'") from e

            # Fallback to ISO format parsing
            try:
                return datetime.fromisoformat(val_clean)
            except ValueError:
                # Try common fallback patterns
                common_formats = [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d",
                    "%d/%m/%Y",
                    "%m/%d/%Y",
                    "%Y/%m/%d",
                ]
                for fmt in common_formats:
                    try:
                        return datetime.strptime(val_clean, fmt)
                    except ValueError:
                        pass
                raise ValueError(f"Cannot parse '{val_clean}' as datetime with any known format")

        raise TypeError(f"Cannot coerce {type(value).__name__} to datetime")


class ListType(DataType):
    """
    Validates or coerces values into a list, with optional item-type validation.
    """

    name = "list"

    def __init__(self, item_type: Optional[DataType] = None, delimiter: str = ",") -> None:
        self.item_type = item_type
        self.delimiter = delimiter

    def coerce(self, value: Any, strict: bool = False) -> List[Any]:
        if isinstance(value, list):
            items = value
        elif isinstance(value, (tuple, set)):
            items = list(value)
        elif not strict and isinstance(value, str):
            val_clean = value.strip()
            if not val_clean:
                items = []
            else:
                items = [item.strip() for item in val_clean.split(self.delimiter)]
        else:
            raise TypeError(f"Cannot coerce {type(value).__name__} to list")

        if self.item_type:
            return [self.item_type.coerce(item, strict=strict) for item in items]
        return items
