export interface HealthCheck {
  status: string;
  database: boolean;
  version: string;
}

export interface SeasonSummary {
  id: number;
  name: string;
  status: string;
  matchday_current: number;
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
  photo_path: string | null;
  team_name: string;
  points: number;
  score_breakdown: ScoreBreakdown | null;
}

export interface BenchPlayerEntry {
  player_id: number;
  player_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  matchday_points: number;
  score_breakdown: ScoreBreakdown | null;
}

export interface LineupDetailResponse {
  participant_id: number;
  display_name: string;
  matchday_number: number;
  formation: string;
  total_points: number;
  players: LineupPlayerEntry[];
  bench: BenchPlayerEntry[];
}

export interface PositionCounts {
  POR: number;
  DEF: number;
  MED: number;
  DEL: number;
}

export interface SquadSummary {
  participant_id: number;
  display_name: string;
  total_players: number;
  season_points: number;
  positions: PositionCounts;
}

export interface SquadListResponse {
  season_id: number;
  squads: SquadSummary[];
}

export interface SquadPlayerEntry {
  player_id: number;
  display_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  season_points: number;
}

export interface SquadDetailResponse {
  participant_id: number;
  display_name: string;
  season_points: number;
  players: SquadPlayerEntry[];
}

// Drafts
export interface DraftSummary {
  id: number;
  phase: string;
  draft_type: string;
  status: string;
  total_picks: number;
  started_at: string | null;
  completed_at: string | null;
}

export interface DraftListResponse {
  season_id: number;
  drafts: DraftSummary[];
}

export interface DraftParticipant {
  participant_id: number;
  display_name: string;
  draft_order: number | null;
}

export interface DraftPickEntry {
  pick_number: number;
  round_number: number;
  participant_id: number;
  display_name: string;
  draft_order: number | null;
  player_name: string;
  position: string;
  team_name: string;
}

export interface DraftDetailResponse {
  season_id: number;
  phase: string;
  draft_type: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  participants: DraftParticipant[];
  picks: DraftPickEntry[];
}

// Economy
export interface ParticipantBalance {
  participant_id: number;
  display_name: string;
  initial_fee: number;
  weekly_total: number;
  draft_fees: number;
  net_balance: number;
}

export interface EconomyResponse {
  season_id: number;
  balances: ParticipantBalance[];
}

export interface TransactionEntry {
  id: number;
  type: string;
  amount: number;
  description: string | null;
  matchday_number: number | null;
  created_at: string;
}

export interface ParticipantEconomyResponse {
  participant_id: number;
  display_name: string;
  net_balance: number;
  transactions: TransactionEntry[];
}

// Lineup submission ("my lineup" endpoint)
export interface LineupPlayerResponseData {
  player_id: number;
  player_name: string;
  position_slot: string;
  display_order: number;
  photo_path: string | null;
}

export interface CurrentLineupData {
  lineup_id: number;
  formation: string;
  confirmed: boolean;
  confirmed_at: string | null;
  telegram_sent: boolean;
  players: LineupPlayerResponseData[];
}

export interface MyLineupResponse {
  participant_id: number;
  display_name: string;
  lineup_deadline_min: number;
  current_lineup: CurrentLineupData | null;
  squad: SquadPlayerEntry[];
}

// Copa
export interface CopaMatchdayResult {
  participant_id: number;
  display_name: string;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
}

export interface CopaMatchdayDetail {
  matchday_number: number;
  results: CopaMatchdayResult[];
}

export interface CopaStandingEntry {
  rank: number;
  participant_id: number;
  display_name: string;
  total_points: number;
  matches_played: number;
  wins: number;
  draws: number;
  losses: number;
  total_goals_for: number;
  total_goals_against: number;
  goal_difference: number;
}

export interface CopaFullResponse {
  season_id: number;
  season_name: string;
  standings: CopaStandingEntry[];
  matchdays: CopaMatchdayDetail[];
}

// Dashboard (combined endpoint)
export interface DashboardResponse {
  standings: StandingsResponse | null;
  current_matchday: MatchdayDetailResponse | null;
  copa: CopaFullResponse | null;
  economy: EconomyResponse | null;
}

// ---------------------------------------------------------------------------
// Stats (admin) — matches backend/src/features/stats/schemas.py
// ---------------------------------------------------------------------------

export interface PlayerStatRow {
  player_id: number;
  display_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  goals: number;
  penalty_goals: number;
  own_goals: number;
  assists: number;
  penalties_saved: number;
  yellow_cards: number;
  red_cards: number;
  avg_marca: number | null;
  avg_as: number | null;
  minutes_played: number;
  matchdays_played: number;
  started_count: number;
  avg_points: number;
  total_points: number;
}

export interface PlayerStatsResponse {
  season_id: number;
  players: PlayerStatRow[];
}

export interface ParticipantBreakdown {
  participant_id: number;
  display_name: string;
  pts_play: number;
  pts_result: number;
  pts_clean_sheet: number;
  pts_goals: number;
  pts_assists: number;
  pts_yellow: number;
  pts_red: number;
  pts_marca_as: number;
  pts_total: number;
}

export interface ParticipantExtremes {
  participant_id: number;
  display_name: string;
  best_points: number;
  best_matchday: number;
  worst_points: number;
  worst_matchday: number;
  avg_points: number;
}

export interface EvolutionEntry {
  matchday_number: number;
  participant_id: number;
  display_name: string;
  points: number;
  cumulative: number;
}

export interface ParticipantStatsResponse {
  season_id: number;
  breakdowns: ParticipantBreakdown[];
  extremes: ParticipantExtremes[];
  evolution: EvolutionEntry[];
}

export interface FormationUsage {
  formation: string;
  usage_count: number;
}

export interface MostLinedUpPlayer {
  player_id: number;
  display_name: string;
  position: string;
  team_name: string;
  photo_path: string | null;
  times_lined_up: number;
}

export interface MatchdayAverageEntry {
  matchday_number: number;
  avg_points: number;
  max_points: number;
  min_points: number;
}

export interface RecordEntry {
  label: string;
  value: string;
  detail: string;
}

export interface LeagueStatsResponse {
  season_id: number;
  formations: FormationUsage[];
  most_lined_up: MostLinedUpPlayer[];
  matchday_averages: MatchdayAverageEntry[];
  records: RecordEntry[];
}
