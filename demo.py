"""
datapype - Showcase Demonstration Script
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An end-to-end executable demonstration of the datapype library.
Demonstrates declarative schema validation, dirty data cleansing, ETL pipelines,
relational joins, grouped aggregations, and multi-format serialization.
"""

import json
from datapype import (
    CSVParser,
    Dataset,
    DateTimeType,
    Email,
    Field,
    FloatType,
    InChoices,
    IntegerType,
    NonNegative,
    Pipeline,
    Positive,
    Range,
    RoundNumber,
    Schema,
    StringType,
    ToLowerCase,
    ToTitleCase,
    Trim,
)


def run_demo() -> None:
    print("=" * 70)
    print("   DATAPYPE: High-Performance Data Validation & ETL Pipeline Engine")
    print("=" * 70)

    # 1. Define Schema
    print("\n[Step 1] Defining Declarative Schema...")
    user_schema = Schema(
        fields=[
            Field("id", data_type=IntegerType(), required=True, validators=[Positive()]),
            Field("name", data_type=StringType(), required=True, transformers=[Trim(), ToTitleCase()]),
            Field("email", data_type=StringType(), required=True, transformers=[Trim(), ToLowerCase()], validators=[Email()]),
            Field("age", data_type=IntegerType(), required=True, validators=[Range(min_value=18, max_value=100)]),
            Field("dept", data_type=StringType(), required=True, transformers=[Trim(), ToTitleCase()], validators=[InChoices(["Engineering", "Product", "Sales", "Marketing"])]),
            Field("salary", data_type=FloatType(), required=True, transformers=[RoundNumber(2)], validators=[NonNegative()]),
        ],
        allow_unknown=False,
        strip_unknown=True,
    )
    print(f"  Schema configured with {len(user_schema.fields)} fields.")

    # 2. Raw Dirty CSV Data
    print("\n[Step 2] Ingesting Dirty CSV Data...")
    raw_csv = (
        "id, name ,email ,age,dept,salary\n"
        "101,  ALICE SMITH , alice@example.com , 29 , Engineering , 95000.50\n"
        "102, bob JONES,bob@corp.org, 45 , Sales , 68000.00\n"
        "-99, Invalid ID,bad_id@corp.org, 30 , Product , 70000.00\n"           # Invalid negative ID
        "103, Charlie Brown ,charlie@peanuts.com, 17 , Marketing , 32000.00\n"   # Invalid age (< 18)
        "104,  DANA SCULLY , scully@fbi.gov , 38 , Engineering , 105000.75\n"
        "105, Evan Wright , evan@news.net , 52 , Marketing , 62000.00\n"
        "106, Fiona Gallagher, fiona_gallagher, 26 , Product , 55000.00\n"      # Invalid email format
    )

    # 3. Execute ETL Pipeline
    print("\n[Step 3] Executing Fluent ETL Pipeline...")
    pipeline = (
        Pipeline.create("enterprise_etl")
        .extract_csv(raw_csv)
        .validate(user_schema, drop_invalid=True)
        .filter(lambda r: r["salary"] >= 60000, name="high_earners_filter")
        .mutate("bonus_10pct", lambda r: round(r["salary"] * 0.10, 2))
        .mutate("total_comp", lambda r: round(r["salary"] + r["bonus_10pct"], 2))
        .sort_by("salary", reverse=True)
    )

    result = pipeline.execute()

    print(f"\nPipeline Execution Summary:")
    print(f"  * Pipeline Name       : {result.name}")
    print(f"  * Execution Time      : {result.duration_seconds:.4f} seconds")
    print(f"  * Valid Clean Rows    : {result.row_count}")
    print(f"  * Rejected Dead-Letter: {result.rejected_count}")
    print(f"  * Stages Executed     : {' -> '.join(result.stages_executed)}")

    # 4. Display Clean Records
    print("\n[Step 4] Processed & Cleaned Records:")
    for idx, record in enumerate(result.dataset, start=1):
        print(f"  [{idx}] {record['name']} | Dept: {record['dept']} | Salary: ${record['salary']:,.2f} | Total Comp: ${record['total_comp']:,.2f}")

    # 5. Display Dead-Letter Queue (Rejected Records)
    print("\n[Step 5] Dead-Letter Audit (Rejected Records):")
    for idx, err in enumerate(result.rejected_records, start=1):
        print(f"  [Error {idx}] Row Index {err.record_index}: {err.errors[0].field} -> {err.errors[0].message}")

    # 6. Relational Department Analytics
    print("\n[Step 6] Departmental Aggregations & Metrics:")
    dept_metrics = (
        result.dataset.group_by("dept")
        .aggregate({
            "salary": "avg",
            "total_comp": "sum",
            "id": "count",
        })
    )
    for row in dept_metrics:
        print(f"  * {row['dept']}: Count={row['id_count']}, Avg Salary=${row['salary_avg']:,.2f}, Total Outlay=${row['total_comp_sum']:,.2f}")

    # 7. JSON Output Preview
    print("\n[Step 7] Serializing Processed Data to JSON:")
    json_preview = result.dataset.select("id", "name", "dept", "total_comp").to_json(indent=2)
    print(json_preview)

    print("\n" + "=" * 70)
    print("   Demo executed successfully! Zero warnings or unhandled exceptions.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
