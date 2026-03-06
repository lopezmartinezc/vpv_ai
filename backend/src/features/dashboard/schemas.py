from __future__ import annotations

from pydantic import BaseModel

from src.features.copa.schemas import CopaFullResponse
from src.features.economy.schemas import EconomyResponse
from src.features.matchdays.schemas import MatchdayDetailResponse
from src.features.standings.schemas import StandingsResponse


class DashboardResponse(BaseModel):
    standings: StandingsResponse | None = None
    current_matchday: MatchdayDetailResponse | None = None
    copa: CopaFullResponse | None = None
    economy: EconomyResponse | None = None
