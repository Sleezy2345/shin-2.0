"""Manual, isolated SHADOW evaluator. Never calls a canonical GENOME writer.

All saved grades are proposals from genuinely pregame-frozen rows; SHADOW
observations are not official settlements, trained experience or promotions.
"""
from typing import Any

from .models import PostgameItem, PostgameRunReport
from .molt import Molt
from .postgame_carapace import PostgameCarapace
from .postgame_evaluation import _result_reference, evaluate_candidate
from .scars import Scars
from .settlement import PlayerPropSettlementEvaluator, TeamSettlementEvaluator
from .shadow_contract import eligible_shadow_freeze
from .shadow_genome import ShadowGenome, ShadowGenomeError
from .sportsgameodds import SportsGameOddsClient, SportsGameOddsError


class ShadowPostgame:
    def __init__(self, *, genome: Any | None = None, results_client: Any | None = None):
        # Construct the restricted login before the results client; missing SHADOW
        # authorization must abort before external network or canonical API access.
        self.genome = genome if genome is not None else ShadowGenome()
        self.results_client = results_client if results_client is not None else SportsGameOddsClient()
        self.carapace = PostgameCarapace()
        self.team_evaluator = TeamSettlementEvaluator()
        self.prop_evaluator = PlayerPropSettlementEvaluator()
        self.scars = Scars()
        self.molt = Molt()

    def run(self, slate_id: str | None = None) -> PostgameRunReport:
        # A missing migration or disabled/invalid restricted credential aborts.
        self.genome.ready()
        queue = self.genome.queue(slate_id)
        if not queue:
            return PostgameRunReport(slate_id, "SHADOW", ())

        items: list[PostgameItem] = []
        event_ids: list[str] = []
        for row in queue:
            frozen = row.get("payload") or {}
            inputs = frozen.get("inputs") if isinstance(frozen, dict) else None
            event_id = inputs.get("provider_event_id") if isinstance(inputs, dict) else None
            if isinstance(event_id, str) and event_id.strip() and event_id not in event_ids:
                event_ids.append(event_id)
        try:
            outcomes = {result.provider_event_id: result for result in self.results_client.finalized_events(event_ids)} if event_ids else {}
        except SportsGameOddsError:
            return PostgameRunReport(slate_id, "SHADOW", tuple(
                PostgameItem(str(row.get("prediction_id") or ""), "SHADOW", "ERROR",
                             "Final-result provider is unavailable; no observation was recorded", {})
                for row in queue
            ))

        for row in queue:
            prediction_id = str(row.get("prediction_id") or "")
            frozen = row.get("payload") or {}
            inputs = frozen.get("inputs") if isinstance(frozen, dict) else None
            event_id = inputs.get("provider_event_id") if isinstance(inputs, dict) else None
            outcome = outcomes.get(event_id) if isinstance(event_id, str) else None
            if outcome is None:
                items.append(PostgameItem(prediction_id, "SHADOW", "UNRESOLVED",
                                          "Matching final result is unavailable", {}))
                continue
            eligibility = eligible_shadow_freeze(row, outcome)
            if eligibility.decision != "PASS":
                status = "REVIEW_REQUIRED" if eligibility.decision == "REVIEW_REQUIRED" else "UNRESOLVED"
                items.append(PostgameItem(prediction_id, "SHADOW", status,
                                          "; ".join(eligibility.reasons), {}))
                continue
            try:
                proposed, diagnosis, proposal = evaluate_candidate(
                    row, outcome, carapace=self.carapace,
                    team_evaluator=self.team_evaluator, prop_evaluator=self.prop_evaluator,
                    scars=self.scars, molt=self.molt,
                )
            except Exception:
                items.append(PostgameItem(prediction_id, "SHADOW", "ERROR",
                                          "SHADOW evaluator failed; no observation recorded", {}))
                continue
            items.append(proposed)
            if proposed.status != "PROPOSED_SETTLEMENT" or diagnosis is None:
                continue
            result_reference = _result_reference(outcome)
            result_reference["provider"] = outcome.provenance.provider.casefold()
            # Deliberately do not include fetch-time provenance in grade: the SQL
            # replay digest excludes timestamps in result, so an identical result
            # must not become another experience merely because it was re-fetched.
            grade = {
                "status": proposed.status,
                "outcome": proposed.payload["outcome"],
                "grading_inputs": proposed.payload["grading_inputs"],
                "evaluator_version": proposed.payload["evaluator_version"],
                "reason": proposed.reason,
            }
            observation = {
                "freeze_fingerprint": row["freeze_fingerprint"],
                "slate_id": row["slate_id"],
                "prediction_type": frozen["prediction_type"],
                "adapter_version": "sgo-results-v1",
                "evaluator_version": grade["evaluator_version"],
                "learning_eligible": False,
                "carapace": eligibility.as_dict(),
                "result": result_reference,
                "grade": grade,
                "scars_proposal": diagnosis.payload,
                "molt_proposal": None if proposal is None else {
                    "hypothesis": proposal.hypothesis_payload,
                    "evidence": proposal.evidence_payload,
                },
            }
            try:
                stored = self.genome.record(prediction_id, observation)
            except ShadowGenomeError:
                items.append(PostgameItem(prediction_id, "SHADOW", "ERROR",
                                          "Restricted SHADOW record failed; canonical state untouched", {}))
                continue
            if not stored["created"]:
                status = "REPLAY_IGNORED"
            elif stored.get("revision_of"):
                status = "CORRECTION_REVIEW"
            else:
                status = "OBSERVATION_RECORDED"
            items.append(PostgameItem(prediction_id, "SHADOW", status,
                                      "SHADOW-only; not official settlement or trained experience",
                                      {"observation_id": stored.get("observation_id"),
                                       "revision_of": stored.get("revision_of"),
                                       "learning_eligible": False}))
        return PostgameRunReport(slate_id, "SHADOW", tuple(items))
