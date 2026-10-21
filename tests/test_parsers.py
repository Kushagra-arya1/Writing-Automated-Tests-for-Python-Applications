"""
tests.test_parsers
~~~~~~~~~~~~~~~~~~

Unit tests for datapype.parsers (CSVParser and JSONParser).
Tests dialect handling, custom delimiters, quote escaping, empty line stripping,
NDJSON streaming, and malformed syntax recovery.
"""

import os
import tempfile
import pytest

from datapype.dataset import Dataset
from datapype.exceptions import ParserError
from datapype.parsers import CSVParser, JSONParser


class TestCSVParser:
    """Tests for CSVParser."""

    def test_standard_csv_with_header(self):
        csv_text = "id,name,role\n1,Alice,admin\n2,Bob,user\n"
        parser = CSVParser()
        ds = parser.parse_string(csv_text)
        assert len(ds) == 2
        assert ds.columns == ["id", "name", "role"]
        assert ds[0] == {"id": "1", "name": "Alice", "role": "admin"}

    def test_custom_delimiters_and_quotes(self):
        # Semicolon delimited with quoted commas
        csv_text = 'id;name;comment\n1;"Doe, John";"Senior, Lead"\n'
        parser = CSVParser(delimiter=";", quotechar='"')
        ds = parser.parse_string(csv_text)
        assert len(ds) == 1
        assert ds[0]["name"] == "Doe, John"
        assert ds[0]["comment"] == "Senior, Lead"

    def test_csv_without_header(self):
        csv_text = "Alice,30\nBob,25\n"
        parser = CSVParser(has_header=False)
        ds = parser.parse_string(csv_text)
        assert len(ds) == 2
        assert ds.columns == ["col_0", "col_1"]
        assert ds[0] == {"col_0": "Alice", "col_1": "30"}

    def test_whitespace_and_empty_lines_handling(self):
        csv_text = (
            "\n"
            "  id  ,   name  \n"
            "\n"
            "  101 ,  Alice  \n"
            "       \n"
            "  102 ,  Bob    \n"
        )
        parser = CSVParser(strip_whitespace=True, skip_empty_lines=True)
        ds = parser.parse_string(csv_text)
        assert len(ds) == 2
        assert ds.columns == ["id", "name"]
        assert ds[0]["name"] == "Alice"
        assert ds[1]["name"] == "Bob"

    def test_empty_string_returns_empty_dataset(self):
        parser = CSVParser()
        assert len(parser.parse_string("")) == 0
        assert len(parser.parse_string("   \n   ")) == 0

    def test_column_mismatch_raises_parser_error_with_line_number(self):
        csv_text = "id,name,role\n1,Alice,admin\n2,Bob\n"  # line 3 missing role
        parser = CSVParser()
        with pytest.raises(ParserError) as exc:
            parser.parse_string(csv_text)
        assert exc.value.format_name == "CSV"
        assert exc.value.line_number == 3
        assert "Column count mismatch" in exc.value.message

    def test_empty_header_name_raises(self):
        csv_text = "id,,role\n1,Alice,admin\n"
        parser = CSVParser()
        with pytest.raises(ParserError, match="empty column names"):
            parser.parse_string(csv_text)

    def test_parse_file_success_and_error(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".csv") as tmp:
            tmp.write("a,b\n1,2\n")
            tmp_path = tmp.name

        try:
            parser = CSVParser()
            ds = parser.parse_file(tmp_path)
            assert len(ds) == 1
            assert ds[0] == {"a": "1", "b": "2"}
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        with pytest.raises(ParserError, match="Could not read file"):
            parser.parse_file("non_existent_file_path.csv")


class TestJSONParser:
    """Tests for JSONParser."""

    def test_parse_json_array_of_objects(self):
        json_text = '[{"id": 1, "product": "Widget"}, {"id": 2, "product": "Gadget"}]'
        parser = JSONParser()
        ds = parser.parse_string(json_text)
        assert len(ds) == 2
        assert ds[0]["product"] == "Widget"

    def test_parse_single_json_object(self):
        json_text = '{"status": "ok", "code": 200}'
        parser = JSONParser()
        ds = parser.parse_string(json_text)
        assert len(ds) == 1
        assert ds[0]["status"] == "ok"

    def test_parse_ndjson_stream(self):
        ndjson_text = (
            '{"event": "login", "user": "alice"}\n'
            '\n'
            '{"event": "view", "user": "bob"}\n'
            '{"event": "logout", "user": "alice"}\n'
        )
        parser = JSONParser(is_ndjson=True)
        ds = parser.parse_string(ndjson_text)
        assert len(ds) == 3
        assert ds[0]["event"] == "login"
        assert ds[2]["event"] == "logout"

    def test_empty_json_string(self):
        parser = JSONParser()
        assert len(parser.parse_string("")) == 0
        assert len(parser.parse_string("   ")) == 0

    def test_malformed_json_raises(self):
        parser = JSONParser()
        with pytest.raises(ParserError, match="Malformed JSON"):
            parser.parse_string("{not valid json}")

    def test_non_dict_elements_in_array_raises(self):
        parser = JSONParser()
        with pytest.raises(ParserError, match="Expected array of objects"):
            parser.parse_string('["just", "strings"]')

    def test_parse_json_file(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tmp:
            tmp.write('[{"msg": "hello"}]')
            tmp_path = tmp.name

        try:
            parser = JSONParser()
            ds = parser.parse_file(tmp_path)
            assert len(ds) == 1
            assert ds[0]["msg"] == "hello"
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        with pytest.raises(ParserError, match="Could not read file"):
            parser.parse_file("invalid_file_location.json")
