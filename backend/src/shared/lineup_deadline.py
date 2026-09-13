"""When a jornada's lineups close, and when they may be seen.

Two questions with one answer. The deadline was computed in two places in
``LineupService`` — once to refuse a late lineup, once to tell the participant
how long he has left — and a third copy was about to appear to decide whether a
rival's lineup may be read. Three copies of a rule drift; one does not.

The effective deadline is the matchday's precomputed ``deadline_at`` when there
is one (that is where an explicit override lives), otherwise the first kick-off
minus the season's ``lineup_deadline_min``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

# A jornada that is over. The scraper marks it "finished"; seasons migrated from
# the old site call it "completed". Treating only one as over would hide every
# lineup of every past season. ``stats_ok`` is the third signal: a jornada whose
# stats are in has been played, whatever its status says.
_PLAYED = frozenset({"finished", "completed"})


def effective_deadline(matchday: object, lineup_deadline_min: int) -> datetime | None:
    """The moment lineups close for ``matchday``, or ``None`` if nothing says."""
    deadline: datetime | None = getattr(matchday, "deadline_at", None)
    if deadline is None:
        first_match: datetime | None = getattr(matchday, "first_match_at", None)
        if first_match is None:
            return None
        deadline = first_match - timedelta(minutes=lineup_deadline_min)
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    return deadline


def lineups_are_public(
    matchday: object, lineup_deadline_min: int, *, now: datetime | None = None
) -> bool:
    """Whether anyone may see every participant's lineup for this jornada.

    A lineup is the one secret in the game: seen before the deadline, it can be
    copied or countered. So they open when the deadline passes, or once the
    jornada is finished. With no deadline information and the jornada still open,
    they stay closed — guessing "open" is the mistake that cannot be undone.
    """
    if getattr(matchday, "status", None) in _PLAYED or getattr(matchday, "stats_ok", False):
        return True
    deadline = effective_deadline(matchday, lineup_deadline_min)
    if deadline is None:
        return False
    return (now or datetime.now(UTC)) >= deadline
