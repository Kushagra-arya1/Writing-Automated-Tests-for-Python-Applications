"""
datapype.schema
~~~~~~~~~~~~~~~

Declarative schema definition and record validation engine.
Supports field transformations, type coercion, composable validations,
and error accumulation or fail-fast policies.
"""

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from datapype.exceptions import (
    FieldValidationError,
    SchemaDefinitionError,
    TransformationError,
    ValidationError,
)
from datapype.transformers import Transformer
from datapype.types import AnyType, DataType
from datapype.validators import Required, Validator


class Field:
    """
    Defines a schema field with typing, default value, transformations, and validations.

    Processing lifecycle for a field:
    1. Default value substitution (if value is missing or None).
    2. Transformations (e.g. trim, case conversion).
    3. Type coercion / validation.
    4. Custom and constraint validators (range, length, regex, etc.).
    """

    def __init__(
        self,
        name: str,
        data_type: Optional[DataType] = None,
        required: bool = True,
        default: Any = None,
        transformers: Optional[Sequence[Transformer]] = None,
        validators: Optional[Sequence[Validator]] = None,
        description: Optional[str] = None,
    ) -> None:
        if not name or not isinstance(name, str) or not name.strip():
            raise SchemaDefinitionError(f"Field name must be a non-empty string, got {name!r}")

        self.name = name.strip()
        self.data_type = data_type or AnyType()
        self.required = required
        self.default = default
        self.transformers = list(transformers or [])
        self.validators = list(validators or [])
        self.description = description

        # If required is True and no explicit Required validator is in validators, prepend one
        if self.required:
            has_req = any(isinstance(v, Required) for v in self.validators)
            if not has_req:
                self.validators.insert(0, Required())

    def process(self, value: Any, strict: bool = False) -> Tuple[Any, List[FieldValidationError]]:
        """
        Executes the processing lifecycle for this field.

        Returns:
            Tuple of (processed_value, list_of_validation_errors).
        """
        errors: List[FieldValidationError] = []

        # 1. Default value substitution
        if value is None and self.default is not None:
            value = self.default() if callable(self.default) else self.default

        # 2. Transformers
        if value is not None:
            for t in self.transformers:
                try:
                    value = t.transform(value, self.name)
                except TransformationError as e:
                    errors.append(FieldValidationError(self.name, value, t.name, e.message))
                    return value, errors

        # 3. Type Coercion / Validation
        if value is not None:
            try:
                value = self.data_type.coerce(value, strict=strict)
            except (TypeError, ValueError) as e:
                errors.append(
                    FieldValidationError(
                        self.name,
                        value,
                        f"type_{self.data_type.name}",
                        f"Value cannot be coerced to {self.data_type.name}: {e}",
                    )
                )
                return value, errors

        # 4. Validators
        for v in self.validators:
            try:
                v.validate(value, self.name)
            except FieldValidationError as e:
                errors.append(e)

        return value, errors


class Schema:
    """
    Represents a tabular or record schema with configurable error policies.

    Args:
        fields: A sequence or dictionary of Field objects.
        allow_unknown: If True, fields in the input not defined in the schema are preserved.
        strip_unknown: If True and allow_unknown is False, unmodeled fields are dropped silently.
                       If False and allow_unknown is False, unmodeled fields raise an error.
        fail_fast: If True, raises ValidationError on the first encountered error.
                   If False, accumulates all errors across all fields.
        strict_types: If True, rejects implicit type coercions (e.g. "123" to int).
    """

    def __init__(
        self,
        fields: Union[Sequence[Field], Dict[str, Field]],
        allow_unknown: bool = False,
        strip_unknown: bool = True,
        fail_fast: bool = False,
        strict_types: bool = False,
    ) -> None:
        if isinstance(fields, dict):
            self.fields = dict(fields)
        elif isinstance(fields, (list, tuple)):
            self.fields = {}
            for item in fields:
                if not isinstance(item, Field):
                    raise SchemaDefinitionError(f"Expected Field instance, got {type(item).__name__}")
                self.fields[item.name] = item
        else:
            raise SchemaDefinitionError("Fields must be a list or dict of Field instances")

        if not self.fields:
            raise SchemaDefinitionError("Schema must define at least one field")

        for name, field in self.fields.items():
            if not isinstance(field, Field):
                raise SchemaDefinitionError(f"Field '{name}' must be an instance of Field, got {type(field).__name__}")

        self.allow_unknown = allow_unknown
        self.strip_unknown = strip_unknown
        self.fail_fast = fail_fast
        self.strict_types = strict_types

    def validate_record(self, record: Dict[str, Any], record_index: Optional[int] = None) -> Dict[str, Any]:
        """
        Validates and transforms a single record dictionary.

        Returns:
            The sanitized, coerced, transformed record dictionary.

        Raises:
            ValidationError: If one or more field validations fail.
        """
        if not isinstance(record, dict):
            raise ValidationError(
                [FieldValidationError("__record__", record, "type", f"Expected dict, got {type(record).__name__}")],
                record_index=record_index,
            )

        processed_record: Dict[str, Any] = {}
        errors: List[FieldValidationError] = []

        # Check unknown keys
        input_keys = set(record.keys())
        schema_keys = set(self.fields.keys())
        unknown_keys = input_keys - schema_keys

        if unknown_keys:
            if not self.allow_unknown and not self.strip_unknown:
                for uk in sorted(unknown_keys):
                    err = FieldValidationError(uk, record[uk], "unknown_field", f"Field '{uk}' is not recognized")
                    errors.append(err)
                    if self.fail_fast:
                        raise ValidationError(errors, record_index=record_index)

        # Process modeled fields
        for field_name, field in self.fields.items():
            raw_val = record.get(field_name, None)
            processed_val, field_errors = field.process(raw_val, strict=self.strict_types)

            if field_errors:
                errors.extend(field_errors)
                if self.fail_fast:
                    raise ValidationError(errors, record_index=record_index)

            processed_record[field_name] = processed_val

        # If allow_unknown is True, retain unknown fields
        if self.allow_unknown and unknown_keys:
            for uk in unknown_keys:
                processed_record[uk] = record[uk]

        if errors:
            raise ValidationError(errors, record_index=record_index)

        return processed_record

    def validate_batch(
        self, records: Iterable[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[ValidationError]]:
        """
        Validates an iterable of records.
        Does not halt on individual row errors, separating valid records
        from invalid records for dead-letter queuing or error reporting.

        Returns:
            Tuple of (valid_records, validation_errors).
        """
        valid_records: List[Dict[str, Any]] = []
        errors: List[ValidationError] = []

        for idx, rec in enumerate(records):
            try:
                clean_rec = self.validate_record(rec, record_index=idx)
                valid_records.append(clean_rec)
            except ValidationError as e:
                errors.append(e)

        return valid_records, errors
