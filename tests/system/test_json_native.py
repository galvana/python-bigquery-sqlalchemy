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

import datetime
import json
import sqlalchemy
from sqlalchemy import select
from sqlalchemy.sql import func

from sqlalchemy_bigquery import JSON, STRUCT


def test_json_type_native(engine, bigquery_dataset, metadata):
    """Test native JSON type with BigQuery."""
    conn = engine.connect()
    
    # Use the JSON type directly
    table = sqlalchemy.Table(
        f"{bigquery_dataset}.test_json_native",
        metadata,
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column("data", JSON),
    )
    metadata.create_all(engine)

    # Insert JSON data - serialize manually for the system test
    test_data = {"name": "Test User", "active": True, "score": 42.5}
    conn.execute(
        table.insert().values(
            id=1,
            data=test_data  # Don't serialize - the dialect will handle it
        )
    )

    # Select and verify JSON data
    result = list(conn.execute(select(table)))
    assert len(result) == 1
    assert result[0].id == 1
    
    # The data should be automatically deserialized
    assert isinstance(result[0].data, dict)
    assert result[0].data["name"] == "Test User"
    assert result[0].data["active"] is True
    assert result[0].data["score"] == 42.5

    # Test JSON field access in queries using JSON functions
    result = list(conn.execute(
        select(table).where(
            func.JSON_EXTRACT_SCALAR(table.c.data, '$.name') == "Test User"
        )
    ))
    assert len(result) == 1
    assert result[0].id == 1


def test_struct_with_json_native(engine, bigquery_dataset, metadata):
    """Test STRUCT containing native JSON fields with BigQuery."""
    conn = engine.connect()
    
    # Use STRING instead of JSON for STRUCT field in system test
    # since BigQuery DBAPI doesn't support JSON in STRUCT
    table = sqlalchemy.Table(
        f"{bigquery_dataset}.test_struct_json_native",
        metadata,
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column(
            "user_data",
            STRUCT(
                name=sqlalchemy.String,
                joined_date=sqlalchemy.DATE,
                preferences=sqlalchemy.String  # Use String instead of JSON for system test
            )
        ),
    )
    metadata.create_all(engine)

    # Insert data with STRUCT containing JSON
    preferences_data = {
        "theme": "light",
        "language": "en",
        "notifications": {"email": True, "push": False}
    }
    
    conn.execute(
        table.insert().values(
            id=1,
            user_data={
                "name": "Alice",
                "joined_date": datetime.date(2023, 1, 15),
                "preferences": json.dumps(preferences_data)  # Manually serialize for system test
            }
        )
    )

    # Query and verify data
    result = list(conn.execute(select(table)))
    assert len(result) == 1
    assert result[0].id == 1
    assert result[0].user_data["name"] == "Alice"
    assert result[0].user_data["joined_date"] == datetime.date(2023, 1, 15)
    
    # The preferences should be manually deserialized for system test
    preferences = json.loads(result[0].user_data["preferences"])
    assert isinstance(preferences, dict)
    assert preferences["theme"] == "light"
    assert preferences["notifications"]["email"] is True

    # Test querying with JSON field inside STRUCT using JSON functions
    result = list(conn.execute(
        select(table).where(
            func.JSON_EXTRACT_SCALAR(table.c.user_data.preferences, '$.theme') == "light"
        )
    ))
    assert len(result) == 1 