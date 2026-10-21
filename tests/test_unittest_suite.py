"""
tests.test_unittest_suite
~~~~~~~~~~~~~~~~~~~~~~~~~

Standard library `unittest.TestCase` implementation for environments without pytest.
Validates core functionality of datapype using native unittest fixtures, subtests,
and assertion methods.
"""

from datetime import datetime
import unittest

from datapype.dataset import Dataset
from datapype.exceptions import (
    FieldValidationError,
    PipelineExecutionError,
    SchemaDefinitionError,
    TransformationError,
    ValidationError,
)
from datapype.parsers import CSVParser, JSONParser
from datapype.pipeline import Pipeline
from datapype.schema import Field, Schema
from datapype.transformers import DateFormat, RoundNumber, ToLowerCase, ToTitleCase, Trim
from datapype.types import BooleanType, DateTimeType, FloatType, IntegerType, StringType
from datapype.validators import Email, InChoices, Length, Positive, Range, Required


class TestDataPypeUnittest(unittest.TestCase):
    """Native unittest test suite for datapype."""

    def setUp(self) -> None:
        """Initialize reusable schemas and datasets."""
        self.user_schema = Schema([
            Field("id", data_type=IntegerType(), required=True, validators=[Positive()]),
            Field("name", data_type=StringType(), required=True, transformers=[Trim(), ToTitleCase()]),
            Field("email", data_type=StringType(), required=True, transformers=[Trim(), ToLowerCase()], validators=[Email()]),
            Field("age", data_type=IntegerType(), required=True, validators=[Range(min_value=18, max_value=120)]),
            Field("salary", data_type=FloatType(), required=True, transformers=[RoundNumber(2)]),
        ])

    def test_types_coercion_and_strictness(self) -> None:
        int_t = IntegerType()
        self.assertEqual(int_t.coerce("42"), 42)
        self.assertEqual(int_t.coerce(100), 100)
        with self.assertRaises(TypeError):
            int_t.coerce(True)
        with self.assertRaises(TypeError):
            int_t.coerce("42", strict=True)

        bool_t = BooleanType()
        self.assertTrue(bool_t.coerce("yes"))
        self.assertFalse(bool_t.coerce("false"))

        float_t = FloatType()
        self.assertAlmostEqual(float_t.coerce("3.1415"), 3.1415)

    def test_validators(self) -> None:
        req = Required()
        self.assertTrue(req.is_valid("test"))
        self.assertFalse(req.is_valid(None))

        rng = Range(min_value=10, max_value=20)
        self.assertTrue(rng.is_valid(15))
        self.assertFalse(rng.is_valid(5))
        self.assertFalse(rng.is_valid(25))

        email_val = Email()
        self.assertTrue(email_val.is_valid("user@example.com"))
        self.assertFalse(email_val.is_valid("not_an_email"))

    def test_transformers(self) -> None:
        trim = Trim()
        self.assertEqual(trim.transform("  padded  "), "padded")

        lower = ToLowerCase()
        self.assertEqual(lower.transform("HELLO"), "hello")

        rnd = RoundNumber(2)
        self.assertEqual(rnd.transform(3.14159), 3.14)
        self.assertEqual(rnd.transform("123.456"), 123.46)

    def test_schema_record_validation(self) -> None:
        raw = {
            "id": "101",
            "name": "  john doe  ",
            "email": "JOHN.DOE@CORP.COM",
            "age": "32",
            "salary": "75200.556",
        }
        clean = self.user_schema.validate_record(raw)
        self.assertEqual(clean["id"], 101)
        self.assertEqual(clean["name"], "John Doe")
        self.assertEqual(clean["email"], "john.doe@corp.com")
        self.assertEqual(clean["age"], 32)
        self.assertEqual(clean["salary"], 75200.56)

    def test_schema_validation_failure(self) -> None:
        invalid_raw = {
            "id": "-1",            # Fails Positive
            "name": "",            # Fails Required
            "email": "bad_email",  # Fails Email
            "age": "15",           # Fails Range >= 18
            "salary": "abc",       # Fails FloatType
        }
        with self.assertRaises(ValidationError) as ctx:
            self.user_schema.validate_record(invalid_raw)
        self.assertGreaterEqual(len(ctx.exception.errors), 4)

    def test_dataset_operations(self) -> None:
        ds = Dataset([
            {"id": 1, "dept": "Eng", "score": 90},
            {"id": 2, "dept": "Sales", "score": 75},
            {"id": 3, "dept": "Eng", "score": 85},
        ])
        # Filter
        eng = ds.filter(lambda r: r["dept"] == "Eng")
        self.assertEqual(len(eng), 2)

        # Mutate
        doubled = ds.mutate("doubled_score", lambda r: r["score"] * 2)
        self.assertEqual(doubled[0]["doubled_score"], 180)

        # Group and aggregate
        grouped = ds.group_by("dept").aggregate({"score": "avg"})
        self.assertEqual(len(grouped), 2)
        eng_row = next(r for r in grouped if r["dept"] == "Eng")
        self.assertEqual(eng_row["score_avg"], 87.5)

    def test_parsers_csv_and_json(self) -> None:
        csv_content = "id,val\n1,10\n2,20\n"
        csv_parser = CSVParser()
        ds_csv = csv_parser.parse_string(csv_content)
        self.assertEqual(len(ds_csv), 2)
        self.assertEqual(ds_csv[0]["val"], "10")

        json_content = '[{"a": 1}, {"a": 2}]'
        json_parser = JSONParser()
        ds_json = json_parser.parse_string(json_content)
        self.assertEqual(len(ds_json), 2)

    def test_pipeline_integration(self) -> None:
        csv_data = "id,name,email,age,salary\n1,Alice,alice@example.com,28,60000\n"
        res = (
            Pipeline.create("test_pipe")
            .extract_csv(csv_data)
            .validate(self.user_schema)
            .execute()
        )
        self.assertTrue(res.is_successful)
        self.assertEqual(res.row_count, 1)
        self.assertEqual(res.dataset[0]["name"], "Alice")


if __name__ == "__main__":
    unittest.main()
