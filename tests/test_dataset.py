"""
tests.test_dataset
~~~~~~~~~~~~~~~~~~

Unit tests for datapype.dataset (Dataset and GroupedDataset).
Tests tabular relational operations, filtering, projections, sorting, deduplication,
joins (inner, left, right, outer), aggregations, and serialization.
"""

import math
import os
import tempfile
import pytest

from datapype.dataset import Dataset, GroupedDataset


@pytest.fixture
def sample_emp_dataset() -> Dataset:
    return Dataset([
        {"id": 1, "name": "Alice", "dept": "Engineering", "salary": 90000, "active": True},
        {"id": 2, "name": "Bob", "dept": "Sales", "salary": 60000, "active": True},
        {"id": 3, "name": "Charlie", "dept": "Engineering", "salary": 110000, "active": False},
        {"id": 4, "name": "Dana", "dept": "Marketing", "salary": 75000, "active": True},
        {"id": 5, "name": "Evan", "dept": "Sales", "salary": 65000, "active": False},
    ])


class TestDatasetBasicOperations:
    """Tests for basic Dataset access, columns, length, and immutability."""

    def test_empty_dataset(self):
        ds = Dataset()
        assert len(ds) == 0
        assert ds.columns == []
        assert ds.to_dict() == []
        assert repr(ds) == "Dataset(rows=0, columns=[])"

    def test_columns_and_length(self, sample_emp_dataset):
        assert len(sample_emp_dataset) == 5
        assert sample_emp_dataset.columns == ["id", "name", "dept", "salary", "active"]

    def test_indexing_and_slicing(self, sample_emp_dataset):
        first = sample_emp_dataset[0]
        assert first["name"] == "Alice"

        sliced = sample_emp_dataset[1:3]
        assert isinstance(sliced, Dataset)
        assert len(sliced) == 2
        assert sliced[0]["name"] == "Bob"
        assert sliced[1]["name"] == "Charlie"

    def test_records_immutability(self, sample_emp_dataset):
        recs = sample_emp_dataset.records
        recs[0]["name"] = "MODIFIED"
        assert sample_emp_dataset[0]["name"] == "Alice"


class TestDatasetTransformations:
    """Tests for filter, select, drop, rename, and mutate."""

    def test_filter(self, sample_emp_dataset):
        eng = sample_emp_dataset.filter(lambda r: r["dept"] == "Engineering")
        assert len(eng) == 2
        assert all(r["dept"] == "Engineering" for r in eng)

        high_salary_active = sample_emp_dataset.filter(lambda r: r["salary"] >= 75000 and r["active"])
        assert len(high_salary_active) == 2
        assert sorted([r["name"] for r in high_salary_active]) == ["Alice", "Dana"]

    def test_select(self, sample_emp_dataset):
        projected = sample_emp_dataset.select("id", "name")
        assert len(projected) == 5
        assert projected.columns == ["id", "name"]
        assert list(projected[0].keys()) == ["id", "name"]

    def test_drop(self, sample_emp_dataset):
        dropped = sample_emp_dataset.drop("dept", "active")
        assert "dept" not in dropped.columns
        assert "active" not in dropped.columns
        assert "salary" in dropped.columns

    def test_rename(self, sample_emp_dataset):
        renamed = sample_emp_dataset.rename({"name": "full_name", "dept": "department"})
        assert "full_name" in renamed.columns
        assert "department" in renamed.columns
        assert renamed[0]["full_name"] == "Alice"
        assert renamed[0]["department"] == "Engineering"

    def test_mutate(self, sample_emp_dataset):
        mutated = sample_emp_dataset.mutate("bonus", lambda r: r["salary"] * 0.1)
        assert "bonus" in mutated.columns
        assert mutated[0]["bonus"] == 9000.0
        assert mutated[1]["bonus"] == 6000.0


class TestDatasetSortingAndDeduplication:
    """Tests for sort_by, drop_duplicates, head, and tail."""

    def test_sort_by_column(self, sample_emp_dataset):
        asc = sample_emp_dataset.sort_by("salary", reverse=False)
        assert [r["salary"] for r in asc] == [60000, 65000, 75000, 90000, 110000]

        desc = sample_emp_dataset.sort_by("salary", reverse=True)
        assert [r["salary"] for r in desc] == [110000, 90000, 75000, 65000, 60000]

    def test_sort_with_none_values(self):
        ds = Dataset([{"id": 1, "val": 10}, {"id": 2, "val": None}, {"id": 3, "val": 5}])
        sorted_ds = ds.sort_by("val")
        # None values are grouped safely
        assert sorted_ds[0]["val"] == 5
        assert sorted_ds[1]["val"] == 10
        assert sorted_ds[2]["val"] is None

    def test_drop_duplicates_all_columns(self):
        ds = Dataset([
            {"a": 1, "b": 2},
            {"a": 1, "b": 2},
            {"a": 2, "b": 3},
        ])
        deduped = ds.drop_duplicates()
        assert len(deduped) == 2
        assert deduped.to_dict() == [{"a": 1, "b": 2}, {"a": 2, "b": 3}]

    def test_drop_duplicates_subset(self):
        ds = Dataset([
            {"id": 1, "version": 1, "data": "A"},
            {"id": 1, "version": 2, "data": "B"},
            {"id": 2, "version": 1, "data": "C"},
        ])
        deduped = ds.drop_duplicates(subset=["id"])
        assert len(deduped) == 2
        assert deduped[0]["data"] == "A"
        assert deduped[1]["data"] == "C"

    def test_head_and_tail(self, sample_emp_dataset):
        assert len(sample_emp_dataset.head(2)) == 2
        assert sample_emp_dataset.head(2)[0]["name"] == "Alice"
        assert len(sample_emp_dataset.tail(2)) == 2
        assert sample_emp_dataset.tail(2)[1]["name"] == "Evan"


class TestDatasetJoins:
    """Tests for relational inner, left, right, and outer joins."""

    @pytest.fixture
    def depts_dataset(self) -> Dataset:
        return Dataset([
            {"dept_name": "Engineering", "floor": 4, "head": "Grace"},
            {"dept_name": "Sales", "floor": 2, "head": "Frank"},
            {"dept_name": "HR", "floor": 1, "head": "Hannah"},  # No employees in HR
        ])

    def test_inner_join(self, sample_emp_dataset, depts_dataset):
        # Join emp on dept == dept_name
        emp_with_dept_key = sample_emp_dataset.rename({"dept": "dept_name"})
        joined = emp_with_dept_key.join(depts_dataset, on="dept_name", how="inner")
        # Marketing is in emp but not in depts; HR is in depts but not in emp
        # 2 Engineering + 2 Sales = 4 rows
        assert len(joined) == 4
        assert all("floor" in r for r in joined)
        dept_names = set(r["dept_name"] for r in joined)
        assert dept_names == {"Engineering", "Sales"}

    def test_left_join(self, sample_emp_dataset, depts_dataset):
        emp_with_dept_key = sample_emp_dataset.rename({"dept": "dept_name"})
        joined = emp_with_dept_key.join(depts_dataset, on="dept_name", how="left")
        assert len(joined) == 5
        # Dana in Marketing has no dept match, floor should be None
        dana_row = next(r for r in joined if r["name"] == "Dana")
        assert dana_row["floor"] is None
        assert dana_row["head"] is None

    def test_right_join(self, sample_emp_dataset, depts_dataset):
        emp_with_dept_key = sample_emp_dataset.rename({"dept": "dept_name"})
        joined = emp_with_dept_key.join(depts_dataset, on="dept_name", how="right")
        # 4 matched (2 Eng, 2 Sales) + 1 unmatched right (HR) = 5 rows
        assert len(joined) == 5
        hr_row = next(r for r in joined if r["dept_name"] == "HR")
        assert hr_row["head"] == "Hannah"
        assert hr_row["name"] is None

    def test_outer_join(self, sample_emp_dataset, depts_dataset):
        emp_with_dept_key = sample_emp_dataset.rename({"dept": "dept_name"})
        joined = emp_with_dept_key.join(depts_dataset, on="dept_name", how="outer")
        # 4 matched + 1 unmatched left (Marketing) + 1 unmatched right (HR) = 6 rows
        assert len(joined) == 6

    def test_unsupported_join_type_raises(self, sample_emp_dataset, depts_dataset):
        with pytest.raises(ValueError, match="Unsupported join method"):
            sample_emp_dataset.join(depts_dataset, on="id", how="cross")


class TestDatasetAggregations:
    """Tests for aggregate and group_by."""

    def test_dataset_aggregate_builtins(self, sample_emp_dataset):
        aggs = sample_emp_dataset.aggregate({
            "salary": "sum",
            "id": "count",
        })
        assert aggs["salary_sum"] == 400000
        assert aggs["id_count"] == 5

    def test_dataset_aggregate_stats(self, sample_emp_dataset):
        stats = sample_emp_dataset.aggregate({
            "salary": "avg",
        })
        assert stats["salary_avg"] == 80000.0

        min_max = sample_emp_dataset.aggregate({
            "salary": "min",
            "active": "count",
        })
        assert min_max["salary_min"] == 60000

        stddev = sample_emp_dataset.aggregate({"salary": "stddev"})
        assert stddev["salary_stddev"] > 0

    def test_group_by_aggregation(self, sample_emp_dataset):
        grouped = sample_emp_dataset.group_by("dept")
        agg_ds = grouped.aggregate({
            "salary": "avg",
            "id": "count",
        })
        assert len(agg_ds) == 3
        lookup = {r["dept"]: r for r in agg_ds}

        # Engineering: Alice (90k) + Charlie (110k) => avg 100k, count 2
        assert lookup["Engineering"]["salary_avg"] == 100000.0
        assert lookup["Engineering"]["id_count"] == 2

        # Sales: Bob (60k) + Evan (65k) => avg 62.5k, count 2
        assert lookup["Sales"]["salary_avg"] == 62500.0
        assert lookup["Sales"]["id_count"] == 2

        # Marketing: Dana (75k) => avg 75k, count 1
        assert lookup["Marketing"]["salary_avg"] == 75000.0
        assert lookup["Marketing"]["id_count"] == 1


class TestDatasetSerialization:
    """Tests for to_csv and to_json export."""

    def test_to_csv_string_and_file(self, sample_emp_dataset):
        csv_str = sample_emp_dataset.to_csv()
        assert "id,name,dept,salary,active" in csv_str
        assert "Alice" in csv_str

        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv") as tmp:
            tmp_path = tmp.name

        try:
            sample_emp_dataset.to_csv(filepath=tmp_path)
            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "Alice" in content
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_to_json_string_and_file(self, sample_emp_dataset):
        json_str = sample_emp_dataset.to_json()
        assert '"name": "Alice"' in json_str

        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tmp:
            tmp_path = tmp.name

        try:
            sample_emp_dataset.to_json(filepath=tmp_path)
            with open(tmp_path, "r", encoding="utf-8") as f:
                content = f.read()
            assert '"name": "Alice"' in content
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
