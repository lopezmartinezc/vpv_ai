"""Format: full Berger round-robin + KO top-8 with a best-of-three final.

The Liga 2026-27 playoffs, Apertura and Clausura (11 participants):

* regular phase: everyone against everyone, 11 jornadas, one rests each;
* cuartos in one jornada: 1-8, 4-5, 2-7, 3-6;
* semis in one jornada: winner 1-8 v winner 4-5, winner 2-7 v winner 3-6;
* the final over three jornadas, best of three (``ko_series``).

The regular table breaks a tie on points by point difference, then head to
head. A drawn cuartos or semis goes to the better regular-phase seed.
"""

from __future__ import annotations

from src.features.competitions.formats.liga_berger_ko8 import LigaBergerKo8Plugin
from src.features.competitions.ko_bracket import KoSlot, chain_winners, seed_classic_bracket
from src.features.competitions.schemas import MatchupDraft, StandingEntry

FINAL_LEGS = 3


class LigaBergerKo8Bo3Plugin(LigaBergerKo8Plugin):
    format_id = "liga_berger_ko8_bo3"
    display_name = "Liga todos contra todos + KO top-8, final al mejor de 3"
    final_legs = FINAL_LEGS
    head_to_head_tiebreak = True

    def required_rounds_ko(self) -> int:
        # Cuartos + semis + the three jornadas of the final.
        return 2 + FINAL_LEGS

    def generate_ko_phase(
        self,
        standings: list[StandingEntry],
        matchday_ids: list[int],
        n_regular_rounds: int,
    ) -> list[MatchupDraft]:
        if len(matchday_ids) != self.required_rounds_ko():
            raise ValueError(
                f"{self.format_id} expects {self.required_rounds_ko()} KO matchdays, "
                f"got {len(matchday_ids)}"
            )
        top8 = self.top8(standings)
        cuartos = seed_classic_bracket(
            top8, round_label="quarter", round_number=n_regular_rounds + 1
        )
        semis = chain_winners(
            cuartos, round_number=n_regular_rounds + 2, round_label="semi", feeder_offset=0
        )
        # Every leg of the final is fed by both semis, so the engine writes
        # the two finalists into all three as soon as each semi is decided.
        first_semi = len(cuartos)
        final = [
            KoSlot(
                round_number=n_regular_rounds + 3 + leg,
                round_label="final",
                feeder_a=first_semi,
                feeder_b=first_semi + 1,
            )
            for leg in range(FINAL_LEGS)
        ]

        drafts: list[MatchupDraft] = []
        for slot in cuartos + semis + final:
            drafts.append(
                MatchupDraft(
                    phase="ko",
                    round_number=slot.round_number,
                    matchday_id=matchday_ids[slot.round_number - n_regular_rounds - 1],
                    participant_a_id=slot.a_pid,
                    participant_b_id=slot.b_pid,
                    feeder_a_index=slot.feeder_a,
                    feeder_b_index=slot.feeder_b,
                    round_label=slot.round_label,
                )
            )
        return drafts
