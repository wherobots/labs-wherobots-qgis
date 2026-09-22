"""Tests for the SQL-construction hardening.

A third-party scan flagged table and schema names being interpolated straight
into statements. Identifiers cannot be parameter-bound in any dialect, so the
plugin validates and backtick-quotes them instead. These tests pin that
behaviour, and guard the narrowed exception handling in ``_to_bytes`` that
replaced a bare ``except Exception: pass``.
"""

import base64

import pytest

from tests.support import clear_logged_messages, install_qgis_stubs

install_qgis_stubs()

from wherobots_qgis.utils.sql import (  # noqa: E402
    escape_string_literal,
    quote_column,
    quote_identifier,
    quote_qualified_name,
)


# --- Identifier quoting ----------------------------------------------------

def test_qualified_name_is_backtick_quoted_per_part():
    assert (
        quote_qualified_name("wherobots_open_data.overture.places")
        == "`wherobots_open_data`.`overture`.`places`"
    )


def test_single_part_name_is_quoted():
    assert quote_qualified_name("places") == "`places`"


def test_surrounding_whitespace_is_trimmed():
    assert quote_qualified_name("  db . table  ") == "`db`.`table`"


@pytest.mark.parametrize(
    "hostile",
    [
        "places; DROP TABLE users",
        "places`; DROP TABLE users; SELECT `",
        "a.`b`.c",
    ],
)
def test_injection_attempts_are_neutralised(hostile):
    """A backtick is rejected outright; anything else loses its meaning."""
    if "`" in hostile:
        with pytest.raises(ValueError):
            quote_qualified_name(hostile)
    else:
        quoted = quote_qualified_name(hostile)
        assert quoted.startswith("`") and quoted.endswith("`")
        # The whole hostile string is trapped inside one quoted identifier.
        assert quoted == f"`{hostile}`"


@pytest.mark.parametrize("bad", ["", "   ", None, "db.", ".table", "a..b"])
def test_empty_or_malformed_names_are_rejected(bad):
    with pytest.raises(ValueError):
        quote_qualified_name(bad)


def test_quote_identifier_rejects_backticks():
    with pytest.raises(ValueError):
        quote_identifier("ge`om")


def test_quote_column_quotes_a_single_name():
    assert quote_column("geometry") == "`geometry`"


def test_legitimate_odd_names_still_work():
    """Backtick quoting keeps names that a strict allowlist would reject."""
    assert quote_qualified_name("my-db.my table") == "`my-db`.`my table`"


# --- String literals -------------------------------------------------------

def test_single_quotes_are_doubled():
    assert escape_string_literal("O'Hara") == "O''Hara"


def test_literal_escaping_defuses_a_quote_break_out():
    assert escape_string_literal("x'); DROP TABLE t; --") == "x''); DROP TABLE t; --"


def test_trailing_backslash_cannot_escape_the_closing_quote():
    """The bypass: Spark treats a backslash as live in a string literal, so an
    attribute ending in one would escape the quote the caller appends."""
    assert escape_string_literal("foo\\") == "foo\\\\"


def test_a_value_mixing_backslashes_and_quotes_escapes_both():
    assert escape_string_literal("a\\'b") == "a\\\\''b"


def test_backslash_quote_break_out_is_neutralised():
    hostile = "x\\'); DROP TABLE t; --"
    assert escape_string_literal(hostile) == "x\\\\''); DROP TABLE t; --"


def test_ordinary_windows_style_paths_round_trip():
    """Doubling is the escaped form, not corruption: Spark reads it back as
    the original single backslashes."""
    assert escape_string_literal("C:\\data\\layer") == "C:\\\\data\\\\layer"


# --- _to_bytes: the narrowed excepts must not change behaviour -------------

@pytest.fixture
def to_bytes():
    clear_logged_messages()
    from wherobots_qgis.core.raster_task import _to_bytes

    return _to_bytes


def test_to_bytes_passes_through_raw_bytes(to_bytes):
    assert to_bytes(b"\x49\x49\x2a\x00") == b"\x49\x49\x2a\x00"


def test_to_bytes_decodes_base64(to_bytes):
    payload = b"\x49\x49\x2a\x00rasterbody"
    assert to_bytes(base64.b64encode(payload).decode()) == payload


def test_to_bytes_decodes_hex(to_bytes):
    # 9 bytes → an 18-character hex string, which is not valid base64, so the
    # base64 attempt falls through to the hex branch as intended.
    payload = b"\x49\x49\x2a\x00raste"
    assert to_bytes(payload.hex()) == payload


def test_to_bytes_returns_none_for_plain_text(to_bytes):
    assert to_bytes("not encoded binary at all!") is None


def test_to_bytes_uses_tobytes(to_bytes):
    class Arrayish:
        def tobytes(self):
            return b"\x4d\x4d\x00\x2a"

    assert to_bytes(Arrayish()) == b"\x4d\x4d\x00\x2a"


def test_failing_tobytes_is_logged_not_swallowed(to_bytes):
    from tests.support import logged_messages

    class Broken:
        def tobytes(self):
            raise TypeError("no buffer interface")

    assert to_bytes(Broken()) is None
    assert any("tobytes() failed" in m[0] for m in logged_messages())


# --- The log sink must never break its caller -----------------------------

def test_a_failing_log_sink_does_not_raise_and_is_counted():
    """The handler cannot log its own failure, so it counts the drop instead
    of swallowing it silently (replaces a bare ``except: pass``)."""
    import sys

    from wherobots_qgis.utils import logging as plugin_log

    sink = sys.modules["qgis.core"].QgsMessageLog
    before = plugin_log.dropped_count()

    def boom(message, tag="", level=0):
        raise RuntimeError("C++ object already deleted")

    original = sink.logMessage
    sink.logMessage = staticmethod(boom)
    try:
        plugin_log.log_warning("close failed during unload")  # must not raise
    finally:
        sink.logMessage = original

    assert plugin_log.dropped_count() == before + 1
