# DataPype: Automated Testing & Data Pipeline Engine
*Week 3 Task Submission - Writing Automated Tests for Python Applications*

[![Python Version](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Test Suite](https://img.shields.io/badge/tests-238%20passed-brightgreen.svg)](#test-execution)
[![Code Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen.svg)](#code-coverage)
[![TDD](https://img.shields.io/badge/methodology-Test--Driven%20Development%20(TDD)-orange.svg)](#test-driven-development-tdd-process)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## Executive Summary

**`datapype`** is a production-grade Python library designed for declarative schema validation, tabular data manipulation, transformation, and resilient ETL pipelines. Built strictly following **Test-Driven Development (TDD)** principles, it features **238 automated test cases** delivering **95% statement coverage** across all modules.

The library requires **zero external runtime dependencies** (using solely the Python standard library), ensuring 100% self-contained reproducibility on any platform. The test suite is dual-compatible with both modern **`pytest`** and Python's built-in **`unittest`** runner.

---

## Deliverables Index

In accordance with the Week 3 Task requirements:
1. **Python Module (`datapype/`)**: Clean, modular, type-annotated architecture for data validation, relational manipulation, and ETL pipelines.
2. **Automated Test Suite (`tests/`)**: 238 unit, integration, edge-case, and TDD demonstration tests.
3. **Test Documentation (`TEST_DOCUMENTATION.md`)**: Comprehensive 6-part test plan detailing methodology, rationale, boundary analysis, and refactoring history.
4. **Execution Scripts**:
   - `demo.py`: End-to-end interactive demonstration.
   - `run_tests.py`: Multi-runner test execution CLI.
   - `package_submission.py`: Creates the standalone submission ZIP archive.

---

## Architectural Overview

The `datapype` library follows the Single Responsibility Principle and Separation of Concerns:

```
week 3/
├── datapype/                           # Core Library Package
│   ├── __init__.py                     # Public API exports
│   ├── exceptions.py                   # Hierarchical custom exception tree
│   ├── types.py                        # Strict/lenient type coercion engine
│   ├── validators.py                   # Composable validation predicates
│   ├── transformers.py                 # Pure data normalization & cleaning
│   ├── schema.py                       # Declarative schema & batch error collection
│   ├── dataset.py                      # Tabular container with joins & aggregations
│   ├── parsers.py                      # Ingestion engine for CSV, JSON, and NDJSON
│   └── pipeline.py                     # Fluent ETL orchestrator with telemetry
├── tests/                              # Automated Test Suite (238 Tests)
│   ├── __init__.py
│   ├── conftest.py                     # Shared pytest fixtures & mock datasets
│   ├── test_types.py                   # Unit tests: type casting & strictness (84 tests)
│   ├── test_validators.py              # Unit tests: constraints & boundaries (41 tests)
│   ├── test_transformers.py            # Unit tests: pure transformation functions (24 tests)
│   ├── test_schema.py                  # Unit tests: schema enforcement & policies (14 tests)
│   ├── test_dataset.py                 # Unit tests: relational operations & joins (24 tests)
│   ├── test_parsers.py                 # Unit tests: CSV/JSON dialects & malformed input (15 tests)
│   ├── test_pipeline_integration.py    # Integration tests: end-to-end ETL pipelines (6 tests)
│   ├── test_edge_cases.py              # Stress tests: Unicode, leap years, boundaries (11 tests)
│   ├── test_tdd_demonstration.py       # TDD Lifecycle demonstration (11 tests)
│   └── test_unittest_suite.py          # Native unittest.TestCase suite (8 tests)
├── demo.py                             # Interactive runnable demonstration
├── run_tests.py                        # Unified test runner (pytest / unittest)
├── pyproject.toml                      # Build metadata & pytest configuration
├── requirements.txt                    # Production dependencies (Zero external deps)
├── requirements-dev.txt                # Development test runner dependencies
├── package_submission.py               # Submission packager generating .zip archive
├── README.md                           # This document
└── TEST_DOCUMENTATION.md               # Detailed test methodology and test catalog
```

---

## Quickstart & Usage

### 1. Schema Validation & Data Cleansing

```python
from datapype import (
    Schema, Field, IntegerType, StringType, FloatType,
    Trim, ToTitleCase, ToLowerCase, RoundNumber,
    Positive, Range, Email
)

# Declarative schema definition
user_schema = Schema([
    Field("id", data_type=IntegerType(), required=True, validators=[Positive()]),
    Field("name", data_type=StringType(), required=True, transformers=[Trim(), ToTitleCase()]),
    Field("email", data_type=StringType(), required=True, transformers=[Trim(), ToLowerCase()], validators=[Email()]),
    Field("age", data_type=IntegerType(), required=True, validators=[Range(min_value=18, max_value=120)]),
    Field("salary", data_type=FloatType(), required=True, transformers=[RoundNumber(2)]),
])

# Validate and normalize a dirty record
raw_record = {
    "id": "101",
    "name": "  ALICE SMITH  ",
    "email": "ALICE@EXAMPLE.COM",
    "age": "29",
    "salary": "75000.556",
}

clean_record = user_schema.validate_record(raw_record)
print(clean_record)
# Output:
# {'id': 101, 'name': 'Alice Smith', 'email': 'alice@example.com', 'age': 29, 'salary': 75000.56}
```

### 2. Fluent ETL Pipeline

```python
from datapype import Pipeline

raw_csv = (
    "id,name,email,age,salary\n"
    "101,  Alice Smith , alice@example.com , 29 , 75000.50\n"
    "102, Bob Jones , bob@corp.org , 45 , 62000.00\n"
    "-99, Invalid User , bad_email , 15 , 20000.00\n" # Invalid row (rejected to dead-letter)
)

result = (
    Pipeline.create("payroll_etl")
    .extract_csv(raw_csv)
    .validate(user_schema, drop_invalid=True) # Dead-letter collection
    .filter(lambda r: r["age"] >= 25)
    .mutate("bonus", lambda r: round(r["salary"] * 0.10, 2))
    .mutate("total_comp", lambda r: round(r["salary"] + r["bonus"], 2))
    .sort_by("salary", reverse=True)
    .execute()
)

print(f"Processed: {result.row_count} rows, Rejected: {result.rejected_count} rows")
print(result.dataset.to_json(indent=2))
```

---

## Test Execution

The test suite can be run using either `run_tests.py`, `pytest`, or Python's built-in `unittest` runner.

### Method 1: Using the Unified Runner (Recommended)
```bash
# Automatically detects pytest and runs with coverage; falls back to unittest
python run_tests.py

# Force pytest execution with coverage
python run_tests.py --pytest

# Force standard library unittest execution
python run_tests.py --unittest
```

### Method 2: Direct Pytest Execution
```bash
# Run all 238 tests
python -m pytest -v

# Run with full branch coverage report
python -m pytest --cov=datapype --cov-report=term-missing
```

### Method 3: Direct Unittest Execution (Zero External Tools)
```bash
# Run using Python's standard library test runner
python -m unittest discover -v -s tests
```

---

## Code Coverage Summary

Generated via `pytest-cov` on Python 3.14:

| Module | Statements | Missing Lines | Coverage | Status |
| :--- | :---: | :---: | :---: | :---: |
| `datapype/__init__.py` | 10 | 0 | **100%** | PASS |
| `datapype/exceptions.py` | 43 | 0 | **100%** | PASS |
| `datapype/types.py` | 157 | 4 | **97%** | PASS |
| `datapype/dataset.py` | 191 | 7 | **96%** | PASS |
| `datapype/schema.py` | 102 | 4 | **96%** | PASS |
| `datapype/validators.py` | 143 | 7 | **95%** | PASS |
| `datapype/transformers.py` | 148 | 8 | **95%** | PASS |
| `datapype/parsers.py` | 93 | 6 | **94%** | PASS |
| `datapype/pipeline.py` | 110 | 9 | **92%** | PASS |
| **TOTAL** | **997** | **45** | **95%** | **PASS** |

---

## Test-Driven Development (TDD) Process

This project applied the **Red-Green-Refactor** development cycle throughout its creation:

1. **🔴 RED Phase**:
   - Write failing automated unit tests asserting desired behavior, boundary contracts, and edge conditions prior to implementation.
   - Example: Before implementing `LuhnChecksumValidator`, tests in `test_tdd_demonstration.py` were written asserting that valid card vectors pass and mutated check digits fail.
2. **🟢 GREEN Phase**:
   - Write the minimum necessary implementation code to satisfy the test contract.
   - Run the test suite to confirm the state transition from red to green.
3. **🔵 REFACTOR Phase**:
   - Review code for cognitive complexity, maintainability, and performance.
   - Restructure algorithms, generalize regex patterns, enhance error diagnostics, and remove redundancies.
   - Re-run the full automated regression suite to ensure zero regressions.

For a detailed case study of the TDD lifecycle across multiple features, refer to [TEST_DOCUMENTATION.md](file:///c:/Users/Kushagra%20Arya/OneDrive/Desktop/week%203/TEST_DOCUMENTATION.md).

---

## Packaging the Submission Archive

To produce the required self-contained ZIP archive for submission:

```bash
python package_submission.py
```

This script verifies test execution, validates archive integrity, and outputs `datapype_test_submission.zip` containing all module source files, tests, and documentation.
