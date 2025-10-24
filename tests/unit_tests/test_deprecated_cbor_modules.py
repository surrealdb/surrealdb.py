import warnings

import pytest

from surrealdb.cbor import decoder, encoder, types


def test_deprecated_decoder_module():
    """Test that the deprecated decoder module works and emits a warning."""
    # The warning is emitted at import time, so we need to import it fresh
    import importlib
    import warnings

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Re-import to trigger the warning
        importlib.reload(decoder)

        # Test that imports work
        assert hasattr(decoder, "CBORDecoder")
        assert hasattr(decoder, "load")
        assert hasattr(decoder, "loads")

        # Check that warning was emitted
        assert len(w) >= 1  # type: ignore
        assert any("deprecated" in str(warning.message) for warning in w)  # type: ignore


def test_deprecated_encoder_module():
    """Test that the deprecated encoder module works and emits a warning."""
    # The warning is emitted at import time, so we need to import it fresh
    import importlib
    import warnings

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Re-import to trigger the warning
        importlib.reload(encoder)

        # Test that imports work
        assert hasattr(encoder, "CBOREncoder")
        assert hasattr(encoder, "dump")
        assert hasattr(encoder, "dumps")
        assert hasattr(encoder, "shareable_encoder")

        # Check that warning was emitted
        assert len(w) >= 1  # type: ignore
        assert any("deprecated" in str(warning.message) for warning in w)  # type: ignore


def test_deprecated_types_module():
    """Test that the deprecated types module works and emits a warning."""
    # The warning is emitted at import time, so we need to import it fresh
    import importlib
    import warnings

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        # Re-import to trigger the warning
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

        # Check that warning was emitted
        assert len(w) >= 1  # type: ignore
        assert any("deprecated" in str(warning.message) for warning in w)  # type: ignore
