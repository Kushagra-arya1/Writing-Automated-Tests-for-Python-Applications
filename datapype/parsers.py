"""
datapype.parsers
~~~~~~~~~~~~~~~~

Ingestion utilities for structured data formats (CSV, JSON, NDJSON).
Converts raw files and streams into typed Dataset instances with line-level diagnostics.
"""

import csv
import io
import json
from typing import Any, Dict, List, Optional

from datapype.dataset import Dataset
from datapype.exceptions import ParserError


class CSVParser:
    """
    Parses delimiter-separated tabular text into a Dataset.
    Supports dialect configuration, whitespace trimming, and malformed row detection.
    """

    def __init__(
        self,
        delimiter: str = ",",
        quotechar: str = '"',
        has_header: bool = True,
        strip_whitespace: bool = True,
        skip_empty_lines: bool = True,
    ) -> None:
        self.delimiter = delimiter
        self.quotechar = quotechar
        self.has_header = has_header
        self.strip_whitespace = strip_whitespace
        self.skip_empty_lines = skip_empty_lines

    def parse_string(self, content: str) -> Dataset:
        """
        Parses CSV string into a Dataset.

        Raises:
            ParserError: If delimiter parsing fails or row headers mismatch.
        """
        if not content.strip():
            return Dataset([])

        stream = io.StringIO(content)
        reader = csv.reader(stream, delimiter=self.delimiter, quotechar=self.quotechar)

        rows: List[List[str]] = []
        for line_idx, raw_row in enumerate(reader, start=1):
            if self.skip_empty_lines and not any(cell.strip() for cell in raw_row):
                continue
            cleaned = [c.strip() if self.strip_whitespace else c for c in raw_row]
            rows.append(cleaned)

        if not rows:
            return Dataset([])

        if self.has_header:
            headers = rows[0]
            data_rows = rows[1:]

            # Check duplicate or empty headers
            if any(not h for h in headers):
                raise ParserError("CSV", 1, "CSV header contains empty column names")

            records: List[Dict[str, Any]] = []
            for row_idx, row in enumerate(data_rows, start=2):
                if len(row) != len(headers):
                    raise ParserError(
                        "CSV",
                        row_idx,
                        f"Column count mismatch: expected {len(headers)} fields, found {len(row)}",
                    )
                record = {headers[i]: row[i] for i in range(len(headers))}
                records.append(record)

            return Dataset(records)
        else:
            # Generate col_0, col_1, ...
            col_count = len(rows[0])
            headers = [f"col_{i}" for i in range(col_count)]
            records = []
            for row_idx, row in enumerate(rows, start=1):
                if len(row) != col_count:
                    raise ParserError(
                        "CSV",
                        row_idx,
                        f"Column count mismatch: expected {col_count} fields, found {len(row)}",
                    )
                records.append({headers[i]: row[i] for i in range(col_count)})
            return Dataset(records)

    def parse_file(self, filepath: str, encoding: str = "utf-8") -> Dataset:
        """Parses a CSV file from the filesystem."""
        try:
            with open(filepath, "r", encoding=encoding) as f:
                content = f.read()
        except OSError as e:
            raise ParserError("CSV", None, f"Could not read file '{filepath}': {e}") from e
        return self.parse_string(content)


class JSONParser:
    """
    Parses JSON array or Newline-Delimited JSON (NDJSON) into a Dataset.
    """

    def __init__(self, is_ndjson: bool = False) -> None:
        self.is_ndjson = is_ndjson

    def parse_string(self, content: str) -> Dataset:
        """
        Parses JSON or NDJSON string into a Dataset.

        Raises:
            ParserError: If JSON syntax is invalid or structure is not records.
        """
        clean = content.strip()
        if not clean:
            return Dataset([])

        if self.is_ndjson:
            records: List[Dict[str, Any]] = []
            for line_idx, line in enumerate(clean.splitlines(), start=1):
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    obj = json.loads(line_str)
                except json.JSONDecodeError as e:
                    raise ParserError("NDJSON", line_idx, f"Invalid JSON syntax: {e}") from e

                if not isinstance(obj, dict):
                    raise ParserError("NDJSON", line_idx, f"Expected JSON object per line, got {type(obj).__name__}")
                records.append(obj)
            return Dataset(records)
        else:
            try:
                data = json.loads(clean)
            except json.JSONDecodeError as e:
                raise ParserError("JSON", None, f"Malformed JSON: {e}") from e

            if isinstance(data, dict):
                return Dataset([data])
            elif isinstance(data, list):
                for idx, item in enumerate(data):
                    if not isinstance(item, dict):
                        raise ParserError("JSON", idx + 1, f"Expected array of objects, item {idx} is {type(item).__name__}")
                return Dataset(data)
            else:
                raise ParserError("JSON", None, f"Expected JSON array or object, got {type(data).__name__}")

    def parse_file(self, filepath: str, encoding: str = "utf-8") -> Dataset:
        """Parses a JSON file from the filesystem."""
        try:
            with open(filepath, "r", encoding=encoding) as f:
                content = f.read()
        except OSError as e:
            raise ParserError("JSON", None, f"Could not read file '{filepath}': {e}") from e
        return self.parse_string(content)
