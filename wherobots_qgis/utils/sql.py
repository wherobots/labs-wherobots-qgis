"""Safe construction of SQL fragments from user-supplied names and values.

The Wherobots DB-API cannot bind identifiers (no dialect can), and table or
schema names in this plugin come straight from free-text widgets. So every
identifier that ends up in a statement goes through here first: each dotted
part is validated and wrapped in backticks, which is the Spark SQL quoting
form Wherobots uses. Backtick quoting keeps legitimate names containing
spaces or dashes working while stripping any meaning from ``;``, quotes and
whitespace.

This module deliberately imports nothing from QGIS so it can be unit tested
without a QGIS runtime.
"""


def quote_identifier(part):
    """Backtick-quote a single identifier part.

    :param part: one component of a name, e.g. ``places``
    :returns: the part wrapped in backticks
    :raises ValueError: if the part is empty or contains a backtick
    """
    if part is None:
        raise ValueError("Identifier cannot be empty.")
    part = str(part).strip()
    if not part:
        raise ValueError("Identifier cannot be empty.")
    if "`" in part:
        raise ValueError(
            f"Invalid identifier {part!r}: backticks are not allowed in names."
        )
    return f"`{part}`"


def quote_qualified_name(name):
    """Validate and backtick-quote a possibly dotted name.

    ``wherobots_open_data.overture.places`` becomes
    ``` `wherobots_open_data`.`overture`.`places` ```.

    :param name: a table or schema name, optionally dot-qualified
    :returns: the fully quoted name
    :raises ValueError: if the name is empty or any part is invalid
    """
    if name is None:
        raise ValueError("Name cannot be empty.")
    name = str(name).strip()
    if not name:
        raise ValueError("Name cannot be empty.")
    parts = name.split(".")
    if any(not p.strip() for p in parts):
        raise ValueError(
            f"Invalid name {name!r}: expected catalog.database.table with no "
            "empty parts."
        )
    return ".".join(quote_identifier(p) for p in parts)


def quote_column(name):
    """Backtick-quote a single column name."""
    return quote_identifier(name)


def escape_string_literal(value):
    """Escape a value for embedding inside a single-quoted SQL literal.

    Returns the inner text only — the caller supplies the surrounding quotes.
    """
    return str(value).replace("'", "''")
