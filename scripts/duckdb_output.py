"""Export DuckDB relations through typed Arrow, preserving timestamp precision."""

import pyarrow as pa


def to_pandas_utc(relation):
    """Normalize aware columns to UTC without guessing zones for naive timestamps.

    DuckDB 2.0's direct pandas export loses the zone of TIMESTAMPTZ_NS.
    Its relation Arrow export retains both the zone and the original time unit.
    Changing Arrow's timezone metadata preserves epoch integers and NULLs.
    """
    table = relation.to_arrow_table()
    for index, field in enumerate(table.schema):
        if pa.types.is_timestamp(field.type) and field.type.tz is not None:
            utc_type = pa.timestamp(field.type.unit, tz="UTC")
            table = table.set_column(
                index, field.with_type(utc_type), table.column(index).cast(utc_type)
            )
    return table.to_pandas()
