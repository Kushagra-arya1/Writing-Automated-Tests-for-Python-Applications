"""
tests.test_edge_cases
~~~~~~~~~~~~~~~~~~~~~

Rigorous edge cases, boundary value analysis (BVA), and stress tests for datapype.
Covers Unicode, emojis, extreme numbers, leap years, empty datasets, null-heavy payloads,
and unusual delimiters.
"""

from datetime import datetime
import io
import pytest

from datapype.dataset import Dataset
from datapype.parsers import CSVParser, JSONParser
from datapype.pipeline import Pipeline
from datapype.schema import Field, Schema
from datapype.transformers import DateFormat, RoundNumber, ToLowerCase, Trim
from datapype.types import BooleanType, DateTimeType, FloatType, IntegerType, StringType
from datapype.validators import Email, Length, Range, Required


class TestUnicodeAndSpecialCharacters:
    """Tests handling of international scripts, accents, emojis, and symbols."""

    def test_multilingual_and_emoji_strings(self):
        f = Field("text", data_type=StringType(), transformers=[Trim()], validators=[Length(min_length=1)])
        # Japanese, Arabic, German, Accents, Emojis
        samples = ["こんにちは", "مرحبا", "Größenmaßstäbe", "Renée François", "🚀 Launch 🔥"]
        for sample in samples:
            val, errs = f.process(f"  {sample}  ")
            assert len(errs) == 0
            assert val == sample

    def test_csv_parser_with_utf8_accents_and_emojis(self):
        csv_text = (
            "id,name,comment\n"
            "1,José Müller,🚀 Superb!\n"
            "2,田中 太郎,素晴らしい\n"
        )
        parser = CSVParser()
        ds = parser.parse_string(csv_text)
        assert len(ds) == 2
        assert ds[0]["name"] == "José Müller"
        assert ds[0]["comment"] == "🚀 Superb!"
        assert ds[1]["name"] == "田中 太郎"


class TestExtremeNumericBoundaries:
    """Tests handling of astronomical numbers, float scientific notation, and precision."""

    def test_astronomical_integers(self):
        t = IntegerType()
        huge_int = 10**40
        assert t.coerce(huge_int) == huge_int
        assert t.coerce(str(huge_int)) == huge_int

    def test_scientific_notation_floats(self):
        t = FloatType()
        small_float = 1.25e-12
        large_float = 9.87e15
        assert t.coerce("1.25e-12") == pytest.approx(small_float)
        assert t.coerce("9.87e15") == pytest.approx(large_float)

    def test_range_boundaries_with_floats(self):
        r = Range(min_value=0.000001, max_value=0.000002)
        r.validate(0.0000015, "val")
        r.validate(0.000001, "val")
        r.validate(0.000002, "val")
        with pytest.raises(Exception):
            r.validate(0.0000009, "val")
        with pytest.raises(Exception):
            r.validate(0.0000021, "val")


class TestDateTimeEdgeCases:
    """Tests for leap years, end-of-year, and microseconds."""

    def test_leap_year_validity(self):
        t = DateTimeType(date_format="%Y-%m-%d")
        # 2024 is a leap year, 2023 is not
        dt_leap = t.coerce("2024-02-29")
        assert dt_leap == datetime(2024, 2, 29)

        with pytest.raises(ValueError):
            t.coerce("2023-02-29")

    def test_end_of_year_and_time_precision(self):
        t = DateTimeType()
        dt = t.coerce("2025-12-31T23:59:59.999999")
        assert dt.year == 2025
        assert dt.microsecond == 999999


class TestEmptyAndNullPayloads:
    """Tests resilience on empty datasets, null rows, and missing attributes."""

    def test_empty_dataset_operations(self):
        ds = Dataset([])
        assert ds.filter(lambda r: True) == ds
        assert ds.select("col_a", "col_b").columns == []
        assert ds.drop("col_a") == ds
        assert ds.sort_by("id") == ds
        assert ds.drop_duplicates() == ds
        assert ds.head(10) == ds
        assert ds.tail(10) == ds

        # Empty aggregations
        aggs = ds.aggregate({"val": "sum", "val2": "avg", "val3": "count", "val4": "min"})
        assert aggs["val_sum"] is None
        assert aggs["val2_avg"] is None
        assert aggs["val3_count"] == 0
        assert aggs["val4_min"] is None

    def test_join_on_empty_datasets(self):
        ds_empty = Dataset([])
        ds_other = Dataset([{"id": 1, "val": "x"}])

        # Left join with empty right
        assert len(ds_other.join(ds_empty, on="id", how="left")) == 1
        # Inner join with empty right
        assert len(ds_other.join(ds_empty, on="id", how="inner")) == 0

    def test_all_null_values_in_record(self):
        schema = Schema([
            Field("id", data_type=IntegerType(), required=False, default=0),
            Field("name", data_type=StringType(), required=False, default="Anonymous"),
            Field("active", data_type=BooleanType(), required=False, default=False),
        ])
        clean = schema.validate_record({"id": None, "name": None, "active": None})
        assert clean == {"id": 0, "name": "Anonymous", "active": False}


class TestHighVolumeAndStress:
    """Tests processing throughput with generated records."""

    def test_high_volume_batch_validation_and_aggregation(self):
        # Generate 2,000 records
        raw_records = [
            {"id": i, "name": f"User_{i}", "score": (i % 100) * 1.5, "active": "true" if i % 2 == 0 else "false"}
            for i in range(1, 2001)
        ]

        schema = Schema([
            Field("id", data_type=IntegerType(), required=True),
            Field("name", data_type=StringType(), required=True),
            Field("score", data_type=FloatType(), required=True),
            Field("active", data_type=BooleanType(), required=True),
        ])

        valid, errs = schema.validate_batch(raw_records)
        assert len(valid) == 2000
        assert len(errs) == 0

        ds = Dataset(valid)
        assert len(ds) == 2000

        # Run multi-operation pipeline
        even_actives = ds.filter(lambda r: r["active"] and r["score"] > 50)
        assert len(even_actives) > 0

        stats = ds.aggregate({"score": "avg", "id": "count"})
        assert stats["id_count"] == 2000
        assert stats["score_avg"] > 0
