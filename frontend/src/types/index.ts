export interface HealthCheck {
  status: string;
  database: boolean;
  version: string;
}

export interface SeasonSummary {
  id: number;
  name: string;
  status: string;
  total_participants: number;
}

export interface SeasonDetail {
  id: number;
  name: string;
  status: string;
  matchday_start: number;
  matchday_end: number | null;
  matchday_current: number;
  matchday_winter: number | null;
  matchday_scanned: number;
  draft_pool_size: number;
  lineup_deadline_min: number;
  total_participants: number;
  created_at: string;
}

export interface ScoringRule {
  id: number;
  rule_key: string;
  position: string | null;
  value: string;
  description: string | null;
}

export interface ValidFormation {
  id: number;
  formation: string;
  defenders: number;
  midfielders: number;
  forwards: number;
}

export interface StandingEntry {
  rank: number;
  participant_id: number;
  display_name: string;
  total_points: number;
  matchdays_played: number;
  avg_points: number;
}

export interface StandingsResponse {
  season_id: number;
  season_name: string;
  entries: StandingEntry[];
}

export interface MatchdaySummaryItem {
  number: number;
  status: string;
  counts: boolean;
  stats_ok: boolean;
  first_match_at: string | null;
}

export interface MatchdayListResponse {
  season_id: number;
  matchdays: MatchdaySummaryItem[];
}

export interface MatchEntry {
  id: number;
  home_team: string;
  away_team: string;
  home_score: number | null;
  away_score: number | null;
  counts: boolean;
  played_at: string | null;
}

export interface ParticipantScore {
  rank: number | null;
  participant_id: number;
  display_name: string;
  total_points: number;
  formation: string | null;
}

export interface MatchdayDetailResponse {
  season_id: number;
  number: number;
  status: string;
  counts: boolean;
  stats_ok: boolean;
  first_match_at: string | null;
  matches: MatchEntry[];
  scores: ParticipantScore[];
}

export interface ScoreBreakdown {
  pts_play: number;
  pts_starter: number;
  pts_result: number;
  pts_clean_sheet: number;
  pts_goals: number;
  pts_assists: number;
  pts_yellow: number;
  pts_red: number;
  pts_marca: number;
  pts_as: number;
  pts_total: number;
}

export interface LineupPlayerEntry {
  display_order: number;
  position_slot: string;
  player_id: number;
  player_name: string;
  team_name: string;
  points: number;
  score_breakdown: ScoreBreakdown | null;
}

export interface LineupDetailResponse {
  participant_id: number;
  display_name: string;
  matchday_number: number;
  formation: string;
  total_points: number;
  players: LineupPlayerEntry[];
}
