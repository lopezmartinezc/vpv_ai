"""Format: 6 jornadas balanced round-robin + KO top-4 (semis + final).

Tailored to 13 participants on 8 VPV matchdays:
- Regular: each participant plays exactly 4 cruces and rests 2 times.
  Distribution per jornada: [5, 5, 5, 5, 3, 3].
- KO: top-4 → semis (1º vs 4º, 2º vs 3º) → final.
"""

from __future__ import annotations

from src.features.competitions.formats.base import FormatPlugin
from src.features.competitions.ko_bracket import chain_winners, seed_classic_bracket
from src.features.competitions.scheduler import generate_balanced_schedule
from src.features.competitions.schemas import MatchupDraft, StandingEntry


class BalancedKo4Plugin(FormatPlugin):
    format_id = "balanced_ko4"
    display_name = "Balanced (4 partidos/uno) + KO top-4"

    def required_rounds_regular(self) -> int:
        return 6

    def required_rounds_ko(self) -> int:
        return 2

    def generate_regular_phase(
        self,
        participants: list[int],
        matchday_ids: list[int],
        seed: int,
    ) -> list[MatchupDraft]:
        if len(participants) != 13:
            raise ValueError(f"balanced_ko4 expects 13 participants, got {len(participants)}")
        if len(matchday_ids) != self.required_rounds_regular():
            raise ValueError(
                f"balanced_ko4 expects {self.required_rounds_regular()} matchdays, "
                f"got {len(matchday_ids)}"
            )
        rounds = generate_balanced_schedule(
            participants,
            n_rounds=6,
            games_per_player=4,
            seed=seed,
        )
        drafts: list[MatchupDraft] = []
        for round_idx, pairs in enumerate(rounds):
            for pair in pairs:
                drafts.append(
                    MatchupDraft(
                        phase="regular",
                        round_number=round_idx + 1,
                        matchday_id=matchday_ids[round_idx],
                        participant_a_id=pair.a,
                        participant_b_id=pair.b,
                        group_label="overall",
                    )
                )
        return drafts

    def generate_ko_phase(
        self,
        standings: list[StandingEntry],
        matchday_ids: list[int],
    ) -> list[MatchupDraft]:
        if len(matchday_ids) != self.required_rounds_ko():
            raise ValueError(
                f"balanced_ko4 expects {self.required_rounds_ko()} KO matchdays, "
                f"got {len(matchday_ids)}"
            )
        top4 = [s.participant_id for s in standings[:4]]
        semis = seed_classic_bracket(top4, round_label="semi", round_number=7)
        final = chain_winners(semis, round_number=8, round_label="final", feeder_offset=0)

        slots = semis + final
        # Map each slot to its destination matchday and to MatchupDraft.
        drafts: list[MatchupDraft] = []
        for slot in slots:
            md_id = matchday_ids[0] if slot.round_label == "semi" else matchday_ids[1]
            drafts.append(
                MatchupDraft(
                    phase="ko",
                    round_number=slot.round_number,
                    matchday_id=md_id,
                    participant_a_id=slot.a_pid,
                    participant_b_id=slot.b_pid,
                    feeder_a_index=slot.feeder_a,
                    feeder_b_index=slot.feeder_b,
                    round_label=slot.round_label,
                )
            )
        return drafts

    def resolve_ko_tie(
        self,
        participant_a_id: int,
        participant_b_id: int,
        standings_snapshot: list[StandingEntry],
    ) -> int:
        ranks = {s.participant_id: s.rank for s in standings_snapshot}
        # The better regular-phase rank (lower number) advances.
        return min(
            (participant_a_id, participant_b_id),
            key=lambda pid: ranks.get(pid, 10_000),
        )
