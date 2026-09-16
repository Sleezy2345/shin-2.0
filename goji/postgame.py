from typing import Any

from .genome import GenomeClient, GenomeError
from .models import PostgameItem, PostgameRunReport, ResolvedOutcome, ScarsDiagnosis
from .molt import Molt
from .postgame_carapace import PostgameCarapace
from .scars import Scars, build_observed_evidence
from .settlement import PlayerPropSettlementEvaluator, TeamSettlementEvaluator
from .sportsgameodds import SportsGameOddsClient, SportsGameOddsError


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


def _diagnosis_from_postmortem(row: dict[str, Any]) -> ScarsDiagnosis:
    postmortem = dict(row.get("postmortem") or {})
    prediction_id = str(row.get("prediction_id") or postmortem.get("prediction_id") or "")
    memory_id = str(row.get("memory_id") or postmortem.get("memory_id") or f"scars:{prediction_id}")
    return ScarsDiagnosis(
        memory_id=memory_id,
        prediction_id=prediction_id,
        expectation_quality=str(postmortem.get("expectation_quality") or "UNKNOWN"),
        reasoning_quality=str(postmortem.get("reasoning_quality") or "UNKNOWN"),
        outcome_informativeness=str(postmortem.get("outcome_informativeness") or "UNKNOWN"),
        variance_class=str(postmortem.get("variance_class") or "UNKNOWN"),
        learning_value=float(postmortem.get("learning_value") or 0.0),
        eligible_for_pattern_learning=postmortem.get("eligible_for_pattern_learning") is True,
        payload=postmortem,
    )


class OperationalPostgame:
    def __init__(
        self,
        *,
        genome: GenomeClient | Any | None = None,
        results_client: SportsGameOddsClient | Any | None = None,
        carapace: PostgameCarapace | None = None,
        team_evaluator: TeamSettlementEvaluator | None = None,
        prop_evaluator: PlayerPropSettlementEvaluator | None = None,
        scars: Scars | None = None,
        molt: Molt | None = None,
    ):
        self.genome = genome or GenomeClient()
        self.results_client = results_client or SportsGameOddsClient()
        self.carapace = carapace or PostgameCarapace()
        self.team_evaluator = team_evaluator or TeamSettlementEvaluator()
        self.prop_evaluator = prop_evaluator or PlayerPropSettlementEvaluator()
        self.scars = scars or Scars()
        self.molt = molt or Molt()

    def run(self, slate_id: str | None = None, *, mode: str = "AUDIT") -> PostgameRunReport:
        mode = mode.upper()
        if mode not in {"AUDIT", "LIVE"}:
            raise ValueError("postgame mode must be AUDIT or LIVE")

        items: list[PostgameItem] = []
        audit_diagnoses: list[tuple[ScarsDiagnosis, dict[str, Any]]] = []
        settlement_queue = list(self.genome.review_queue(slate_id) or [])
        event_ids: list[str] = []
        for row in settlement_queue:
            frozen = _with_provider_event_id(dict(row.get("payload") or {}))
            event_id = _provider_event_id(frozen)
            if event_id and event_id not in event_ids:
                event_ids.append(event_id)

        results_by_id: dict[str, ResolvedOutcome] = {}
        if event_ids:
            try:
                results_by_id = {row.provider_event_id: row for row in self.results_client.finalized_events(event_ids)}
            except SportsGameOddsError as exc:
                for row in settlement_queue:
                    items.append(PostgameItem(
                        prediction_id=str(row.get("prediction_id") or ""),
                        phase="SETTLEMENT",
                        status="UNRESOLVED",
                        reason=str(exc),
                        payload={},
                    ))
                settlement_queue = []

        for row in settlement_queue:
            prediction_id = str(row.get("prediction_id") or "")
            frozen = _with_provider_event_id(dict(row.get("payload") or {}))
            event_id = _provider_event_id(frozen)
            if not event_id:
                items.append(PostgameItem(prediction_id, "SETTLEMENT", "UNRESOLVED", "provider event id is missing", {}))
                continue
            result = results_by_id.get(event_id)
            if result is None:
                items.append(PostgameItem(prediction_id, "SETTLEMENT", "UNRESOLVED", "matching provider result is unavailable", {}))
                continue

            state = self.carapace.evaluate(result, frozen)
            if state.decision == "BLOCKED":
                items.append(PostgameItem(prediction_id, "SETTLEMENT", "UNRESOLVED", _reason(state.reasons), {"result": _result_reference(result)}))
                continue
            if state.decision == "REVIEW_REQUIRED":
                review_payload = {"carapace_state": state.as_dict(), "result": _result_reference(result)}
                if mode == "LIVE":
                    try:
                        self.genome.mark_review_required(prediction_id, row.get("slate_id"), _reason(state.reasons), review_payload)
                    except GenomeError as exc:
                        items.append(PostgameItem(prediction_id, "SETTLEMENT", "ERROR", str(exc), review_payload))
                        continue
                items.append(PostgameItem(prediction_id, "SETTLEMENT", "REVIEW_REQUIRED", _reason(state.reasons), review_payload))
                continue

            if frozen.get("prediction_type") == "TEAM":
                decision = self.team_evaluator.evaluate(frozen, result)
            elif frozen.get("prediction_type") == "PLAYER_PROP":
                decision = self.prop_evaluator.evaluate(frozen, result)
            else:
                decision = None

            if decision is None or decision.outcome == "REVIEW_REQUIRED":
                review_reason = decision.reason if decision is not None else "unsupported prediction type"
                review_payload = {"result": _result_reference(result), "prediction_type": frozen.get("prediction_type")}
                if mode == "LIVE":
                    try:
                        self.genome.mark_review_required(prediction_id, row.get("slate_id"), review_reason, review_payload)
                    except GenomeError as exc:
                        items.append(PostgameItem(prediction_id, "SETTLEMENT", "ERROR", str(exc), review_payload))
                        continue
                items.append(PostgameItem(prediction_id, "SETTLEMENT", "REVIEW_REQUIRED", review_reason, review_payload))
                continue

            payload = _settlement_payload(result, decision)
            if mode == "LIVE":
                try:
                    self.genome.settle(
                        f"settle:{prediction_id}",
                        prediction_id,
                        payload,
                        str(row.get("freeze_fingerprint") or ""),
                    )
                except GenomeError as exc:
                    items.append(PostgameItem(prediction_id, "SETTLEMENT", "ERROR", str(exc), payload))
                    continue
                status = "SETTLED"
            else:
                status = "PROPOSED_SETTLEMENT"
                observed = build_observed_evidence(frozen, payload)
                diagnosis = self.scars.diagnose(prediction_id, frozen, payload, observed)
                audit_diagnoses.append((diagnosis, frozen))
            items.append(PostgameItem(prediction_id, "SETTLEMENT", status, decision.reason, payload))

        if mode == "AUDIT":
            for diagnosis, frozen in audit_diagnoses:
                items.append(PostgameItem(
                    diagnosis.prediction_id,
                    "SCARS",
                    "PROPOSED_POSTMORTEM",
                    "audit diagnosis only; no canonical write",
                    diagnosis.payload,
                ))
                proposal = self.molt.propose(diagnosis, frozen)
                if proposal is not None:
                    items.append(PostgameItem(
                        diagnosis.prediction_id,
                        "MOLT",
                        "PROPOSED_EVIDENCE",
                        "audit hypothesis/evidence only; no canonical write",
                        {"hypothesis": proposal.hypothesis_payload, "evidence": proposal.evidence_payload},
                    ))

        for row in list(self.genome.postmortem_queue(slate_id) or []):
            prediction_id = str(row.get("prediction_id") or "")
            frozen = dict(row.get("verdict_payload") or {})
            settlement_payload = dict(row.get("settlement_payload") or {})
            observed = build_observed_evidence(frozen, settlement_payload)
            diagnosis = self.scars.diagnose(prediction_id, frozen, settlement_payload, observed)
            if mode == "LIVE":
                try:
                    self.genome.record_postmortem(diagnosis.memory_id, prediction_id, diagnosis.payload)
                except GenomeError as exc:
                    items.append(PostgameItem(prediction_id, "SCARS", "ERROR", str(exc), diagnosis.payload))
                    continue
                status = "POSTMORTEM_RECORDED"
            else:
                status = "PROPOSED_POSTMORTEM"
            items.append(PostgameItem(prediction_id, "SCARS", status, "SCARS diagnosis complete", diagnosis.payload))

        for row in list(self.genome.molt_queue(slate_id) or []):
            prediction_id = str(row.get("prediction_id") or "")
            frozen = dict(row.get("verdict_payload") or {})
            diagnosis = _diagnosis_from_postmortem(row)
            proposal = self.molt.propose(diagnosis, frozen)
            if proposal is None:
                items.append(PostgameItem(prediction_id, "MOLT", "NO_PROPOSAL", "postmortem is not eligible for pattern learning", {}))
                continue
            if mode == "LIVE":
                try:
                    self.genome.register_hypothesis(proposal.hypothesis_payload)
                    self.genome.record_experience_evidence(proposal.evidence_payload)
                except GenomeError as exc:
                    items.append(PostgameItem(
                        prediction_id,
                        "MOLT",
                        "ERROR",
                        str(exc),
                        {"hypothesis": proposal.hypothesis_payload, "evidence": proposal.evidence_payload},
                    ))
                    continue
                status = "EVIDENCE_RECORDED"
            else:
                status = "PROPOSED_EVIDENCE"
            items.append(PostgameItem(
                prediction_id,
                "MOLT",
                status,
                "MOLT proposal remains OBSERVED/SHADOW and requires human approval",
                {"hypothesis": proposal.hypothesis_payload, "evidence": proposal.evidence_payload},
            ))

        return PostgameRunReport(slate_id=slate_id, mode=mode, items=tuple(items))
