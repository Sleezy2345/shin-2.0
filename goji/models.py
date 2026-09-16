from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Provenance:
    provider: str
    source_id: str
    observed_at: datetime


@dataclass(frozen=True)
class NormalizedEvent:
    event_id: str
    league: str
    home_team: str
    away_team: str
    starts_at: datetime
    provenance: Provenance


@dataclass(frozen=True)
class PredictionInput:
    prediction_id: str
    sport: str
    prediction_type: str
    selection: str
    features: dict[str, Any]
    provenance: tuple[Provenance, ...]


@dataclass(frozen=True)
class PredictionDecision:
    prediction_id: str
    selection: str
    model_probability: float | None
    market_implied_probability: float | None
    model_status: str
    roar_action: str
    reason: str


@dataclass(frozen=True)
class PregameCandidate:
    prediction_id: str
    sport: str
    game_id: str
    prediction_type: str
    selection: str
    market_key: str
    independent_group_key: str
    inputs: dict[str, Any]
    features: dict[str, Any]
    provenance: tuple[Provenance, ...]
    context: dict[str, Any]


@dataclass(frozen=True)
class ValidationState:
    decision: str
    reasons: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"decision": self.decision, "reasons": list(self.reasons)}


@dataclass(frozen=True)
class PreparedSlate:
    slate_id: str
    predictions: tuple[dict[str, Any], ...]
    blocked: tuple[dict[str, Any], ...]
