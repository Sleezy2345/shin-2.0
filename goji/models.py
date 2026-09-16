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
class MarketResult:
    odd_id: str
    score: float | None
    scoring_supported: bool


@dataclass(frozen=True)
class ResolvedOutcome:
    provider_event_id: str
    sport: str
    finalized: bool
    home_team: str
    away_team: str
    home_score: float | None
    away_score: float | None
    market_results: dict[str, MarketResult]
    players: dict[str, dict[str, Any]]
    provenance: Provenance
    raw_reference: dict[str, Any]


@dataclass(frozen=True)
class SettlementDecision:
    outcome: str
    reason: str
    grading_inputs: dict[str, Any]
    evaluator_version: str


@dataclass(frozen=True)
class ScarsDiagnosis:
    memory_id: str
    prediction_id: str
    expectation_quality: str
    reasoning_quality: str
    outcome_informativeness: str
    variance_class: str
    learning_value: float
    eligible_for_pattern_learning: bool
    payload: dict[str, Any]


@dataclass(frozen=True)
class MoltProposal:
    hypothesis_payload: dict[str, Any]
    evidence_payload: dict[str, Any]


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
