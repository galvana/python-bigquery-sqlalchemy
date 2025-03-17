# Copyright (c) 2024 The sqlalchemy-bigquery Authors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import json
import pytest
import sqlalchemy

from sqlalchemy_bigquery import JSON, STRUCT
from .conftest import setup_table


def test_json_colspec():
    """Test JSON type column specification"""
    assert JSON().get_col_spec() == "JSON"


def test_json_repr():
    """Test JSON type representation"""
    assert isinstance(repr(JSON()), str)


def test_json_literals(faux_conn):
    """Test JSON literal handling in compilation"""
    table = setup_table(
        faux_conn,
        "json_test",
        sqlalchemy.Column("json_col", JSON),
    )
    
    # Test simple value insertion
    stmt = table.insert().values(json_col={"key": "value"})
    compiled = stmt.compile(faux_conn.engine)
    
    # Check that the compiled statement includes proper type
    # For parameter binding, we use STRING because BigQuery DBAPI doesn't support JSON
    assert "%(json_col:STRING)s" in str(compiled)
    
    # Test with literal_binds=True to check JSON literals
    compiled_literal = stmt.compile(faux_conn.engine, compile_kwargs={"literal_binds": True})
    assert "JSON" in str(compiled_literal)


def test_json_in_struct_colspec():
    """Test STRUCT with JSON field column specification"""
    struct_with_json = STRUCT(
        name=sqlalchemy.String,
        data=JSON,
    )
    
    # Verify the column spec includes JSON type
    assert struct_with_json.get_col_spec() == "STRUCT<name STRING, data JSON>"


def test_json_in_struct_compilation(faux_conn, metadata):
    """Test compilation of a STRUCT containing a JSON field"""
    struct_with_json = STRUCT(
        name=sqlalchemy.String,
        data=JSON,
    )
    
    table = sqlalchemy.Table(
        "struct_json_test",
        metadata,
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column("person", struct_with_json),
    )
    
    # Test CREATE TABLE statement compilation
    create_stmt = sqlalchemy.schema.CreateTable(table)
    compiled_create = create_stmt.compile(faux_conn.engine)
    
    # Check that proper STRUCT with JSON type is used in DDL
    assert "STRUCT<name STRING, data JSON>" in str(compiled_create)
    
    # Test insert statement compilation
    insert_stmt = table.insert().values(
        id=1,
        person={
            "name": "Test User",
            "data": {"preferences": {"theme": "dark", "language": "en"}}
        }
    )
    
    compiled_insert = insert_stmt.compile(faux_conn.engine)
    
    # For parameter binding, we use STRING because BigQuery DBAPI doesn't support JSON
    # But the STRUCT definition should still show JSON
    assert "STRUCT<name STRING, data JSON>" in str(compiled_insert)


def test_json_field_access_compilation(faux_conn, metadata):
    """Test compilation of JSON field access"""
    table = sqlalchemy.Table(
        "json_access_test",
        metadata,
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column("data", JSON),
    )
    
    # Test JSON field access in a WHERE clause
    stmt = sqlalchemy.select(table.c.id).where(table.c.data["key"] == "value")
    compiled = stmt.compile(faux_conn.engine)
    
    # Check that JSON field access is properly compiled
    assert "(`json_access_test`.`data`.key)" in str(compiled)


def test_json_in_struct_field_access(faux_conn, metadata):
    """Test compilation of accessing a JSON field within a STRUCT"""
    struct_with_json = STRUCT(
        name=sqlalchemy.String,
        data=JSON,
    )
    
    table = sqlalchemy.Table(
        "struct_json_access",
        metadata,
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column("person", struct_with_json),
    )
    
    # Test accessing JSON field inside a STRUCT
    stmt = sqlalchemy.select(table.c.id).where(
        table.c.person.data["preferences"]["theme"] == "dark"
    )
    
    compiled = stmt.compile(faux_conn.engine)
    compiled_str = str(compiled)
    
    # Check that nested field access works correctly
    assert "((`struct_json_access`.`person`.data).preferences).theme" in compiled_str 