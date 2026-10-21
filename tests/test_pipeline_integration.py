"""
tests.test_pipeline_integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration tests for the complete datapype ETL pipeline orchestrator.
Tests end-to-end ingestion, schema validation, transformation, rejection logging,
relational joins, metrics telemetry, and exporter pipelines.
"""

import pytest

from datapype.dataset import Dataset
from datapype.exceptions import PipelineExecutionError
from datapype.pipeline import Pipeline, PipelineResult
from datapype.schema import Field, Schema
from datapype.transformers import RoundNumber, ToLowerCase, ToTitleCase, Trim
from datapype.types import BooleanType, FloatType, IntegerType, StringType
from datapype.validators import Email, InChoices, Positive, Range


class TestETLPipelineIntegration:
    """Full integration tests connecting extraction, validation, transformation, and export."""

    def test_end_to_end_csv_pipeline_with_dirty_data(self, sample_raw_users_csv, user_schema):
        # Build and execute end-to-end pipeline
        pipeline = (
            Pipeline.create(name="user_etl_pipeline")
            .extract_csv(sample_raw_users_csv)
            .validate(user_schema, drop_invalid=True)
            .filter(lambda r: r["age"] >= 25, name="filter_adults")
            .mutate("tax", lambda r: round(r["salary"] * 0.2, 2))
            .mutate("net_salary", lambda r: round(r["salary"] - r["tax"], 2))
            .sort_by("salary", reverse=True)
        )

        result: PipelineResult = pipeline.execute()
        assert result.is_successful is True
        assert result.rejected_count == 0
        assert result.name == "user_etl_pipeline"
        assert len(result.stages_executed) >= 5

        # Verify filtered and transformed output
        ds = result.dataset
        # Out of 5 users: Charlie Brown is 19 (< 25) -> filtered out.
        # Remaining 4: Alice (29), Bob (45), Dana (38), Evan (52)
        assert len(ds) == 4

        # Sorted by salary descending:
        # Dana (89000.75), Alice (75000.50), Bob (62000.00), Evan (58000.00)
        assert ds[0]["name"] == "Dana Scully"
        assert ds[0]["salary"] == 89000.75
        assert ds[0]["tax"] == 17800.15
        assert ds[0]["net_salary"] == 71200.60
        assert ds[0]["active"] is True

        assert ds[1]["name"] == "Alice Smith"
        assert ds[2]["name"] == "Bob Jones"
        assert ds[3]["name"] == "Evan Wright"

    def test_pipeline_with_validation_rejections_collected(self):
        # CSV with 2 valid records and 2 invalid records
        mixed_csv = (
            "id,name,email,score\n"
            "1,Alice,alice@corp.com,95.5\n"
            "2,Bob,not_an_email,80.0\n"       # Invalid email
            "-3,Charlie,charlie@corp.com,88\n" # Negative ID
            "4,Dana,dana@corp.com,92.0\n"
        )

        schema = Schema([
            Field("id", data_type=IntegerType(), required=True, validators=[Positive()]),
            Field("name", data_type=StringType(), required=True),
            Field("email", data_type=StringType(), required=True, validators=[Email()]),
            Field("score", data_type=FloatType(), required=True),
        ])

        pipeline = (
            Pipeline.create("rejection_audit_pipeline")
            .extract_csv(mixed_csv)
            .validate(schema, drop_invalid=True)
        )

        result = pipeline.execute()

        assert result.row_count == 2
        assert result.rejected_count == 2
        assert result.is_successful is False

        # Check rejected records contain expected error metadata
        rejections = result.rejected_records
        assert rejections[0].record_index == 1  # Bob
        assert rejections[1].record_index == 2  # Charlie

        # Check clean records
        clean_ids = [r["id"] for r in result.dataset]
        assert clean_ids == [1, 4]

    def test_pipeline_strict_validation_abort(self):
        bad_csv = "id,name\n1,Alice\n-99,BadID\n"
        schema = Schema([
            Field("id", data_type=IntegerType(), validators=[Positive()]),
            Field("name", data_type=StringType()),
        ])

        pipeline = (
            Pipeline.create("strict_pipeline")
            .extract_csv(bad_csv)
            .validate(schema, drop_invalid=False)  # Abort on invalid
        )

        with pytest.raises(PipelineExecutionError) as exc:
            pipeline.execute()

        assert exc.value.stage_name == "schema_validation"
        assert "Schema validation failed" in exc.value.message

    def test_pipeline_with_ndjson_and_group_aggregation(self, sample_ndjson_text):
        schema = Schema([
            Field("id", data_type=IntegerType()),
            Field("product", data_type=StringType(), transformers=[Trim()]),
            Field("price", data_type=FloatType()),
            Field("in_stock", data_type=BooleanType()),
        ])

        pipeline = (
            Pipeline.create("ndjson_inventory")
            .extract_json(sample_ndjson_text, is_ndjson=True)
            .validate(schema)
            .transform("categorize_pricing", lambda ds: ds.mutate(
                "tier", lambda r: "premium" if r["price"] > 100 else "budget"
            ))
        )

        result = pipeline.execute()
        assert result.row_count == 3

        # Group and aggregate
        grouped_ds = result.dataset.group_by("tier").aggregate({
            "price": "avg",
            "id": "count",
        })
        assert len(grouped_ds) == 2
        lookup = {r["tier"]: r for r in grouped_ds}
        assert lookup["premium"]["price_avg"] == 1200.0
        assert lookup["premium"]["id_count"] == 1
        assert lookup["budget"]["id_count"] == 2

    def test_pipeline_missing_extractor_raises(self):
        pipeline = Pipeline.create("unconfigured")
        with pytest.raises(PipelineExecutionError, match="No extraction source"):
            pipeline.execute()

    def test_pipeline_telemetry_metrics(self):
        pipeline = (
            Pipeline.create("telemetry_demo")
            .extract([{"x": 10}, {"x": 20}])
            .mutate("double_x", lambda r: r["x"] * 2)
        )
        res = pipeline.execute()
        metrics = res.to_dict()
        assert metrics["name"] == "telemetry_demo"
        assert metrics["row_count"] == 2
        assert metrics["rejected_count"] == 0
        assert metrics["duration_seconds"] >= 0.0
        assert "mutate_double_x" in metrics["stages_executed"]
