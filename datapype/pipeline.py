"""
datapype.pipeline
~~~~~~~~~~~~~~~~~

Fluent ETL data pipeline builder and execution orchestrator.
Manages sequential stages of data extraction, schema validation, transformation,
rejection filtering, and telemetry.
"""

import time
from typing import Any, Callable, Dict, List, Optional, Union

from datapype.dataset import Dataset
from datapype.exceptions import PipelineExecutionError, ValidationError
from datapype.parsers import CSVParser, JSONParser
from datapype.schema import Schema


class PipelineResult:
    """Encapsulates the output and telemetry of an executed pipeline."""

    def __init__(
        self,
        name: str,
        dataset: Dataset,
        rejected_records: List[ValidationError],
        stages_executed: List[str],
        duration_seconds: float,
    ) -> None:
        self.name = name
        self.dataset = dataset
        self.rejected_records = rejected_records
        self.stages_executed = stages_executed
        self.duration_seconds = duration_seconds

    @property
    def row_count(self) -> int:
        return len(self.dataset)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected_records)

    @property
    def is_successful(self) -> bool:
        return len(self.rejected_records) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Summary of pipeline run metrics."""
        return {
            "name": self.name,
            "row_count": self.row_count,
            "rejected_count": self.rejected_count,
            "stages_executed": self.stages_executed,
            "duration_seconds": round(self.duration_seconds, 4),
            "is_successful": self.is_successful,
        }

    def __repr__(self) -> str:
        return (
            f"PipelineResult(name='{self.name}', rows={self.row_count}, "
            f"rejected={self.rejected_count}, duration={self.duration_seconds:.4f}s)"
        )


class Pipeline:
    """
    Fluent ETL pipeline orchestrator.
    """

    def __init__(self, name: str = "pipeline") -> None:
        self.name = name
        self._extractor: Optional[Callable[[], Dataset]] = None
        self._stages: List[Dict[str, Any]] = []

    @classmethod
    def create(cls, name: str = "pipeline") -> "Pipeline":
        return cls(name=name)

    def extract(self, source: Union[Dataset, List[Dict[str, Any]]]) -> "Pipeline":
        """Supplies an in-memory dataset or list of records."""
        if isinstance(source, Dataset):
            self._extractor = lambda: source
        elif isinstance(source, list):
            self._extractor = lambda: Dataset(source)
        else:
            raise ValueError("extract() expects Dataset or list of record dicts")
        return self

    def extract_csv(self, content: str, **parser_kwargs: Any) -> "Pipeline":
        """Extracts dataset from CSV text."""
        parser = CSVParser(**parser_kwargs)
        self._extractor = lambda: parser.parse_string(content)
        return self

    def extract_json(self, content: str, is_ndjson: bool = False) -> "Pipeline":
        """Extracts dataset from JSON / NDJSON text."""
        parser = JSONParser(is_ndjson=is_ndjson)
        self._extractor = lambda: parser.parse_string(content)
        return self

    def validate(self, schema: Schema, drop_invalid: bool = True) -> "Pipeline":
        """
        Validates records against a schema.

        Args:
            schema: The Schema instance to validate against.
            drop_invalid: If True, invalid rows are collected into rejected_records.
                          If False, raises PipelineExecutionError on the first invalid row.
        """
        self._stages.append(
            {
                "type": "validate",
                "name": "schema_validation",
                "schema": schema,
                "drop_invalid": drop_invalid,
            }
        )
        return self

    def filter(self, predicate: Callable[[Dict[str, Any]], bool], name: Optional[str] = None) -> "Pipeline":
        """Filters dataset rows matching a predicate."""
        stage_name = name or f"filter_{predicate.__name__ if hasattr(predicate, '__name__') else 'custom'}"
        self._stages.append({"type": "filter", "name": stage_name, "predicate": predicate})
        return self

    def mutate(
        self,
        column: str,
        func: Callable[[Dict[str, Any]], Any],
        name: Optional[str] = None,
    ) -> "Pipeline":
        """Appends or computes a column for each row."""
        stage_name = name or f"mutate_{column}"
        self._stages.append({"type": "mutate", "name": stage_name, "column": column, "func": func})
        return self

    def sort_by(self, key: Union[str, Callable[[Dict[str, Any]], Any]], reverse: bool = False) -> "Pipeline":
        """Sorts the dataset."""
        key_name = key if isinstance(key, str) else "custom_key"
        self._stages.append({"type": "sort", "name": f"sort_by_{key_name}", "key": key, "reverse": reverse})
        return self

    def drop_duplicates(self, subset: Optional[List[str]] = None) -> "Pipeline":
        """Deduplicates rows."""
        self._stages.append({"type": "dedupe", "name": "drop_duplicates", "subset": subset})
        return self

    def transform(self, step_name: str, transform_func: Callable[[Dataset], Dataset]) -> "Pipeline":
        """Applies a custom dataset-level transformation."""
        self._stages.append({"type": "custom", "name": step_name, "func": transform_func})
        return self

    def execute(self) -> PipelineResult:
        """
        Executes all configured extraction and transformation stages.

        Returns:
            PipelineResult containing the final dataset, rejected records, and metrics.

        Raises:
            PipelineExecutionError: If extraction was not set or an unhandled failure occurred.
        """
        if self._extractor is None:
            raise PipelineExecutionError("extraction", "No extraction source configured for pipeline")

        start_time = time.time()
        stages_executed: List[str] = ["extraction"]
        rejected_records: List[ValidationError] = []

        try:
            dataset = self._extractor()
        except Exception as e:
            raise PipelineExecutionError("extraction", f"Failed to extract source data: {e}", original_error=e) from e

        for stage in self._stages:
            stage_name = stage["name"]
            stage_type = stage["type"]
            stages_executed.append(stage_name)

            try:
                if stage_type == "validate":
                    schema: Schema = stage["schema"]
                    drop_invalid: bool = stage["drop_invalid"]
                    valid_recs, errs = schema.validate_batch(dataset.records)

                    if errs:
                        rejected_records.extend(errs)
                        if not drop_invalid:
                            raise PipelineExecutionError(
                                stage_name,
                                f"Schema validation failed on {len(errs)} record(s)",
                                original_error=errs[0],
                            )

                    dataset = Dataset(valid_recs)

                elif stage_type == "filter":
                    dataset = dataset.filter(stage["predicate"])

                elif stage_type == "mutate":
                    dataset = dataset.mutate(stage["column"], stage["func"])

                elif stage_type == "sort":
                    dataset = dataset.sort_by(stage["key"], reverse=stage["reverse"])

                elif stage_type == "dedupe":
                    dataset = dataset.drop_duplicates(subset=stage.get("subset"))

                elif stage_type == "custom":
                    dataset = stage["func"](dataset)

            except Exception as e:
                if isinstance(e, PipelineExecutionError):
                    raise
                raise PipelineExecutionError(stage_name, f"Stage error: {e}", original_error=e) from e

        duration = time.time() - start_time
        return PipelineResult(
            name=self.name,
            dataset=dataset,
            rejected_records=rejected_records,
            stages_executed=stages_executed,
            duration_seconds=duration,
        )
