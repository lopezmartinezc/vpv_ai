"""Format: full Berger round-robin + KO top-8 (cuartos + semis + final).

Designed for Liga playoffs (Apertura / Clausura). 13 jornadas Berger
con BYE para 13 participantes (cada uno juega 12, descansa 1); 11
rondas si fueran 12 (par); adapta a cualquier N.

KO siempre top-8 a 3 jornadas: cuartos, semis, final.
"""

from __future__ import annotations

import random

from src.features.competitions.formats.base import FormatPlugin
from src.features.competitions.ko_bracket import chain_winners, seed_classic_bracket
from src.features.competitions.scheduler import generate_berger
from src.features.competitions.schemas import MatchupDraft, StandingEntry


class LigaBergerKo8Plugin(FormatPlugin):
    format_id = "liga_berger_ko8"
    display_name = "Liga round-robin completo + KO top-8"

    def required_rounds_regular(self, n_participants: int) -> int:
        # Berger schedule: N-1 rounds if even, N rounds if odd (with BYE).
        return n_participants - 1 if n_participants % 2 == 0 else n_participants

    def required_rounds_ko(self) -> int:
        # Cuartos + semis + final.
        return 3

    def generate_regular_phase(
        self,
        participants: list[int],
        matchday_ids: list[int],
        seed: int,
    ) -> list[MatchupDraft]:
        n = len(participants)
        if n < 4:
            raise ValueError(f"liga_berger_ko8 needs at least 4 participants, got {n}")
        expected = self.required_rounds_regular(n)
        if len(matchday_ids) != expected:
            raise ValueError(
                f"liga_berger_ko8 expects {expected} matchdays for "
                f"{n} participants, got {len(matchday_ids)}"
            )

        # Random shuffle to keep the bracket unpredictable across runs.
        rng = random.Random(seed)
        shuffled = participants[:]
        rng.shuffle(shuffled)

        rounds = generate_berger(shuffled)
        if len(rounds) != expected:
            raise RuntimeError(f"Berger returned {len(rounds)} rounds, expected {expected}")

        drafts: list[MatchupDraft] = []
        for round_idx, round_pairs in enumerate(rounds):
            for pair in round_pairs:
                if pair is None:
                    # Bye position — the participant on that side of
                    # the rotation simply rests this round. No matchup
                    # to insert.
                    continue
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
        n_regular_rounds: int,
    ) -> list[MatchupDraft]:
        if len(matchday_ids) != self.required_rounds_ko():
            raise ValueError(
                f"liga_berger_ko8 expects {self.required_rounds_ko()} KO matchdays, "
                f"got {len(matchday_ids)}"
            )
        # Same tie-detection contract as balanced_ko4 — refuse to start
        # if there is an unresolved tie in the top-8 cutoff (or at the
        # 8º/9º boundary that decides who's in).
        boundary = standings[:9]
        seen_ranks: dict[int, list[str]] = {}
        for s in boundary:
            seen_ranks.setdefault(s.rank, []).append(s.display_name)
        ties = [(rank, names) for rank, names in seen_ranks.items() if len(names) > 1]
        if ties:
            tied_msg = "; ".join(f"rank {rank}: {', '.join(names)}" for rank, names in ties)
            raise ValueError(
                "Empate sin desempate dentro del top-8 del playoff. "
                "Resuelve antes de iniciar las eliminatorias: " + tied_msg
            )

        top8 = [s.participant_id for s in standings[:8]]
        cuartos = seed_classic_bracket(
            top8, round_label="quarter", round_number=n_regular_rounds + 1
        )
        semis = chain_winners(
            cuartos,
            round_number=n_regular_rounds + 2,
            round_label="semi",
            feeder_offset=0,
        )
        final = chain_winners(
            semis,
            round_number=n_regular_rounds + 3,
            round_label="final",
            feeder_offset=len(cuartos),
        )

        slots = cuartos + semis + final
        drafts: list[MatchupDraft] = []
        for slot in slots:
            md_id = matchday_ids[slot.round_number - n_regular_rounds - 1]
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
        return min(
            (participant_a_id, participant_b_id),
            key=lambda pid: ranks.get(pid, 10_000),
        )
