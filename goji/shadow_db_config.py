"""Fail-closed configuration for the future isolated SHADOW database client.

Parsing a configuration does not connect to GENOME or authorize SHADOW writes.
"""

from dataclasses import dataclass, field
import os
from os.path import isabs
from typing import Mapping
from urllib.parse import parse_qsl, unquote, urlsplit


class ShadowDatabaseConfigError(RuntimeError):
    """A sanitized configuration failure; never include a secret URI."""


@dataclass(frozen=True)
class ShadowDatabaseConfig:
    dsn: str = field(repr=False)

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "ShadowDatabaseConfig":
        variables = os.environ if environ is None else environ
        if variables.get("GOJI_SHADOW_ENABLED", "").lower() != "true":
            raise ShadowDatabaseConfigError("SHADOW is disabled")
        dsn = variables.get("GOJI_SHADOW_DATABASE_URL", "")
        if not dsn or dsn != dsn.strip():
            raise ShadowDatabaseConfigError("Missing or invalid SHADOW database connection")
        try:
            parsed = urlsplit(dsn)
            query_pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True)
            arguments = dict(query_pairs)
            valid = (
                parsed.scheme == "postgresql"
                and unquote(parsed.username or "") == "goji_shadow_writer"
                and bool(parsed.password)
                and bool(parsed.hostname)
                and parsed.port in (5432, 6543)
                and parsed.path == "/postgres"
                and not parsed.fragment
                and len(query_pairs) == len(arguments) == 2
                and set(arguments) == {"sslmode", "sslrootcert"}
                and arguments["sslmode"] == "verify-full"
                and isabs(arguments["sslrootcert"])
            )
        except (ValueError, TypeError, KeyError):
            valid = False
        if not valid:
            raise ShadowDatabaseConfigError("Invalid restricted SHADOW database configuration")
        return cls(dsn=dsn)
