"""Shared read-only postgame evaluation for AUDIT and future SHADOW.

No GENOME imports, RPCs, or persistence side effects belong in this module.
"""
from typing import Any

from .models import MoltProposal, PostgameItem, ResolvedOutcome, ScarsDiagnosis
from .molt import Molt
from .postgame_carapace import PostgameCarapace
from .scars import Scars, build_observed_evidence
from .settlement import PlayerPropSettlementEvaluator, TeamSettlementEvaluator


def _reason(reasons: tuple[str, ...]) -> str:
    return "; ".join(reasons) or "postgame validation did not pass"


def _provider_event_id(frozen: dict[str, Any]) -> str:
    inputs = frozen.get("inputs") or {}
    explicit = str(inputs.get("provider_event_id") or "").strip()
    if explicit:
        return explicit
    for receipt in frozen.get("provenance") or []:
        if not isinstance(receipt, dict):
            continue
        if str(receipt.get("provider") or "").casefold() == "sportsgameodds":
            source_id = str(receipt.get("source_id") or "").strip()
            if source_id:
                return source_id
    return ""


def _with_provider_event_id(frozen: dict[str, Any]) -> dict[str, Any]:
    resolved = dict(frozen)
    event_id = _provider_event_id(resolved)
    if event_id:
        inputs = dict(resolved.get("inputs") or {})
        inputs.setdefault("provider_event_id", event_id)
        resolved["inputs"] = inputs
    return resolved


def _result_reference(result: ResolvedOutcome) -> dict[str, Any]:
    return {
        "provider_event_id": result.provider_event_id,
        "sport": result.sport,
        "finalized": result.finalized,
        "home_team": result.home_team,
        "away_team": result.away_team,
        "home_score": result.home_score,
        "away_score": result.away_score,
        "observed_at": result.provenance.observed_at.isoformat(),
        "provider": result.provenance.provider,
        "source_id": result.provenance.source_id,
    }


def _settlement_payload(result: ResolvedOutcome, decision: Any) -> dict[str, Any]:
    winner = None
    if result.home_score is not None and result.away_score is not None and result.home_score != result.away_score:
        winner = result.home_team if result.home_score > result.away_score else result.away_team
    actual_state = {
        "winner": winner,
        "home_team": result.home_team,
        "away_team": result.away_team,
        "home_score": result.home_score,
        "away_score": result.away_score,
    }
    if "score" in decision.grading_inputs:
        actual_state["market_score"] = decision.grading_inputs["score"]
    return {
        "outcome": decision.outcome,
        "provider_event_id": result.provider_event_id,
        "sport": result.sport,
        "finalized": result.finalized,
        "grading_inputs": dict(decision.grading_inputs),
        "evaluator_version": decision.evaluator_version,
        "reason": decision.reason,
        "actual_state": actual_state,
        "provenance": [
            {
                "provider": result.provenance.provider,
                "source_id": result.provenance.source_id,
                "observed_at": result.provenance.observed_at.isoformat(),
            }
        ],
    }


def evaluate_candidate(
    row: dict[str, Any],
    result: ResolvedOutcome,
    *,
    carapace: PostgameCarapace,
    team_evaluator: TeamSettlementEvaluator,
    prop_evaluator: PlayerPropSettlementEvaluator,
    scars: Scars,
    molt: Molt,
) -> tuple[PostgameItem, ScarsDiagnosis | None, MoltProposal | None]:
    prediction_id = str(row.get("prediction_id") or "")
    frozen = _with_provider_event_id(dict(row.get("payload") or {}))
    state = carapace.evaluate(result, frozen)
    if state.decision == "BLOCKED":
        return PostgameItem(prediction_id, "SETTLEMENT", "UNRESOLVED", _reason(state.reasons),
                            {"result": _result_reference(result)}), None, None
    if state.decision == "REVIEW_REQUIRED":
        return PostgameItem(prediction_id, "SETTLEMENT", "REVIEW_REQUIRED", _reason(state.reasons),
                            {"carapace_state": state.as_dict(), "result": _result_reference(result)}), None, None

    if frozen.get("prediction_type") == "TEAM":
        decision = team_evaluator.evaluate(frozen, result)
    elif frozen.get("prediction_type") == "PLAYER_PROP":
        decision = prop_evaluator.evaluate(frozen, result)
    else:
        decision = None
    if decision is None or decision.outcome == "REVIEW_REQUIRED":
        reason = decision.reason if decision is not None else "unsupported prediction type"
        return PostgameItem(prediction_id, "SETTLEMENT", "REVIEW_REQUIRED", reason,
                            {"result": _result_reference(result),
                             "prediction_type": frozen.get("prediction_type")}), None, None

    payload = _settlement_payload(result, decision)
    observed = build_observed_evidence(frozen, payload)
    diagnosis = scars.diagnose(prediction_id, frozen, payload, observed)
    proposal = molt.propose(diagnosis, frozen)
    return PostgameItem(prediction_id, "SETTLEMENT", "PROPOSED_SETTLEMENT", decision.reason, payload), diagnosis, proposal
