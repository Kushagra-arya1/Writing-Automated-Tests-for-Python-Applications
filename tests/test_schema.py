"""
tests.test_schema
~~~~~~~~~~~~~~~~~

Unit tests for datapype.schema (Field and Schema).
Validates schema definition integrity, field lifecycles, error accumulation vs fail-fast,
unknown field handling, and batch validation.
"""

import pytest

from datapype.exceptions import (
    FieldValidationError,
    SchemaDefinitionError,
    ValidationError,
)
from datapype.schema import Field, Schema
from datapype.transformers import ToLowerCase, Trim
from datapype.types import BooleanType, FloatType, IntegerType, StringType
from datapype.validators import Email, Length, Positive, Range


class TestFieldDefinition:
    """Tests for Field class."""

    def test_invalid_field_names(self):
        with pytest.raises(SchemaDefinitionError):
            Field("")
        with pytest.raises(SchemaDefinitionError):
            Field("   ")

    def test_field_processing_lifecycle(self):
        f = Field(
            "username",
            data_type=StringType(),
            required=True,
            transformers=[Trim(), ToLowerCase()],
            validators=[Length(min_length=3, max_length=15)],
        )

        val, errors = f.process("   JohnDoe   ")
        assert val == "johndoe"
        assert len(errors) == 0

    def test_default_value_static_and_callable(self):
        f_static = Field("role", data_type=StringType(), required=False, default="guest")
        val1, errs1 = f_static.process(None)
        assert val1 == "guest"
        assert len(errs1) == 0

        f_callable = Field("counter", data_type=IntegerType(), required=False, default=lambda: 99)
        val2, errs2 = f_callable.process(None)
        assert val2 == 99
        assert len(errs2) == 0

    def test_field_type_coercion_failure(self):
        f = Field("age", data_type=IntegerType(), required=True)
        val, errors = f.process("invalid_age")
        assert len(errors) == 1
        assert errors[0].rule == "type_integer"


class TestSchemaValidation:
    """Tests for Schema class."""

    @pytest.fixture
    def basic_schema(self) -> Schema:
        return Schema([
            Field("id", data_type=IntegerType(), required=True, validators=[Positive()]),
            Field("name", data_type=StringType(), required=True, transformers=[Trim()]),
            Field("score", data_type=FloatType(), required=False, default=0.0),
        ])

    def test_schema_init_validations(self):
        with pytest.raises(SchemaDefinitionError, match="at least one field"):
            Schema([])
        with pytest.raises(SchemaDefinitionError):
            Schema(["not_a_field"])

    def test_valid_record_processing(self, basic_schema):
        raw = {"id": "100", "name": "  Tester  ", "score": "88.5"}
        clean = basic_schema.validate_record(raw)
        assert clean == {"id": 100, "name": "Tester", "score": 88.5}

    def test_default_value_applied_when_missing(self, basic_schema):
        raw = {"id": 1, "name": "Solo"}
        clean = basic_schema.validate_record(raw)
        assert clean["score"] == 0.0

    def test_strip_unknown_fields_by_default(self, basic_schema):
        raw = {"id": 1, "name": "Alice", "extra_col": "discard_me"}
        clean = basic_schema.validate_record(raw)
        assert "extra_col" not in clean

    def test_allow_unknown_fields(self):
        schema = Schema(
            [Field("id", data_type=IntegerType())],
            allow_unknown=True,
        )
        clean = schema.validate_record({"id": 10, "meta_tag": "vip"})
        assert clean == {"id": 10, "meta_tag": "vip"}

    def test_reject_unknown_fields(self):
        schema = Schema(
            [Field("id", data_type=IntegerType())],
            allow_unknown=False,
            strip_unknown=False,
        )
        with pytest.raises(ValidationError) as exc:
            schema.validate_record({"id": 1, "rogue_field": "intruder"})
        assert "unknown_field" in [e.rule for e in exc.value.errors]

    def test_error_accumulation_vs_fail_fast(self):
        schema_accumulate = Schema(
            [
                Field("id", data_type=IntegerType(), required=True, validators=[Positive()]),
                Field("email", data_type=StringType(), required=True, validators=[Email()]),
            ],
            fail_fast=False,
        )
        # Both fields invalid: id is negative, email is invalid
        with pytest.raises(ValidationError) as exc_accum:
            schema_accumulate.validate_record({"id": -5, "email": "bad_email"})
        assert len(exc_accum.value.errors) == 2

        schema_fail_fast = Schema(
            [
                Field("id", data_type=IntegerType(), required=True, validators=[Positive()]),
                Field("email", data_type=StringType(), required=True, validators=[Email()]),
            ],
            fail_fast=True,
        )
        with pytest.raises(ValidationError) as exc_fast:
            schema_fail_fast.validate_record({"id": -5, "email": "bad_email"})
        assert len(exc_fast.value.errors) == 1

    def test_non_dict_record_raises(self, basic_schema):
        with pytest.raises(ValidationError, match="Expected dict"):
            basic_schema.validate_record(["not", "a", "dict"])

    def test_validate_batch(self, basic_schema):
        batch = [
            {"id": "1", "name": "Valid 1"},
            {"id": "-99", "name": "Negative ID"},  # Invalid
            {"id": "2", "name": "Valid 2"},
            {"id": "abc", "name": "Bad Type"},     # Invalid
        ]
        valid_records, errors = basic_schema.validate_batch(batch)
        assert len(valid_records) == 2
        assert len(errors) == 2
        assert valid_records[0]["id"] == 1
        assert valid_records[1]["id"] == 2
        assert errors[0].record_index == 1
        assert errors[1].record_index == 3

    def test_validation_error_to_dict_serialization(self, basic_schema):
        try:
            basic_schema.validate_record({"id": -10, "name": ""})
        except ValidationError as e:
            serialized = e.to_dict()
            assert serialized["error_count"] >= 1
            assert "errors" in serialized
            assert isinstance(serialized["errors"], list)
