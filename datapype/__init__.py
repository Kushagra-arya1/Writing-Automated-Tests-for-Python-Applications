"""
datapype
~~~~~~~~

A robust, composable Python library for data validation, transformation,
tabular manipulation, and ETL pipelines.
"""

from datapype.dataset import Dataset, GroupedDataset
from datapype.exceptions import (
    DataPypeError,
    FieldValidationError,
    ParserError,
    PipelineExecutionError,
    SchemaDefinitionError,
    TransformationError,
    ValidationError,
)
from datapype.parsers import CSVParser, JSONParser
from datapype.pipeline import Pipeline, PipelineResult
from datapype.schema import Field, Schema
from datapype.transformers import (
    ChainedTransformer,
    CustomTransformer,
    DateFormat,
    DefaultIfNull,
    MapValues,
    Replace,
    RoundNumber,
    ToLowerCase,
    ToTitleCase,
    ToUpperCase,
    Transformer,
    Trim,
)
from datapype.types import (
    AnyType,
    BooleanType,
    DataType,
    DateTimeType,
    FloatType,
    IntegerType,
    ListType,
    StringType,
)
from datapype.validators import (
    CustomValidator,
    Email,
    InChoices,
    Length,
    NonNegative,
    Positive,
    Range,
    Regex,
    Required,
    Validator,
)

__version__ = "1.0.0"

__all__ = [
    # Core types
    "DataType",
    "AnyType",
    "IntegerType",
    "FloatType",
    "StringType",
    "BooleanType",
    "DateTimeType",
    "ListType",
    # Validators
    "Validator",
    "Required",
    "Range",
    "Length",
    "Regex",
    "InChoices",
    "Email",
    "Positive",
    "NonNegative",
    "CustomValidator",
    # Transformers
    "Transformer",
    "Trim",
    "ToUpperCase",
    "ToLowerCase",
    "ToTitleCase",
    "Replace",
    "RoundNumber",
    "DefaultIfNull",
    "MapValues",
    "DateFormat",
    "CustomTransformer",
    "ChainedTransformer",
    # Schema
    "Field",
    "Schema",
    # Dataset
    "Dataset",
    "GroupedDataset",
    # Parsers
    "CSVParser",
    "JSONParser",
    # Pipeline
    "Pipeline",
    "PipelineResult",
    # Exceptions
    "DataPypeError",
    "SchemaDefinitionError",
    "FieldValidationError",
    "ValidationError",
    "TransformationError",
    "ParserError",
    "PipelineExecutionError",
]
