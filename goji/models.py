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
