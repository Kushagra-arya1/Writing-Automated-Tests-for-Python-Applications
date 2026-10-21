"""
tests.conftest
~~~~~~~~~~~~~~

Shared test fixtures and sample data generators for pytest.
Provides standardized test fixtures for schema validation, datasets,
parsers, and end-to-end integration workflows.
"""

from datetime import datetime
import pytest
from typing import Any, Dict, List

from datapype.dataset import Dataset
from datapype.schema import Field, Schema
from datapype.transformers import DateFormat, RoundNumber, ToLowerCase, ToTitleCase, Trim
from datapype.types import BooleanType, DateTimeType, FloatType, IntegerType, StringType
from datapype.validators import Email, InChoices, Length, NonNegative, Positive, Range, Regex, Required


@pytest.fixture
def sample_raw_users_csv() -> str:
    """Raw CSV content with leading/trailing spaces, inconsistent cases, and boundary values."""
    return (
        "id, name ,email ,age,role,active,salary,joined_date\n"
        "101,  Alice Smith , alice@example.com , 29 , admin , true , 75000.50 , 2021-04-15\n"
        "102, Bob Jones,bob@work.org, 45 , editor, yes , 62000.00 , 2019-11-01\n"
        "103, Charlie Brown ,charlie@peanuts.com, 19 , viewer , 0 , 31000.25 , 2023-01-10\n"
        "104,  Dana Scully , scully@fbi.gov , 38 , admin , TRUE , 89000.75 , 2018-07-22\n"
        "105, Evan Wright , evan@news.net , 52 , editor , false , 58000.00 , 2015-03-30\n"
    )


@pytest.fixture
def sample_orders_csv() -> str:
    """CSV containing sales orders for testing aggregations and relational joins."""
    return (
        "order_id,user_id,amount,category,status\n"
        "ORD-001,101,150.25,electronics,completed\n"
        "ORD-002,101,89.50,books,completed\n"
        "ORD-003,102,320.00,electronics,pending\n"
        "ORD-004,103,45.00,clothing,completed\n"
        "ORD-005,104,210.75,electronics,completed\n"
        "ORD-006,104,65.20,books,refunded\n"
        "ORD-007,999,500.00,furniture,completed\n"
    )


@pytest.fixture
def sample_user_records() -> List[Dict[str, Any]]:
    """Clean, pre-validated in-memory user dictionaries."""
    return [
        {"id": 101, "name": "Alice Smith", "email": "alice@example.com", "age": 29, "role": "admin", "active": True, "salary": 75000.50},
        {"id": 102, "name": "Bob Jones", "email": "bob@work.org", "age": 45, "role": "editor", "active": True, "salary": 62000.00},
        {"id": 103, "name": "Charlie Brown", "email": "charlie@peanuts.com", "age": 19, "role": "viewer", "active": False, "salary": 31000.25},
        {"id": 104, "name": "Dana Scully", "email": "scully@fbi.gov", "age": 38, "role": "admin", "active": True, "salary": 89000.75},
        {"id": 105, "name": "Evan Wright", "email": "evan@news.net", "age": 52, "role": "editor", "active": False, "salary": 58000.00},
    ]


@pytest.fixture
def sample_orders_dataset() -> Dataset:
    """Dataset of sales orders ready for operations."""
    return Dataset([
        {"order_id": "ORD-001", "user_id": 101, "amount": 150.25, "category": "electronics", "status": "completed"},
        {"order_id": "ORD-002", "user_id": 101, "amount": 89.50, "category": "books", "status": "completed"},
        {"order_id": "ORD-003", "user_id": 102, "amount": 320.00, "category": "electronics", "status": "pending"},
        {"order_id": "ORD-004", "user_id": 103, "amount": 45.00, "category": "clothing", "status": "completed"},
        {"order_id": "ORD-005", "user_id": 104, "amount": 210.75, "category": "electronics", "status": "completed"},
        {"order_id": "ORD-006", "user_id": 104, "amount": 65.20, "category": "books", "status": "refunded"},
    ])


@pytest.fixture
def user_schema() -> Schema:
    """Pre-configured Schema enforcing types, cleansing, and constraints on user records."""
    return Schema(
        fields=[
            Field("id", data_type=IntegerType(), required=True, validators=[Positive()]),
            Field(
                "name",
                data_type=StringType(),
                required=True,
                transformers=[Trim(), ToTitleCase()],
                validators=[Length(min_length=2, max_length=50)],
            ),
            Field(
                "email",
                data_type=StringType(),
                required=True,
                transformers=[Trim(), ToLowerCase()],
                validators=[Email()],
            ),
            Field(
                "age",
                data_type=IntegerType(),
                required=True,
                validators=[Range(min_value=18, max_value=120)],
            ),
            Field(
                "role",
                data_type=StringType(),
                required=True,
                transformers=[Trim(), ToLowerCase()],
                validators=[InChoices(["admin", "editor", "viewer"])],
            ),
            Field("active", data_type=BooleanType(), required=True),
            Field(
                "salary",
                data_type=FloatType(),
                required=True,
                transformers=[RoundNumber(decimals=2)],
                validators=[NonNegative()],
            ),
            Field(
                "joined_date",
                data_type=DateTimeType(date_format="%Y-%m-%d"),
                required=False,
                default=None,
            ),
        ],
        allow_unknown=False,
        strip_unknown=True,
        fail_fast=False,
    )


@pytest.fixture
def sample_ndjson_text() -> str:
    """Sample NDJSON stream with one record per line."""
    return (
        '{"id": 1, "product": "Laptop", "price": 1200.0, "in_stock": true}\n'
        '{"id": 2, "product": "Mouse", "price": 25.5, "in_stock": true}\n'
        '{"id": 3, "product": "Keyboard", "price": 75.0, "in_stock": false}\n'
    )
