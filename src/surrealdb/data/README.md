## What is CBOR?
CBOR is a binary data serialization format similar to JSON but more compact, efficient, and capable of encoding a 
broader range of data types. It is useful for exchanging structured data between systems, especially when performance 
and size are critical.

## Purpose of the CBOR Implementation

The CBOR code here allows the custom SurrealDB types (e.g., `GeometryPoint`, `Table`, `Range`, etc.) to be serialized 
into CBOR binary format and deserialized back into Python objects. This is necessary because these types are not natively 
supported by CBOR; thus, custom encoding and decoding logic is implemented.

## Key Components

### Custom Types

`Range` Class: Represents a range with a beginning (`begin`) and end (`end`). These can either be included (`BoundIncluded`) or excluded (`BoundExcluded`).
`Table`, `RecordID`, `GeometryPoint`, etc.: Custom SurrealDB-specific data types, representing domain-specific constructs like tables, records, and geometrical objects.

### CBOR Encoder

The function `default_encoder` is used to encode custom Python objects into CBOR's binary format. This is done by associating a specific CBOR tag (a numeric identifier) with each data type.

For example:

`GeometryPoint` objects are encoded using the tag `TAG_GEOMETRY_POINT` with its coordinates as the value.
`Range` objects are encoded using the tag `TAG_BOUND_EXCLUDED` with a list [begin, end] as its value.
The `CBORTag` class is used to represent tagged data in `CBOR`.

### CBOR Decoder

The function `tag_decoder` is the inverse of `default_encoder`. It takes tagged CBOR data and reconstructs the corresponding Python objects.

For example:

When encountering the `TAG_GEOMETRY_POINT` tag, it creates a `GeometryPoint` object using the tag's value (coordinates).
When encountering the `TAG_RANGE` tag, it creates a `Range` object using the tag's value (begin and end).

### encode and decode Functions

These are high-level functions for serializing and deserializing data:

`encode(obj)`: Converts a Python object into CBOR binary format.
`decode(data)`: Converts CBOR binary data back into a Python object using the custom decoding logic.