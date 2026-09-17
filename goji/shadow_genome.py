"""Only three allowlisted SHADOW functions, under an independent PostgreSQL LOGIN.

This module has no access to canonical write RPCs and never falls back to the
Supabase service key. Connections are opened per operation and closed promptly.
"""

import json
from typing import Any, Callable, Mapping

from .shadow_db_config import ShadowDatabaseConfig


class ShadowGenomeError(RuntimeError):
    """Sanitized database failure: never expose a DSN, password or server error."""


class ShadowGenome:
    def __init__(
        self,
        *,
        config: ShadowDatabaseConfig | None = None,
        environ: Mapping[str, str] | None = None,
        connector: Callable[..., Any] | None = None,
    ) -> None:
        # Validate the separate SHADOW flag/DSN before importing a driver or connecting.
        self._config = config if config is not None else ShadowDatabaseConfig.from_env(environ)
        self._connector = connector

    def _connect(self) -> Any:
        connector = self._connector
        if connector is None:
            import psycopg
            from psycopg.rows import dict_row
            return psycopg.connect(self._config.dsn, connect_timeout=5, row_factory=dict_row)
        return connector(self._config.dsn, connect_timeout=5)

    def ready(self) -> dict[str, Any]:
        try:
            with self._connect() as conn:
                conn.read_only = True
                with conn.cursor() as cursor:
                    cursor.execute("SELECT public.genome_shadow_ready() AS status")
                    row = cursor.fetchone()
            status = row.get("status") if isinstance(row, dict) else None
            if not isinstance(status, dict) or status.get("schema") != "SHADOW/0.3" or status.get("ready") is not True:
                raise ShadowGenomeError("SHADOW schema is not ready")
            return status
        except ShadowGenomeError:
            raise
        except Exception:
            raise ShadowGenomeError("SHADOW database operation failed") from None

    def queue(self, slate_id: str | None = None) -> list[dict[str, Any]]:
        if slate_id is not None and (not isinstance(slate_id, str) or not slate_id.strip()):
            raise ShadowGenomeError("Invalid SHADOW slate id")
        try:
            with self._connect() as conn:
                conn.read_only = True
                with conn.cursor() as cursor:
                    cursor.execute("SELECT * FROM public.genome_shadow_queue(%s)", (slate_id,))
                    rows = cursor.fetchall()
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise ShadowGenomeError("Invalid SHADOW queue response")
            return rows
        except ShadowGenomeError:
            raise
        except Exception:
            raise ShadowGenomeError("SHADOW database operation failed") from None

    def record(self, prediction_id: str, observation: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(prediction_id, str) or not prediction_id.strip() or not isinstance(observation, dict):
            raise ShadowGenomeError("Invalid SHADOW observation")
        try:
            payload = json.dumps(observation, sort_keys=True, allow_nan=False)
        except (TypeError, ValueError):
            raise ShadowGenomeError("Invalid SHADOW observation") from None
        try:
            with self._connect() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT public.genome_shadow_record(%s, %s::jsonb) AS result",
                        (prediction_id, payload),
                    )
                    row = cursor.fetchone()
            result = row.get("result") if isinstance(row, dict) else None
            if not isinstance(result, dict) or not isinstance(result.get("created"), bool):
                raise ShadowGenomeError("Invalid SHADOW record response")
            return result
        except ShadowGenomeError:
            raise
        except Exception:
            raise ShadowGenomeError("SHADOW database operation failed") from None
