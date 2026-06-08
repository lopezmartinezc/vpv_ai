from __future__ import annotations

from abc import ABC, abstractmethod

from src.features.competitions.schemas import MatchupDraft, StandingEntry


class FormatPlugin(ABC):
    """Defines how a specific playoff format behaves.

    The engine treats every format the same way:
        1. Call ``generate_regular_phase`` once with the participants
           and the matchday ids covering the regular phase.
        2. After the regular phase is fully resolved, call
           ``generate_ko_phase`` with the final standings.
        3. When the engine recalculates a matchup and the score is
           tied in a KO cruce, ask the plugin via ``resolve_ko_tie``
           which participant advances.

    Plugins are stateless singletons stored in
    ``competitions.formats.FORMAT_REGISTRY``.
    """

    format_id: str = ""
    display_name: str = ""

    @abstractmethod
    def required_rounds_regular(self) -> int:
        """How many matchday slots the regular phase needs."""

    @abstractmethod
    def required_rounds_ko(self) -> int:
        """How many matchday slots the KO phase needs."""

    @abstractmethod
    def generate_regular_phase(
        self,
        participants: list[int],
        matchday_ids: list[int],
        seed: int,
    ) -> list[MatchupDraft]:
        """Produce all regular-phase cruces. ``len(matchday_ids)`` must
        equal ``required_rounds_regular()``. Draft entries here never
        carry feeder indices — only direct participants — and
        ``phase`` is set to ``'regular'`` by the engine."""

    @abstractmethod
    def generate_ko_phase(
        self,
        standings: list[StandingEntry],
        matchday_ids: list[int],
    ) -> list[MatchupDraft]:
        """Produce KO cruces. ``standings`` is the flat list of every
        participant (regardless of group) ordered by the engine using
        the standard tiebreakers — the plugin can slice it however its
        bracket logic requires. Drafts may reference earlier slots in
        the same list via ``feeder_a_index`` / ``feeder_b_index``;
        the engine resolves those to DB ids after the first flush."""

    @abstractmethod
    def resolve_ko_tie(
        self,
        participant_a_id: int,
        participant_b_id: int,
        standings_snapshot: list[StandingEntry],
    ) -> int:
        """Return the participant_id that advances when a KO cruce
        ends in a draw. ``standings_snapshot`` is the regular phase
        ranking cached when the KO was started."""

    def standings_groups(self) -> list[str]:
        """Group labels for the standings UI. Default: a single
        ``'overall'`` table; formats with groups override (e.g.
        ``['A', 'B']``)."""
        return ["overall"]
