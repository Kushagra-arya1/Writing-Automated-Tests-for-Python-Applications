"""
datapype.dataset
~~~~~~~~~~~~~~~~

In-memory tabular dataset representation with relational operations,
filtering, mapping, aggregations, joins, and deduplication.
"""

from copy import deepcopy
import csv
import io
import json
import math
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Set, Tuple, Union


class Dataset:
    """
    An immutable-by-convention tabular data container.
    Provides functional transformation primitives chaining fluent workflows.
    """

    def __init__(self, records: Optional[Iterable[Dict[str, Any]]] = None) -> None:
        self._records: List[Dict[str, Any]] = [dict(r) for r in (records or [])]

    @property
    def records(self) -> List[Dict[str, Any]]:
        """Returns a shallow copy of the internal records list."""
        return [dict(r) for r in self._records]

    @property
    def columns(self) -> List[str]:
        """Returns the list of column names in the dataset."""
        if not self._records:
            return []
        # Maintain key insertion order across all records
        cols: List[str] = []
        for r in self._records:
            for k in r.keys():
                if k not in cols:
                    cols.append(k)
        return cols

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        return iter(self.records)

    def __getitem__(self, index: Union[int, slice]) -> Union[Dict[str, Any], "Dataset"]:
        if isinstance(index, slice):
            return Dataset(self._records[index])
        return dict(self._records[index])

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Dataset):
            return False
        return self._records == other._records

    def __repr__(self) -> str:
        return f"Dataset(rows={len(self._records)}, columns={self.columns})"

    def filter(self, predicate: Callable[[Dict[str, Any]], bool]) -> "Dataset":
        """
        Filters rows based on a predicate callable.

        Args:
            predicate: Function taking a record dictionary and returning bool.
        """
        filtered = [r for r in self._records if predicate(r)]
        return Dataset(filtered)

    def select(self, *columns: str) -> "Dataset":
        """
        Projects only the specified columns into a new dataset.
        """
        col_set = set(columns)
        projected = [{k: v for k, v in r.items() if k in col_set} for r in self._records]
        return Dataset(projected)

    def drop(self, *columns: str) -> "Dataset":
        """
        Drops the specified columns from the dataset.
        """
        col_set = set(columns)
        dropped = [{k: v for k, v in r.items() if k not in col_set} for r in self._records]
        return Dataset(dropped)

    def rename(self, mapping: Dict[str, str]) -> "Dataset":
        """
        Renames columns using a mapping dictionary.
        """
        renamed = [
            {mapping.get(k, k): v for k, v in r.items()}
            for r in self._records
        ]
        return Dataset(renamed)

    def mutate(self, column: str, func: Callable[[Dict[str, Any]], Any]) -> "Dataset":
        """
        Adds or computes a column based on existing row values.
        """
        mutated: List[Dict[str, Any]] = []
        for r in self._records:
            new_r = dict(r)
            new_r[column] = func(new_r)
            mutated.append(new_r)
        return Dataset(mutated)

    def sort_by(
        self,
        key: Union[str, Callable[[Dict[str, Any]], Any]],
        reverse: bool = False,
    ) -> "Dataset":
        """
        Sorts the dataset by a column name or key extractor function.
        """
        if isinstance(key, str):
            extractor = lambda r: (r.get(key) is None, r.get(key))
        else:
            extractor = key
        sorted_records = sorted(self._records, key=extractor, reverse=reverse)
        return Dataset(sorted_records)

    def drop_duplicates(self, subset: Optional[Sequence[str]] = None) -> "Dataset":
        """
        Removes duplicate rows based on all or a subset of columns.
        Preserves original ordering of the first encounter.
        """
        seen: Set[Tuple[Any, ...]] = set()
        deduped: List[Dict[str, Any]] = []

        for r in self._records:
            if subset:
                sig = tuple(r.get(col) for col in subset)
            else:
                sig = tuple(sorted(r.items()))
            if sig not in seen:
                seen.add(sig)
                deduped.append(r)

        return Dataset(deduped)

    def head(self, n: int = 5) -> "Dataset":
        """Returns the first n rows."""
        return Dataset(self._records[:n])

    def tail(self, n: int = 5) -> "Dataset":
        """Returns the last n rows."""
        return Dataset(self._records[-n:] if n > 0 else [])

    def join(
        self,
        other: "Dataset",
        on: str,
        how: str = "inner",
    ) -> "Dataset":
        """
        Performs a relational join with another Dataset on a key column.

        Args:
            other: Right-hand Dataset.
            on: Column name to join on.
            how: 'inner', 'left', 'right', or 'outer'.
        """
        how = how.lower()
        if how not in {"inner", "left", "right", "outer"}:
            raise ValueError(f"Unsupported join method '{how}'. Choose from inner, left, right, outer.")

        # Index the right-hand dataset by join key
        right_index: Dict[Any, List[Dict[str, Any]]] = {}
        for r in other.records:
            k = r.get(on)
            if k not in right_index:
                right_index[k] = []
            right_index[k].append(r)

        # Collect columns to avoid collision (other than 'on')
        right_cols = [c for c in other.columns if c != on]

        joined: List[Dict[str, Any]] = []
        matched_right_keys: Set[Any] = set()

        for left_row in self._records:
            key_val = left_row.get(on)
            matches = right_index.get(key_val, [])

            if matches:
                matched_right_keys.add(key_val)
                for right_row in matches:
                    merged = dict(left_row)
                    for c in right_cols:
                        col_name = f"{c}_right" if c in left_row and c != on else c
                        merged[col_name] = right_row.get(c)
                    joined.append(merged)
            else:
                if how in {"left", "outer"}:
                    merged = dict(left_row)
                    for c in right_cols:
                        col_name = f"{c}_right" if c in left_row and c != on else c
                        merged[col_name] = None
                    joined.append(merged)

        if how in {"right", "outer"}:
            for right_key, matches in right_index.items():
                if right_key not in matched_right_keys:
                    for right_row in matches:
                        merged = {on: right_key}
                        # Fill left cols with None
                        for c in self.columns:
                            if c != on:
                                merged[c] = None
                        # Fill right cols
                        for c in right_cols:
                            col_name = f"{c}_right" if c in self.columns and c != on else c
                            merged[col_name] = right_row.get(c)
                        joined.append(merged)

        return Dataset(joined)

    def group_by(self, key: str) -> "GroupedDataset":
        """
        Groups rows by a specific column key.
        """
        return GroupedDataset(self, key)

    def aggregate(
        self,
        aggregations: Dict[str, Union[str, Callable[[List[Any]], Any]]],
    ) -> Dict[str, Any]:
        """
        Computes summary statistics across columns.

        Supported built-in aggregation strings:
          'sum', 'avg', 'mean', 'min', 'max', 'count', 'stddev'
        """
        results: Dict[str, Any] = {}

        for col, agg in aggregations.items():
            values = [r.get(col) for r in self._records if r.get(col) is not None]

            if callable(agg):
                results[f"{col}_{getattr(agg, '__name__', 'custom')}"] = agg(values)
                continue

            agg_name = str(agg).lower()
            out_key = f"{col}_{agg_name}"

            if agg_name == "count":
                results[out_key] = len(values)
            elif not values:
                results[out_key] = None
            elif agg_name == "sum":
                results[out_key] = sum(values)
            elif agg_name in {"avg", "mean"}:
                results[out_key] = sum(values) / len(values)
            elif agg_name == "min":
                results[out_key] = min(values)
            elif agg_name == "max":
                results[out_key] = max(values)
            elif agg_name == "stddev":
                if len(values) < 2:
                    results[out_key] = 0.0
                else:
                    mean_val = sum(values) / len(values)
                    variance = sum((x - mean_val) ** 2 for x in values) / (len(values) - 1)
                    results[out_key] = math.sqrt(variance)
            else:
                raise ValueError(f"Unknown aggregation '{agg}'. Choose from sum, avg, mean, min, max, count, stddev.")

        return results

    def to_dict(self) -> List[Dict[str, Any]]:
        """Exports rows as a list of dictionaries."""
        return self.records

    def to_csv(self, filepath: Optional[str] = None, delimiter: str = ",") -> str:
        """Exports dataset to CSV string or file."""
        output = io.StringIO()
        cols = self.columns
        writer = csv.DictWriter(output, fieldnames=cols, delimiter=delimiter)
        writer.writeheader()
        for r in self._records:
            writer.writerow(r)
        content = output.getvalue()
        if filepath:
            with open(filepath, "w", encoding="utf-8", newline="") as f:
                f.write(content)
        return content

    def to_json(self, filepath: Optional[str] = None, indent: int = 2) -> str:
        """Exports dataset to JSON formatted string or file."""
        content = json.dumps(self._records, indent=indent, default=str)
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
        return content


class GroupedDataset:
    """Represents a dataset partitioned by a grouping key."""

    def __init__(self, dataset: Dataset, group_key: str) -> None:
        self.dataset = dataset
        self.group_key = group_key
        self.groups: Dict[Any, List[Dict[str, Any]]] = {}

        for r in dataset:
            k = r.get(group_key)
            if k not in self.groups:
                self.groups[k] = []
            self.groups[k].append(r)

    def aggregate(
        self,
        aggregations: Dict[str, Union[str, Callable[[List[Any]], Any]]],
    ) -> Dataset:
        """
        Calculates aggregations per group and returns a new Dataset.
        """
        output_rows: List[Dict[str, Any]] = []

        for group_val, group_records in self.groups.items():
            sub_dataset = Dataset(group_records)
            agg_results = sub_dataset.aggregate(aggregations)
            row = {self.group_key: group_val}
            row.update(agg_results)
            output_rows.append(row)

        return Dataset(output_rows)
