from typing import Any

import requests

from .config import GenomeConfig


class GenomeError(RuntimeError):
    pass


class GenomeClient:
    def __init__(self, config: GenomeConfig | None = None, *, session: requests.Session | Any | None = None):
        self.config = config or GenomeConfig.from_env()
        self.session = session or requests.Session()

    def _rpc(self, function_name: str, payload: dict[str, Any]) -> Any:
        try:
            response = self.session.post(
                f"{self.config.url}/rest/v1/rpc/{function_name}",
                headers={
                    "apikey": self.config.service_role_key,
                    "Authorization": f"Bearer {self.config.service_role_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise GenomeError(f"GENOME RPC {function_name} failed: {type(exc).__name__}") from exc

    def freeze_slate(self, slate_id: str, predictions: list[dict], blocked: list[dict] | None = None) -> Any:
        return self._rpc(
            "genome_freeze_slate",
            {"p_slate_id": slate_id, "p_predictions": predictions, "p_blocked": blocked or []},
        )

    def review_queue(self, slate_id: str | None = None) -> Any:
        return self._rpc("genome_review_queue", {"p_slate_id": slate_id})

    def scoreboards(self, sport: str | None = None) -> Any:
        return self._rpc("genome_scoreboards", {"p_sport": sport})

    def record_wager_link(
        self,
        wager_id: str,
        prediction_id: str,
        platform: str,
        slip_id: str | None = None,
        stake: float | None = None,
        metadata: dict | None = None,
    ) -> Any:
        return self._rpc(
            "genome_record_wager_link",
            {
                "p_wager_id": wager_id,
                "p_prediction_id": prediction_id,
                "p_platform": platform,
                "p_slip_id": slip_id,
                "p_stake": stake,
                "p_metadata": metadata or {},
            },
        )
