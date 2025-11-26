import warnings
from typing import Any

import pytest

from surrealdb.cbor import decoder, encoder, types


def test_cbor_decoder_module() -> None:
    """Test that the decoder module works."""
    # The warning is emitted at import time, so we need to import it fresh
    import importlib

    importlib.reload(decoder)

    # Test that imports work
    assert hasattr(decoder, "CBORDecoder")
    assert hasattr(decoder, "load")
    assert hasattr(decoder, "loads")


def test_cbor_encoder_module() -> None:
    """Test that the encoder module works."""
    # The warning is emitted at import time, so we need to import it fresh
    import importlib

    importlib.reload(encoder)

    # Test that imports work
    assert hasattr(encoder, "CBOREncoder")
    assert hasattr(encoder, "dump")
    assert hasattr(encoder, "dumps")
    assert hasattr(encoder, "shareable_encoder")


def test_cbor_types_module() -> None:
    """Test that the types module works."""
    # The warning is emitted at import time, so we need to import it fresh
    import importlib

    importlib.reload(types)

    # Test that imports work
    assert hasattr(types, "CBORDecodeEOF")
    assert hasattr(types, "CBORDecodeError")
    assert hasattr(types, "CBORDecodeValueError")
    assert hasattr(types, "CBOREncodeError")
    assert hasattr(types, "CBOREncodeTypeError")
    assert hasattr(types, "CBOREncodeValueError")
    assert hasattr(types, "CBORError")
    assert hasattr(types, "CBORSimpleValue")
    assert hasattr(types, "CBORTag")
    assert hasattr(types, "FrozenDict")
    assert hasattr(types, "undefined")
