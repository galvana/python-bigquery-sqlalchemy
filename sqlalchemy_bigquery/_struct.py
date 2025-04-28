# Copyright (c) 2021 The sqlalchemy-bigquery Authors
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

import packaging.version
import sqlalchemy.sql.default_comparator
import sqlalchemy.sql.sqltypes
import sqlalchemy.types

from . import base

sqlalchemy_1_4_or_more = packaging.version.parse(
    sqlalchemy.__version__
) >= packaging.version.parse("1.4")

if sqlalchemy_1_4_or_more:
    import sqlalchemy.sql.coercions
    import sqlalchemy.sql.roles


def _get_subtype_col_spec(type_):
    global _get_subtype_col_spec

    type_compiler = base.dialect.type_compiler(base.dialect())
    _get_subtype_col_spec = type_compiler.process
    
    # Pass struct_field=True for JSON types in STRUCT fields
    if hasattr(type_, "__class__") and type_.__class__.__name__ == "JSON":
        return type_compiler.process(type_, struct_field=True)
    
    return _get_subtype_col_spec(type_)


class STRUCT(sqlalchemy.sql.sqltypes.Indexable, sqlalchemy.types.UserDefinedType):
    """
    A type for BigQuery STRUCT/RECORD data

    See https://googleapis.dev/python/sqlalchemy-bigquery/latest/struct.html
    """

    # See https://docs.sqlalchemy.org/en/14/core/custom_types.html#creating-new-types

    def __init__(
        self,
        *fields,
        **kwfields,
    ):
        # Note that because:
        # https://docs.python.org/3/whatsnew/3.6.html#pep-468-preserving-keyword-argument-order
        # We know that `kwfields` preserves order.
        self._STRUCT_fields = tuple(
            (
                name,
                type_ if isinstance(type_, sqlalchemy.types.TypeEngine) else type_(),
            )
            for (name, type_) in (fields + tuple(kwfields.items()))
        )

        self._STRUCT_byname = {
            name.lower(): type_ for (name, type_) in self._STRUCT_fields
        }

    def __repr__(self):
        fields = ", ".join(
            f"{name}={repr(type_)}" for name, type_ in self._STRUCT_fields
        )
        return f"STRUCT({fields})"

    def get_col_spec(self, **kw):
        fields = []
        for name, type_ in self._STRUCT_fields:
            # Special handling for JSON types in STRUCT fields
            if hasattr(type_, "__class__") and type_.__class__.__name__ == "JSON":
                fields.append(f"{name} JSON")
            else:
                fields.append(f"{name} {_get_subtype_col_spec(type_)}")
        
        return f"STRUCT<{', '.join(fields)}>"

    def bind_processor(self, dialect):
        import json
        
        # Check if any field in the STRUCT is a JSON type
        has_json_fields = any(
            hasattr(type_, "__class__") and type_.__class__.__name__ == "JSON"
            for _, type_ in self._STRUCT_fields
        )
        
        # If no JSON fields, return dict for backward compatibility
        if not has_json_fields:
            return dict
        
        def process_value(value, struct_type):
            if value is None:
                return None
            
            result = {}
            for key, val in value.items():
                # Find the field type by case-insensitive lookup
                field_type = struct_type._STRUCT_byname.get(key.lower())
                
                if field_type is None:
                    # Field not found in schema, pass through unchanged
                    result[key] = val
                    continue
                    
                # Check if this is a nested STRUCT
                if hasattr(field_type, "__class__") and field_type.__class__.__name__ == "STRUCT":
                    if isinstance(val, dict):
                        # Process nested STRUCT recursively
                        result[key] = process_value(val, field_type)
                    else:
                        result[key] = val
                # Check if this field is a JSON type
                elif hasattr(field_type, "__class__") and field_type.__class__.__name__ == "JSON":
                    # Serialize JSON data
                    if val is not None and not isinstance(val, str):
                        result[key] = json.dumps(val)
                    else:
                        result[key] = val
                else:
                    result[key] = val
            
            return result
        
        def process(value):
            if value is None:
                return None
            
            return process_value(value, self)
        
        return process

    def result_processor(self, dialect, coltype):
        import json
        
        # Check if any field in the STRUCT is a JSON type
        has_json_fields = any(
            hasattr(type_, "__class__") and type_.__class__.__name__ == "JSON"
            for _, type_ in self._STRUCT_fields
        )
        
        # If no JSON fields, return None for backward compatibility
        if not has_json_fields:
            return None
        
        def process_value(value, struct_type):
            if value is None:
                return None
            
            # Handle case where value is a string (happens in some test cases)
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except (ValueError, TypeError):
                    return value
            
            if not isinstance(value, dict):
                return value
            
            result = {}
            for key, val in value.items():
                # Find the field type by case-insensitive lookup
                field_type = struct_type._STRUCT_byname.get(key.lower())
                
                if field_type is None:
                    # Field not found in schema, pass through unchanged
                    result[key] = val
                    continue
                    
                # Check if this is a nested STRUCT
                if hasattr(field_type, "__class__") and field_type.__class__.__name__ == "STRUCT":
                    if isinstance(val, dict):
                        # Process nested STRUCT recursively
                        result[key] = process_value(val, field_type)
                    else:
                        result[key] = val
                # Check if this field is a JSON type
                elif hasattr(field_type, "__class__") and field_type.__class__.__name__ == "JSON":
                    # Deserialize JSON string
                    if val is not None and isinstance(val, str):
                        try:
                            result[key] = json.loads(val)
                        except (ValueError, TypeError):
                            result[key] = val  # Keep as is if not valid JSON
                    else:
                        result[key] = val
                else:
                    result[key] = val
            
            return result
        
        def process(value):
            if value is None:
                return None
            
            return process_value(value, self)
        
        return process

    class Comparator(sqlalchemy.sql.sqltypes.Indexable.Comparator):
        def _setup_getitem(self, name):
            if not isinstance(name, str):
                raise TypeError(
                    f"STRUCT fields can only be accessed with strings field names,"
                    f" not {repr(name)}."
                )
            subtype = self.expr.type._STRUCT_byname.get(name.lower())
            if subtype is None:
                raise KeyError(name)
            operator = struct_getitem_op
            index = _field_index(self, name, operator)
            return operator, index, subtype

        def __getattr__(self, name):
            if name.lower() in self.expr.type._STRUCT_byname:
                return self[name]

    comparator_factory = Comparator


# In the implementations of _field_index below, we're stealing from
# the JSON type implementation, but the code to steal changed in
# 1.4. :/

if sqlalchemy_1_4_or_more:

    def _field_index(self, name, operator):
        return sqlalchemy.sql.coercions.expect(
            sqlalchemy.sql.roles.BinaryElementRole,
            name,
            expr=self.expr,
            operator=operator,
            bindparam_type=sqlalchemy.types.String(),
        )

else:

    def _field_index(self, name, operator):
        return sqlalchemy.sql.default_comparator._check_literal(
            self.expr,
            operator,
            name,
            bindparam_type=sqlalchemy.types.String(),
        )


def struct_getitem_op(a, b):
    raise NotImplementedError()


def json_getitem_op(a, b):
    # This is a placeholder function that will be handled by the compiler
    # The actual implementation is in visit_json_getitem_op_binary
    return None


sqlalchemy.sql.default_comparator.operator_lookup[
    struct_getitem_op.__name__
] = sqlalchemy.sql.default_comparator.operator_lookup["json_getitem_op"]

sqlalchemy.sql.default_comparator.operator_lookup[
    json_getitem_op.__name__
] = sqlalchemy.sql.default_comparator.operator_lookup["json_getitem_op"]


class SQLCompiler:
    def visit_struct_getitem_op_binary(self, binary, operator_, **kw):
        left = self.process(binary.left, **kw)
        return f"{left}.{binary.right.value}"
