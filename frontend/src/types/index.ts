export interface PlayerPrediction {
  player_id: number;
  player_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  opponent_name: string;
  is_home: boolean;
  season_avg: number;
  form_5: number | null;
  location_avg: number | null;
  rival_factor: number;
  xpts: number;
  xpts_floor: number;
  xpts_ceiling: number;
  confidence: string;
  trend: string;
  matchdays_played: number;
  starter_pct: number;
  is_penalty_taker: boolean;
}

export interface OpponentDifficulty {
  team_name: string;
  goals_conceded_avg: number;
  clean_sheet_pct: number;
  difficulty: string;
}

export interface PredictionsResponse {
  season_id: number;
  matchday_number: number;
  predictions: PlayerPrediction[];
  opponent_rankings: OpponentDifficulty[];
}

export interface PlayerDraftStats {
  player_id: number;
  avg_pts: number;
  std_dev: number;
  form_5: number | null;
  trend: string;
  matchdays_played: number;
  starter_pct: number;
}

export interface DraftPlayerStatsResponse {
  players: Record<string, PlayerDraftStats>;
  suggestions: Record<string, number[]>;
}

export interface HealthCheck {
  status: string;
  database: boolean;
  version: string;
}

export interface AchievementEntry {
  id: number;
  achievement_key: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  tier: number;
  participant_id: number;
  display_name: string;
  matchday_number: number | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface SeasonAchievementsResponse {
  season_id: number;
  achievements: AchievementEntry[];
}

export interface SeasonSummary {
  id: number;
  name: string;
  status: string;
  matchday_current: number;
  total_participants: number;
  lineup_deadline_min: number;
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
  pending_players: number;
}

export interface HighlightPlayer {
  player_id: number;
  player_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  points: number;
  owner_name: string;
  goals: number;
  assists: number;
}

export interface DreamTeamPlayer {
  player_id: number;
  player_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  points: number;
}

export interface DreamTeamResponse {
  formation: string;
  total_points: number;
  players: DreamTeamPlayer[];
}

export interface MatchdayHighlightsResponse {
  matchday_number: number;
  mvp: HighlightPlayer | null;
  flop: HighlightPlayer | null;
  top_scorer: HighlightPlayer | null;
  top_assister: HighlightPlayer | null;
  dream_team: DreamTeamResponse | null;
  nightmare_team: DreamTeamResponse | null;
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

export interface FormMatch {
  played: boolean;
  result: number; // 0=L, 1=D, 2=W
  is_home: boolean;
  points: number;
}

export interface PlayerRecentForm {
  matches: FormMatch[];
  clean_sheets: number;
  goals: number;
  assists: number;
  penalty_goals: number;
  yellow_cards: number;
}

export interface SquadPlayerEntry {
  player_id: number;
  display_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  season_points: number;
  recent_form: PlayerRecentForm | null;
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
  id: number;
  pick_number: number;
  round_number: number;
  participant_id: number;
  display_name: string;
  draft_order: number | null;
  player_id: number;
  player_name: string;
  position: string;
  team_name: string;
  photo_path: string | null;
  dropped_player_name: string | null;
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
  next_participant_id: number | null;
}

// Draft management
export interface CreateDraftResponse {
  id: number;
  season_id: number;
  phase: string;
  draft_type: string;
  status: string;
}

export interface AddPickResponse {
  pick_number: number;
  round_number: number;
  participant_id: number;
  display_name: string;
  player_name: string;
  position: string;
  team_name: string;
}

export interface PlayerSearchItem {
  id: number;
  display_name: string;
  position: string;
  team_name: string;
  photo_path: string | null;
  is_already_picked: boolean;
}

export interface PlayerSearchResponse {
  players: PlayerSearchItem[];
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

export interface LineupHistoryPlayerEntry {
  player_id: number;
  player_name: string;
  position_slot: string;
  display_order: number;
  photo_path: string | null;
  points: number;
}

export interface LineupHistoryEntry {
  matchday_number: number;
  formation: string;
  total_points: number;
  confirmed_at: string | null;
  players: LineupHistoryPlayerEntry[];
}

export interface MissedCall {
  position: string;
  benched_name: string;
  benched_points: number;
  lined_up_name: string;
  lined_up_points: number;
}

export interface MatchdayAccuracy {
  matchday_number: number;
  actual_points: number;
  optimal_points: number;
  accuracy_pct: number;
  formation_used: string;
  optimal_formation: string;
  missed_calls: MissedCall[];
}

export interface AccuracyResponse {
  participant_id: number;
  display_name: string;
  season_name: string;
  avg_accuracy: number;
  perfect_weeks: number;
  total_missed_points: number;
  matchdays: MatchdayAccuracy[];
}

export interface AccuracyRankingEntry {
  rank: number;
  participant_id: number;
  display_name: string;
  avg_accuracy: number;
  perfect_weeks: number;
  total_missed_points: number;
  matchdays_played: number;
}

export interface AccuracyRankingResponse {
  season_id: number;
  season_name: string;
  entries: AccuracyRankingEntry[];
}

export interface LineupHistoryResponse {
  participant_id: number;
  display_name: string;
  season_name: string;
  lineups: LineupHistoryEntry[];
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

// Advanced stats (admin) — matches backend/src/features/stats/schemas_advanced.py

export interface AdvancedPlayerStat {
  player_id: number;
  display_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  matchdays_played: number;
  minutes_played: number;
  total_points: number;
  avg_points: number;
  std_dev: number;
  cv: number;
  p10: number;
  p50: number;
  p90: number;
  pp90: number;
  ci_lower: number;
  ci_upper: number;
  form_5: number | null;
  trend: "rising" | "stable" | "falling";
}

export interface AdvancedPlayersResponse {
  season_id: number;
  players: AdvancedPlayerStat[];
}

// Position value analysis (Phase 2)

export interface PositionTierPlayer {
  player_id: number;
  display_name: string;
  team_name: string;
  total_points: number;
  par: number;
}

export interface PositionTier {
  tier: number;
  label: string;
  min_points: number;
  max_points: number;
  players: PositionTierPlayer[];
}

export interface PositionAnalysis {
  position: string;
  player_count: number;
  replacement_level: number;
  avg_points: number;
  median_points: number;
  scarcity_index: number;
  tiers: PositionTier[];
}

export interface PositionValueResponse {
  season_id: number;
  positions: PositionAnalysis[];
}

// Draft history (Phase 3)

export interface PickValuePoint {
  pick_number: number;
  avg_total_points: number;
  sample_count: number;
}

export interface PositionRoundValue {
  round_number: number;
  position: string;
  avg_total_points: number;
  pick_count: number;
}

export interface RateEntry {
  round_range: string;
  rate_pct: number;
  total_picks: number;
}

export interface DraftHistoryResponse {
  pick_value_curve: PickValuePoint[];
  position_by_round: PositionRoundValue[];
  bust_rate: RateEntry[];
  steal_rate: RateEntry[];
}

// Context analysis (Phase 4)

export interface PlayerSplit {
  location: "home" | "away";
  matches: number;
  avg_points: number;
  total_points: number;
  goals: number;
  assists: number;
}

export interface PlayerSplitsResponse {
  player_id: number;
  display_name: string;
  season_id: number;
  splits: PlayerSplit[];
}

export interface TeamDependencyEntry {
  team_name: string;
  top_player_name: string;
  top_player_id: number;
  top_player_points: number;
  team_total_points: number;
  dependency_pct: number;
}

export interface TeamDependencyResponse {
  season_id: number;
  entries: TeamDependencyEntry[];
}

export interface ComparePlayerAxis {
  player_id: number;
  display_name: string;
  photo_path: string | null;
  position: string;
  team_name: string;
  goals_rate: number;
  assists_rate: number;
  avg_points: number;
  consistency: number;
  pp90: number;
  form: number;
}

export interface ComparePlayersResponse {
  season_id: number;
  players: ComparePlayerAxis[];
}
