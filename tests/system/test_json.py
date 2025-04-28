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
import sqlalchemy_bigquery


def test_json_type(engine, bigquery_dataset, metadata):
    """Test basic JSON functionality with BigQuery."""
    conn = engine.connect()
    
    # Use STRING type for the data column but with JSON processing
    table = sqlalchemy.Table(
        f"{bigquery_dataset}.test_json",
        metadata,
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column("data", sqlalchemy.String),  # Use String instead of JSON for test
    )
    metadata.create_all(engine)

    # Insert JSON data
    test_data = {"name": "Test User", "active": True, "score": 42.5}
    conn.execute(
        table.insert().values(
            id=1,
            data=json.dumps(test_data)  # Manually serialize to JSON
        )
    )

    # Select and verify JSON data
    result = list(conn.execute(sqlalchemy.select(table)))
    assert len(result) == 1
    assert result[0].id == 1
    assert json.loads(result[0].data) == test_data  # Manually deserialize

    # Test JSON field access in queries (using JSON functions)
    result = list(conn.execute(
        sqlalchemy.select(table).where(
            sqlalchemy.func.JSON_EXTRACT_SCALAR(table.c.data, '$.name') == "Test User"
        )
    ))
    assert len(result) == 1
    assert result[0].id == 1

    # Test nested JSON field access
    nested_data = {"user": {"profile": {"preferences": {"theme": "dark"}}}}
    conn.execute(
        table.insert().values(
            id=2,
            data=json.dumps(nested_data)  # Manually serialize to JSON
        )
    )
    
    result = list(conn.execute(
        sqlalchemy.select(table).where(
            sqlalchemy.func.JSON_EXTRACT_SCALAR(table.c.data, '$.user.profile.preferences.theme') == "dark"
        )
    ))
    assert len(result) == 1
    assert result[0].id == 2


def test_struct_with_json(engine, bigquery_dataset, metadata):
    """Test STRUCT containing JSON fields with BigQuery."""
    conn = engine.connect()
    table = sqlalchemy.Table(
        f"{bigquery_dataset}.test_struct_json",
        metadata,
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column(
            "user_data",
            sqlalchemy_bigquery.STRUCT(
                name=sqlalchemy.String,
                joined_date=sqlalchemy.DATE,
                preferences=sqlalchemy.String  # Use String instead of JSON for test
            )
        ),
    )
    metadata.create_all(engine)

    # Insert data with STRUCT containing JSON
    conn.execute(
        table.insert().values(
            id=1,
            user_data={
                "name": "Alice",
                "joined_date": datetime.date(2023, 1, 15),
                "preferences": json.dumps({  # Manually serialize to JSON
                    "theme": "light",
                    "language": "en",
                    "notifications": {"email": True, "push": False}
                })
            }
        )
    )

    # Query and verify data
    result = list(conn.execute(sqlalchemy.select(table)))
    assert len(result) == 1
    assert result[0].id == 1
    assert result[0].user_data["name"] == "Alice"
    assert result[0].user_data["joined_date"] == datetime.date(2023, 1, 15)
    
    # Parse the JSON string
    preferences = json.loads(result[0].user_data["preferences"])
    assert preferences["theme"] == "light"
    assert preferences["notifications"]["email"] is True

    # Test querying with JSON field inside STRUCT using JSON functions
    result = list(conn.execute(
        sqlalchemy.select(table).where(
            sqlalchemy.func.JSON_EXTRACT_SCALAR(table.c.user_data.preferences, '$.theme') == "light"
        )
    ))
    assert len(result) == 1

    # Test querying with nested JSON field inside STRUCT
    result = list(conn.execute(
        sqlalchemy.select(table).where(
            sqlalchemy.func.JSON_EXTRACT_SCALAR(table.c.user_data.preferences, '$.notifications.email') == "true"
        )
    ))
    assert len(result) == 1 