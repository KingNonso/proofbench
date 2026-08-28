"""The shared strict model base.

Every persisted or exchanged model in ProofBench is frozen, rejects unknown
fields, and carries a ``schema_version``. Rejecting unknown fields is not
pedantry: a case file with a misspelled ``expected_state`` key that was silently
ignored would look valid and measure nothing.

This lives apart from any one domain so that case, evidence, decision, and trace
models can share it without importing each other.
"""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict

# SQL identifiers reaching psycopg.sql.Identifier are validated against this
# first. Quoting is correct on its own; validating as well means a malformed
# identifier fails as data at the boundary rather than as SQL deep in a world.
_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


class StrictModel(BaseModel):
    """Base for every persisted model: unknown fields are rejected, not ignored."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _check_identifier(raw: str) -> str:
    if not _IDENTIFIER.match(raw):
        raise ValueError(
            "must be a lowercase unquoted SQL identifier: "
            "letters, digits, and underscore, not starting with a digit"
        )
    return raw


SqlIdentifier = Annotated[str, AfterValidator(_check_identifier)]
