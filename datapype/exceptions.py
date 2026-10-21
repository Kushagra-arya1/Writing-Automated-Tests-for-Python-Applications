"""
datapype.exceptions
~~~~~~~~~~~~~~~~~~~

Custom exception hierarchy for the datapype library.
Provides rich contextual error diagnostics for data validation,
transformation, schema enforcement, and pipeline execution.
"""

from typing import Any, List, Optional


class DataPypeError(Exception):
    """Base class for all exceptions in datapype."""
    pass


class SchemaDefinitionError(DataPypeError):
    """Raised when a schema is misconfigured or has invalid field definitions."""
    pass


class FieldValidationError(DataPypeError):
    """
    Raised when an individual field fails a validation or type constraint.

    Attributes:
        field: The name of the field that failed.
        value: The invalid value encountered.
        rule: The name of the validator rule that was violated.
        message: Descriptive error explanation.
    """

    def __init__(self, field: str, value: Any, rule: str, message: str) -> None:
        self.field = field
        self.value = value
        self.rule = rule
        self.message = message
        super().__init__(f"Field '{field}' failed rule '{rule}': {message} (received: {value!r})")


class ValidationError(DataPypeError):
    """
    Raised when one or more record-level or schema validations fail.

    Attributes:
        errors: A list of FieldValidationError instances describing each failure.
        record_index: The index of the record in a batch/stream (if applicable).
    """

    def __init__(self, errors: List[FieldValidationError], record_index: Optional[int] = None) -> None:
        self.errors = errors
        self.record_index = record_index
        idx_str = f" at record index {record_index}" if record_index is not None else ""
        error_msgs = "; ".join(str(e) for e in errors)
        super().__init__(f"Validation failed{idx_str} with {len(errors)} error(s): [{error_msgs}]")

    def to_dict(self) -> dict:
        """Returns a serializable dictionary representation of the validation errors."""
        return {
            "record_index": self.record_index,
            "error_count": len(self.errors),
            "errors": [
                {
                    "field": err.field,
                    "value": repr(err.value),
                    "rule": err.rule,
                    "message": err.message,
                }
                for err in self.errors
            ],
        }


class TransformationError(DataPypeError):
    """Raised when a transformation cannot be applied to a value or record."""

    def __init__(self, transformer: str, field: Optional[str], value: Any, message: str) -> None:
        self.transformer = transformer
        self.field = field
        self.value = value
        self.message = message
        field_str = f" on field '{field}'" if field else ""
        super().__init__(f"Transformation '{transformer}'{field_str} failed: {message} (value: {value!r})")


class ParserError(DataPypeError):
    """Raised when parsing tabular data (CSV, JSON) fails."""

    def __init__(self, format_name: str, line_number: Optional[int], message: str) -> None:
        self.format_name = format_name
        self.line_number = line_number
        self.message = message
        loc_str = f" at line {line_number}" if line_number is not None else ""
        super().__init__(f"{format_name} parser error{loc_str}: {message}")


class PipelineExecutionError(DataPypeError):
    """Raised when an error occurs during ETL pipeline execution."""

    def __init__(self, stage_name: str, message: str, original_error: Optional[Exception] = None) -> None:
        self.stage_name = stage_name
        self.message = message
        self.original_error = original_error
        cause_str = f" (caused by {type(original_error).__name__}: {original_error})" if original_error else ""
        super().__init__(f"Pipeline failed at stage '{stage_name}': {message}{cause_str}")
